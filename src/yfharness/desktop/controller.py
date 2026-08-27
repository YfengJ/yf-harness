"""Thread-safe Qt bridge between QML and the async harness runtime."""

from __future__ import annotations

import asyncio
import json
import threading
from collections import deque
from collections.abc import Callable, Coroutine
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from PySide6.QtCore import (
    Property,
    QAbstractListModel,
    QByteArray,
    QModelIndex,
    QObject,
    QPersistentModelIndex,
    Qt,
    QUrl,
    Signal,
    Slot,
)

from yfharness.cli import _run_once
from yfharness.config.loader import load_config
from yfharness.config.paths import database_file
from yfharness.core.agent import AgentRunner
from yfharness.core.agent_events import (
    AgentEvent,
    BudgetUpdated,
    ModelEventObserved,
    StateChanged,
    ToolExecutionFinished,
    ToolExecutionStarted,
)
from yfharness.core.attachments import prepare_image
from yfharness.core.context import ContextBuilder
from yfharness.core.events import TextDelta
from yfharness.core.models import ApprovalDecision, ApprovalRequest, ContentPart, MessageRole
from yfharness.core.policies import AgentMode, ApprovalPolicy
from yfharness.core.review import ChangeReviewItem, WorkspaceReview
from yfharness.storage.database import Database
from yfharness.storage.models import SessionRecord
from yfharness.storage.repositories import FileChangeRepository, RunRepository, SessionRepository
from yfharness.tools.registry import builtin_tools
from yfharness.tools.security import WorkspaceGuard

_INVALID_MODEL_INDEX = QModelIndex()


class DictListModel(QAbstractListModel):
    """Small role-based model designed for QML ListView delegates."""

    def __init__(self, roles: list[str], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._items: list[dict[str, object]] = []
        self._role_ids = {
            Qt.ItemDataRole.UserRole + index + 1: name for index, name in enumerate(roles)
        }

    def rowCount(
        self,
        parent: QModelIndex | QPersistentModelIndex = _INVALID_MODEL_INDEX,
    ) -> int:
        return 0 if parent.isValid() else len(self._items)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid() or not 0 <= index.row() < len(self._items):
            return None
        name = self._role_ids.get(role)
        return self._items[index.row()].get(name) if name else None

    def roleNames(self) -> dict[int, QByteArray]:
        return {role: QByteArray(name.encode()) for role, name in self._role_ids.items()}

    def replace(self, items: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self._items = list(items)
        self.endResetModel()

    def append_item(self, item: dict[str, object]) -> None:
        row = len(self._items)
        self.beginInsertRows(QModelIndex(), row, row)
        self._items.append(item)
        self.endInsertRows()

    def update_last(self, **values: object) -> None:
        if not self._items:
            return
        self._items[-1].update(values)
        row = len(self._items) - 1
        index = self.index(row, 0)
        self.dataChanged.emit(index, index, list(self._role_ids))

    def take_first(self) -> dict[str, object] | None:
        if not self._items:
            return None
        self.beginRemoveRows(QModelIndex(), 0, 0)
        item = self._items.pop(0)
        self.endRemoveRows()
        return item


class _PendingApproval:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.decision = ApprovalDecision.DENY


@dataclass(frozen=True, slots=True)
class _QueuedRun:
    id: str
    prompt: str
    provider: str
    model: str
    workflow: str
    mode: AgentMode
    permissions: ApprovalPolicy
    attachments: tuple[ContentPart, ...]


class DesktopController(QObject):
    """Expose the real harness runtime to QML without blocking the UI thread."""

    busyChanged = Signal()
    statusChanged = Signal()
    currentSessionChanged = Signal()
    configurationChanged = Signal()
    queueChanged = Signal()
    attachmentsChanged = Signal()
    planChanged = Signal()
    contextChanged = Signal()
    errorOccurred = Signal(str)
    approvalRequested = Signal(str)
    agentEvent = Signal(str, object)
    taskFinished = Signal(str, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.sessions = DictListModel(["sessionId", "title", "detail", "updated"], self)
        self.messages = DictListModel(
            ["role", "speaker", "content", "timestamp", "isUser", "isTool", "pending"], self
        )
        self.instructions = DictListModel(["source", "label", "path", "scope", "tokens"], self)
        self.changes = DictListModel(
            ["changeId", "path", "summary", "diff", "status", "canRestore", "created"],
            self,
        )
        self.queue = DictListModel(["queueId", "prompt", "detail"], self)
        self.attachments = DictListModel(
            ["attachmentId", "name", "path", "mimeType", "size", "transfer"], self
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yfh-desktop")
        self._busy = False
        self._status = "准备就绪"
        self._current_session_id = ""
        self._current_session_title = "新任务"
        self._preview = False
        self._config = load_config()
        self._stream_text = ""
        self._runner_lock = threading.Lock()
        self._active_runner: AgentRunner | None = None
        self._runner_loop: asyncio.AbstractEventLoop | None = None
        self._approval_lock = threading.Lock()
        self._pending_approvals: dict[str, _PendingApproval] = {}
        self._queued_runs: deque[_QueuedRun] = deque()
        self._pending_attachments: list[tuple[str, ContentPart]] = []
        self._queue_paused = False
        self._last_plan = ""
        self._context_summary = "尚未运行任务"
        self._base_context_items: list[dict[str, object]] = []
        self.agentEvent.connect(self._handle_agent_event, Qt.ConnectionType.QueuedConnection)
        self.taskFinished.connect(self._handle_task_finished, Qt.ConnectionType.QueuedConnection)

    @Property(QObject, constant=True)
    def sessionModel(self) -> QObject:
        return self.sessions

    @Property(QObject, constant=True)
    def messageModel(self) -> QObject:
        return self.messages

    @Property(QObject, constant=True)
    def instructionModel(self) -> QObject:
        return self.instructions

    @Property(QObject, constant=True)
    def changeModel(self) -> QObject:
        return self.changes

    @Property(QObject, constant=True)
    def queueModel(self) -> QObject:
        return self.queue

    @Property(QObject, constant=True)
    def attachmentModel(self) -> QObject:
        return self.attachments

    @Property(int, notify=attachmentsChanged)
    def attachmentCount(self) -> int:
        return len(self._pending_attachments)

    @Property(bool, notify=busyChanged)
    def busy(self) -> bool:
        return self._busy

    @Property(int, notify=queueChanged)
    def queueCount(self) -> int:
        return len(self._queued_runs)

    @Property(bool, notify=planChanged)
    def hasExecutablePlan(self) -> bool:
        return bool(self._last_plan)

    @Property(str, notify=planChanged)
    def lastPlanPreview(self) -> str:
        return self._last_plan[:280]

    @Property(str, notify=contextChanged)
    def contextSummary(self) -> str:
        return self._context_summary

    @Property(str, notify=statusChanged)
    def statusText(self) -> str:
        return self._status

    @Property(str, notify=currentSessionChanged)
    def currentSessionId(self) -> str:
        return self._current_session_id

    @Property(str, notify=currentSessionChanged)
    def currentSessionTitle(self) -> str:
        return self._current_session_title

    @Property(str, constant=True)
    def workspacePath(self) -> str:
        if self._preview:
            return "本地项目 / YF-Harness"
        return str(self._config.workspace)

    @Property("QStringList", notify=configurationChanged)  # type: ignore[arg-type]
    def providerOptions(self) -> list[str]:
        return sorted(self._config.providers)

    @Property(str, notify=configurationChanged)
    def defaultProvider(self) -> str:
        return self._config.default_provider

    @Property(str, notify=configurationChanged)
    def defaultModel(self) -> str:
        return self._config.default_model

    @Property("QStringList", notify=configurationChanged)  # type: ignore[arg-type]
    def workflowOptions(self) -> list[str]:
        return sorted(self._config.workflows)

    @Property(str, notify=configurationChanged)
    def defaultWorkflow(self) -> str:
        return self._config.default_workflow

    @Slot(str, result=str)
    def workflowMode(self, name: str) -> str:
        return self._config.workflow(name).mode.value

    @Slot(str, result=str)
    def workflowPermissions(self, name: str) -> str:
        return self._config.workflow(name).permissions.value

    @Slot(str, result=str)
    def workflowDescription(self, name: str) -> str:
        workflow = self._config.workflow(name)
        visible = len(workflow.filter_definitions(builtin_tools().definitions()))
        return f"{workflow.label} · {visible} 个工具 · {len(workflow.hooks)} 个 Hook"

    @Slot(str, result="QStringList")
    def modelsForProvider(self, provider: str) -> list[str]:
        return [
            name
            for name, model in sorted(self._config.models.items())
            if model.provider == provider
        ]

    @Slot(str, bool)
    def addImage(self, value: str, send_to_model: bool) -> None:
        url = QUrl(value)
        local_path = url.toLocalFile() if url.isLocalFile() else value
        try:
            part = prepare_image(
                local_path, WorkspaceGuard(self._config.workspace), send_to_model=send_to_model
            )
        except Exception as exc:
            self.errorOccurred.emit(str(exc))
            return
        attachment_id = str(uuid4())
        self._pending_attachments.append((attachment_id, part))
        self._refresh_attachments()
        boundary = "将发送给模型" if send_to_model else "仅本地"
        self._set_status(f"已附加 {Path(part.path or '').name} · {boundary}")

    @Slot(str)
    def removeAttachment(self, attachment_id: str) -> None:
        self._pending_attachments = [
            item for item in self._pending_attachments if item[0] != attachment_id
        ]
        self._refresh_attachments()

    @Slot()
    def clearAttachments(self) -> None:
        self._pending_attachments.clear()
        self._refresh_attachments()

    @Slot()
    def bootstrap(self) -> None:
        self._submit("bootstrap", self._load_workspace)

    @Slot(str)
    def searchSessions(self, query: str) -> None:
        self._submit("sessions", lambda: self._load_sessions(query.strip() or None))

    @Slot()
    def newSession(self) -> None:
        if self._busy:
            return
        self._current_session_id = ""
        self._current_session_title = "新任务"
        self.messages.replace([])
        self.changes.replace([])
        self._reset_runtime_context()
        self._last_plan = ""
        self.planChanged.emit()
        self.currentSessionChanged.emit()
        self._set_status("等待任务")

    @Slot(str)
    def openSession(self, session_id: str) -> None:
        if self._busy or not session_id:
            return
        self._submit("open_session", lambda: self._load_session(session_id))

    @Slot(str, str, str, str, str)
    @Slot(str, str, str, str, str, str)
    def sendMessage(
        self,
        prompt: str,
        provider: str,
        model: str,
        workflow: str,
        mode: str,
        permissions: str = "",
    ) -> None:
        if not permissions:  # Compatibility with the 0.4 five-argument bridge.
            permissions = mode
            mode = workflow
            workflow = self._config.default_workflow
        prompt = prompt.strip()
        if not prompt:
            return
        if provider not in self._config.providers:
            self.errorOccurred.emit(f"未知 Provider：{provider}")
            return
        if model not in self._config.models or self._config.models[model].provider != provider:
            self.errorOccurred.emit("所选模型不属于当前 Provider")
            return
        if workflow not in self._config.workflows:
            self.errorOccurred.emit(f"未知工作流：{workflow}")
            return
        try:
            selected_mode = AgentMode(mode)
            selected_policy = ApprovalPolicy(permissions)
        except ValueError:
            self.errorOccurred.emit("运行模式或权限策略无效")
            return
        attachments = tuple(part for _, part in self._pending_attachments)
        self.clearAttachments()
        if self._busy:
            self._enqueue(
                prompt,
                provider,
                model,
                workflow,
                selected_mode,
                selected_policy,
                attachments,
            )
            return
        self._start_message(
            prompt,
            provider,
            model,
            workflow,
            selected_mode,
            selected_policy,
            attachments,
        )

    def _start_message(
        self,
        prompt: str,
        provider: str,
        model: str,
        workflow: str,
        mode: AgentMode,
        permissions: ApprovalPolicy,
        attachments: tuple[ContentPart, ...],
    ) -> None:
        if not self._current_session_id:
            self._current_session_title = prompt.splitlines()[0][:80]
            self.currentSessionChanged.emit()
        self.messages.append_item(_message_item("user", prompt, pending=False))
        self.messages.append_item(_message_item("assistant", "", pending=True))
        self._stream_text = ""
        self._set_busy(True)
        self._set_status("正在准备上下文")
        self._submit(
            "run",
            lambda: self._run_agent(
                prompt, provider, model, workflow, mode, permissions, attachments
            ),
        )

    def _enqueue(
        self,
        prompt: str,
        provider: str,
        model: str,
        workflow: str,
        mode: AgentMode,
        permissions: ApprovalPolicy,
        attachments: tuple[ContentPart, ...],
    ) -> None:
        queued = _QueuedRun(
            str(uuid4()), prompt, provider, model, workflow, mode, permissions, attachments
        )
        self._queued_runs.append(queued)
        self.queue.append_item(
            {
                "queueId": queued.id,
                "prompt": prompt,
                "detail": f"{model} · {workflow} · {mode.value}"
                + (f" · {len(attachments)} 张图片" if attachments else ""),
            }
        )
        self.queueChanged.emit()
        self._set_status(f"运行中 · 已排队 {len(self._queued_runs)} 项")

    @Slot()
    def clearQueue(self) -> None:
        self._queued_runs.clear()
        self.queue.replace([])
        self._queue_paused = False
        self.queueChanged.emit()
        self._set_status("队列已清空" if not self._busy else "运行中 · 队列已清空")

    @Slot()
    def resumeQueue(self) -> None:
        if self._busy or not self._queued_runs:
            return
        self._queue_paused = False
        self._start_next_queued()

    @Slot(str, str, str)
    @Slot(str, str, str, str)
    def executeLastPlan(
        self,
        provider: str,
        model: str,
        workflow: str,
        permissions: str = "",
    ) -> None:
        if not permissions:
            permissions = workflow
            workflow = self._config.default_workflow
        if not self._last_plan:
            self.errorOccurred.emit("当前会话没有可执行计划")
            return
        self.sendMessage(
            "请按照以下已经审阅的计划执行。逐步验证，不要扩大范围；遇到冲突先停止。\n\n"
            + self._last_plan,
            provider,
            model,
            workflow,
            AgentMode.AGENT.value,
            permissions,
        )

    @Slot(str)
    def restoreChange(self, record_id: str) -> None:
        if self._busy or not record_id or not self._current_session_id:
            return
        self._submit(
            "restore_change",
            lambda: self._restore_change(record_id, self._current_session_id),
        )

    @Slot()
    def forkSession(self) -> None:
        if self._busy or not self._current_session_id:
            return
        source_id = self._current_session_id
        self._submit("fork_session", lambda: self._fork_session(source_id))

    @Slot()
    def cancelRun(self) -> None:
        if not self._busy:
            return
        self._queue_paused = True
        with self._runner_lock:
            runner = self._active_runner
            loop = self._runner_loop
        if runner is not None and loop is not None:
            loop.call_soon_threadsafe(runner.cancel)
        with self._approval_lock:
            pending = list(self._pending_approvals.values())
        for item in pending:
            item.decision = ApprovalDecision.CANCEL_RUN
            item.event.set()
        self._set_status("正在取消")

    @Slot(str, bool)
    def resolveApproval(self, request_id: str, allowed: bool) -> None:
        with self._approval_lock:
            pending = self._pending_approvals.get(request_id)
        if pending is None:
            return
        pending.decision = ApprovalDecision.ALLOW_ONCE if allowed else ApprovalDecision.DENY
        pending.event.set()

    @Slot()
    def reloadConfiguration(self) -> None:
        try:
            self._config = load_config()
        except Exception as exc:
            self.errorOccurred.emit(f"配置加载失败：{exc}")
            return
        self.configurationChanged.emit()
        self._set_status("配置已刷新")

    @Slot()
    def seedPreview(self) -> None:
        self._preview = True
        self.sessions.replace(
            [
                {
                    "sessionId": "preview-1",
                    "title": "桌面应用重构",
                    "detail": "mock-default · agent",
                    "updated": "刚刚",
                },
                {
                    "sessionId": "preview-2",
                    "title": "Agent 安全边界",
                    "detail": "mock-default · review",
                    "updated": "昨天",
                },
            ]
        )
        self._current_session_id = "preview-1"
        self._current_session_title = "桌面应用重构"
        self.messages.replace(
            [
                _message_item("user", "把终端界面重做成真正可以双击启动的桌面应用。", False),
                _message_item(
                    "assistant",
                    "桌面工作区已经就绪。核心 Agent、会话记录和安全审批仍由 "
                    "YF-Harness 负责，界面现在运行在独立的 Qt 窗口中。",
                    False,
                ),
                {
                    **_message_item("tool", "已检查桌面运行环境 · 7 项通过", False),
                    "speaker": "运行记录",
                },
            ]
        )
        self._base_context_items = [
            {
                "source": "codex",
                "label": "Codex 项目指令 · workspace",
                "path": "AGENTS.md",
                "scope": "workspace",
                "tokens": 184,
            },
            {
                "source": "cursor",
                "label": "Cursor 规则 · Python conventions",
                "path": ".cursor/rules/python.mdc",
                "scope": "src/**/*.py",
                "tokens": 96,
            },
        ]
        self.instructions.replace(self._base_context_items)
        self.changes.replace(
            [
                {
                    "changeId": "preview-change",
                    "path": "src/yfharness/desktop/controller.py",
                    "summary": "修改文件",
                    "diff": "+ queued messages\n+ conflict-safe restore",
                    "status": "active",
                    "canRestore": True,
                    "created": "刚刚",
                }
            ]
        )
        self.currentSessionChanged.emit()
        self._set_status("本地运行 · 安全模式")

    @Slot()
    def shutdown(self) -> None:
        self.cancelRun()
        self._executor.shutdown(wait=False, cancel_futures=True)

    def _submit(
        self,
        kind: str,
        coroutine_factory: Callable[[], Coroutine[Any, Any, object]],
    ) -> None:
        future = self._executor.submit(lambda: asyncio.run(coroutine_factory()))
        future.add_done_callback(lambda completed: self._future_done(kind, completed))

    def _future_done(self, kind: str, future: Future[object]) -> None:
        try:
            payload: object = future.result()
        except BaseException as exc:
            payload = {"error": str(exc) or type(exc).__name__}
        self.taskFinished.emit(kind, payload)

    async def _load_workspace(self) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        await RunRepository(database).mark_interrupted()
        sessions = await SessionRepository(database).list()
        builder = ContextBuilder(self._config.workspace, lambda text: max(1, len(text) // 4))
        instructions = builder.instruction_documents()
        return {
            "sessions": [_session_item(item) for item in sessions],
            "instructions": [
                {
                    "source": item.source,
                    "label": item.label,
                    "path": item.path,
                    "scope": item.scope,
                    "tokens": max(1, len(item.content) // 4),
                }
                for item in instructions
            ],
        }

    async def _load_sessions(self, query: str | None) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        sessions = await SessionRepository(database).list(query=query)
        return {"sessions": [_session_item(item) for item in sessions]}

    async def _load_session(self, session_id: str) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        repository = SessionRepository(database)
        session = await repository.get(session_id)
        if session is None:
            raise KeyError(f"会话不存在：{session_id}")
        messages = await repository.messages(session_id)
        changes = await WorkspaceReview(
            self._config.workspace,
            FileChangeRepository(database),
        ).list_for_session(session_id)
        return {
            "session": _session_item(session),
            "messages": [
                _message_item(message.role.value, message.text_content, pending=False)
                for message in messages
                if message.role is not MessageRole.SYSTEM
            ],
            "changes": [_change_item(item) for item in changes],
        }

    async def _load_changes(self, session_id: str) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        items = await WorkspaceReview(
            self._config.workspace,
            FileChangeRepository(database),
        ).list_for_session(session_id)
        return {"changes": [_change_item(item) for item in items]}

    async def _restore_change(self, record_id: str, session_id: str) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        review = WorkspaceReview(self._config.workspace, FileChangeRepository(database))
        message = await review.restore(record_id)
        items = await review.list_for_session(session_id)
        return {"message": message, "changes": [_change_item(item) for item in items]}

    async def _fork_session(self, session_id: str) -> dict[str, object]:
        database = Database(database_file())
        await database.initialize()
        repository = SessionRepository(database)
        session = await repository.fork(session_id)
        messages = await repository.messages(session.id)
        return {
            "session": _session_item(session),
            "messages": [
                _message_item(message.role.value, message.text_content, pending=False)
                for message in messages
                if message.role is not MessageRole.SYSTEM
            ],
        }

    async def _run_agent(
        self,
        prompt: str,
        provider: str,
        model: str,
        workflow: str,
        mode: AgentMode,
        permissions: ApprovalPolicy,
        attachments: tuple[ContentPart, ...],
    ) -> dict[str, object]:
        loop = asyncio.get_running_loop()

        def runner_sink(runner: AgentRunner) -> None:
            with self._runner_lock:
                self._active_runner = runner
                self._runner_loop = loop

        result = await _run_once(
            prompt,
            provider,
            model,
            self._config.agent.max_run_seconds,
            stream=False,
            session_id=self._current_session_id or None,
            save=True,
            mode=mode,
            permissions=permissions,
            workflow_name=workflow,
            attachment_parts=list(attachments),
            event_sink=self._observe_event,
            approval_handler=self._request_approval,
            runner_sink=runner_sink,
        )
        result["mode"] = mode.value
        result["workflow_id"] = workflow
        return result

    async def _observe_event(self, event: AgentEvent) -> None:
        if isinstance(event, StateChanged):
            self.agentEvent.emit("state", event.state.value)
        elif isinstance(event, ModelEventObserved) and isinstance(event.event, TextDelta):
            self.agentEvent.emit("delta", event.event.text)
        elif isinstance(event, ToolExecutionStarted):
            self.agentEvent.emit(
                "tool_start",
                {"name": event.call.name, "arguments": event.call.arguments},
            )
        elif isinstance(event, ToolExecutionFinished):
            self.agentEvent.emit(
                "tool_finish",
                {"success": event.result.success, "summary": event.result.summary},
            )
        elif isinstance(event, BudgetUpdated):
            self.agentEvent.emit(
                "usage",
                {
                    "tokens": event.usage.total_tokens,
                    "estimated": event.usage.estimated,
                    "cost": event.cost,
                },
            )

    async def _request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        pending = _PendingApproval()
        with self._approval_lock:
            self._pending_approvals[request.id] = pending
        self.approvalRequested.emit(json.dumps(request.model_dump(mode="json"), ensure_ascii=False))
        try:
            await asyncio.to_thread(pending.event.wait)
            return pending.decision
        finally:
            with self._approval_lock:
                self._pending_approvals.pop(request.id, None)

    @Slot(str, object)
    def _handle_agent_event(self, kind: str, payload: object) -> None:
        if kind == "state":
            self._set_status(_state_label(str(payload)))
        elif kind == "delta":
            self._stream_text += str(payload)
            self.messages.update_last(content=self._stream_text, pending=True)
        elif kind == "tool_start" and isinstance(payload, dict):
            self.messages.append_item(
                _message_item("tool", f"正在运行 {payload.get('name', '工具')}…", pending=True)
            )
        elif kind == "tool_finish" and isinstance(payload, dict):
            symbol = "完成" if payload.get("success") else "失败"
            self.messages.update_last(
                content=f"{symbol} · {payload.get('summary', '')}", pending=False
            )
            self.messages.append_item(_message_item("assistant", self._stream_text, pending=True))
        elif kind == "usage" and isinstance(payload, dict):
            marker = "估算" if payload.get("estimated") else "精确"
            self._set_status(f"运行中 · {payload.get('tokens', 0)} tokens ({marker})")

    @Slot(str, object)
    def _handle_task_finished(self, kind: str, payload: object) -> None:
        if isinstance(payload, dict) and payload.get("error"):
            message = str(payload["error"])
            if kind == "run":
                self.messages.update_last(content=f"运行未完成：{message}", pending=False)
                self._set_busy(False)
                self._set_status("运行中断")
                self._queue_paused = True
            self.errorOccurred.emit(message)
            self._clear_runner()
            return
        if not isinstance(payload, dict):
            return
        if kind in {"bootstrap", "sessions"}:
            sessions = payload.get("sessions", [])
            if isinstance(sessions, list):
                self.sessions.replace(sessions)
            instructions = payload.get("instructions", [])
            if isinstance(instructions, list):
                self._base_context_items = instructions
                self.instructions.replace(self._base_context_items)
            if not self._busy:
                self._set_status("准备就绪")
        elif kind == "open_session":
            session = payload.get("session")
            messages = payload.get("messages")
            changes = payload.get("changes")
            if isinstance(session, dict) and isinstance(messages, list):
                self._current_session_id = str(session["sessionId"])
                self._current_session_title = str(session["title"])
                self.messages.replace(messages)
                if isinstance(changes, list):
                    self.changes.replace(changes)
                self._reset_runtime_context()
                self.currentSessionChanged.emit()
                self._set_status("会话已载入")
        elif kind == "run":
            text = str(payload.get("text", ""))
            if not self._stream_text:
                self.messages.update_last(content=text, pending=False)
            else:
                self.messages.update_last(content=self._stream_text, pending=False)
            self._current_session_id = str(payload.get("session_id", ""))
            self.currentSessionChanged.emit()
            self._set_busy(False)
            usage = payload.get("usage", {})
            tokens = usage.get("total_tokens", 0) if isinstance(usage, dict) else 0
            self._set_status(f"已完成 · {tokens} tokens")
            if payload.get("mode") == AgentMode.PLAN.value and text.strip():
                self._last_plan = text.strip()
                self.planChanged.emit()
            context = payload.get("context")
            if isinstance(context, dict):
                sources = context.get("sources", [])
                if isinstance(sources, list):
                    self.instructions.replace(
                        [_context_item(item) for item in sources if isinstance(item, dict)]
                    )
                estimated = context.get("estimated_tokens", 0)
                budget = context.get("budget_tokens", 0)
                compacted = " · 已压缩" if context.get("compacted") else ""
                self._context_summary = f"{estimated}/{budget} tokens{compacted}"
                self.contextChanged.emit()
            self._clear_runner()
            self._submit("sessions", lambda: self._load_sessions(None))
            if self._current_session_id:
                self._submit("changes", lambda: self._load_changes(self._current_session_id))
            self._start_next_queued()
        elif kind == "changes":
            changes = payload.get("changes", [])
            if isinstance(changes, list):
                self.changes.replace(changes)
        elif kind == "restore_change":
            changes = payload.get("changes", [])
            if isinstance(changes, list):
                self.changes.replace(changes)
            self._set_status(str(payload.get("message", "变更已撤销")))
        elif kind == "fork_session":
            session = payload.get("session")
            messages = payload.get("messages")
            if isinstance(session, dict) and isinstance(messages, list):
                self._current_session_id = str(session["sessionId"])
                self._current_session_title = str(session["title"])
                self.messages.replace(messages)
                self.changes.replace([])
                self._reset_runtime_context()
                self.currentSessionChanged.emit()
                self._set_status("已创建会话分支")
                self._submit("sessions", lambda: self._load_sessions(None))

    def _start_next_queued(self) -> None:
        if self._busy or self._queue_paused or not self._queued_runs:
            return
        queued = self._queued_runs.popleft()
        self.queue.take_first()
        self.queueChanged.emit()
        self._start_message(
            queued.prompt,
            queued.provider,
            queued.model,
            queued.workflow,
            queued.mode,
            queued.permissions,
            queued.attachments,
        )

    def _clear_runner(self) -> None:
        with self._runner_lock:
            self._active_runner = None
            self._runner_loop = None

    def _reset_runtime_context(self) -> None:
        self.instructions.replace(self._base_context_items)
        self._context_summary = "会话上下文将在下次运行时刷新"
        self.contextChanged.emit()

    def _refresh_attachments(self) -> None:
        self.attachments.replace(
            [
                {
                    "attachmentId": attachment_id,
                    "name": Path(part.path or "").name,
                    "path": part.path or "",
                    "mimeType": part.mime_type or "",
                    "size": part.size_bytes or 0,
                    "transfer": (
                        "发送给模型" if part.transfer.value == "remote_model" else "仅本地"
                    ),
                }
                for attachment_id, part in self._pending_attachments
            ]
        )
        self.attachmentsChanged.emit()

    def _set_busy(self, value: bool) -> None:
        if self._busy != value:
            self._busy = value
            self.busyChanged.emit()

    def _set_status(self, value: str) -> None:
        if self._status != value:
            self._status = value
            self.statusChanged.emit()


def _session_item(session: SessionRecord) -> dict[str, object]:
    return {
        "sessionId": session.id,
        "title": session.title,
        "detail": f"{session.model} · {session.mode}",
        "updated": _relative_time(session.updated_at),
    }


def _change_item(item: ChangeReviewItem) -> dict[str, object]:
    return {
        "changeId": item.id,
        "path": item.path,
        "summary": item.summary,
        "diff": item.diff,
        "status": item.status,
        "canRestore": item.can_restore,
        "created": item.created_at,
    }


def _context_item(item: dict[str, object]) -> dict[str, object]:
    return {
        "source": str(item.get("kind", "context")),
        "label": str(item.get("label", "上下文来源")),
        "path": str(item.get("path") or "运行时上下文"),
        "scope": str(item.get("scope") or item.get("kind", "runtime")),
        "tokens": _safe_int(item.get("estimated_tokens")),
    }


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return 0


def _message_item(role: str, content: str, pending: bool) -> dict[str, object]:
    is_user = role == MessageRole.USER.value
    is_tool = role == MessageRole.TOOL.value
    speaker = "你" if is_user else ("运行记录" if is_tool else "YF-Harness")
    return {
        "role": role,
        "speaker": speaker,
        "content": content,
        "timestamp": datetime.now().strftime("%H:%M"),
        "isUser": is_user,
        "isTool": is_tool,
        "pending": pending,
    }


def _relative_time(value: datetime) -> str:
    now = datetime.now(value.tzinfo)
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 60:
        return "刚刚"
    if seconds < 3600:
        return f"{seconds // 60} 分钟前"
    if seconds < 86_400:
        return f"{seconds // 3600} 小时前"
    return value.strftime("%m月%d日")


def _state_label(value: str) -> str:
    labels = {
        "building_context": "正在整理上下文",
        "requesting_model": "正在请求模型",
        "streaming": "正在生成",
        "validating_tool": "正在校验工具",
        "awaiting_approval": "等待你的审批",
        "executing_tool": "正在执行工具",
        "compacting": "正在压缩上下文",
        "completed": "已完成",
        "cancelled": "已取消",
        "failed": "运行失败",
    }
    return labels.get(value, value)
