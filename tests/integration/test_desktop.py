from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication, QImage

from yfharness.core.models import ModelConfig
from yfharness.desktop.controller import DesktopController, DictListModel


@pytest.fixture(scope="module")
def qt_application() -> Iterator[QGuiApplication]:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    os.environ.setdefault("QSG_RHI_BACKEND", "software")
    application = QGuiApplication.instance() or QGuiApplication([])
    yield application


def _wait_until(predicate: object, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        QCoreApplication.processEvents()
        if callable(predicate) and predicate():
            return
        time.sleep(0.01)
    pytest.fail("Qt desktop operation timed out")


def _item(model: DictListModel, row: int) -> dict[str, object]:
    index = model.index(row, 0)
    return {
        bytes(name).decode(): model.data(index, role) for role, name in model.roleNames().items()
    }


@pytest.mark.desktop
def test_desktop_controller_runs_and_persists_mock_task(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    controller = DesktopController()

    assert controller.defaultWorkflow == "balanced"
    assert controller.workflowMode("plan") == "plan"
    assert controller.workflowPermissions("guarded") == "always_ask"
    assert "32,000 context" in controller.modelDescription("mock-default")

    controller.sendMessage(
        "/goal Ship a focused desktop workflow",
        "mock",
        "mock-default",
        "balanced",
        "agent",
        "safe_auto",
    )
    assert controller.hasActiveGoal
    assert controller.currentGoal == "Ship a focused desktop workflow"

    controller.sendMessage(
        "Desktop mock task",
        "mock",
        "mock-default",
        "balanced",
        "agent",
        "safe_auto",
    )
    _wait_until(lambda: not controller.busy and bool(controller.currentSessionId))

    assert controller.messages.rowCount() == 2
    assert _item(controller.messages, 0)["content"] == "Desktop mock task"
    assert "MockProvider" in str(_item(controller.messages, 1)["content"])
    assert controller.statusText.startswith("已完成")
    _wait_until(lambda: controller.sessions.rowCount() == 1)
    assert controller.contextTokens > 0
    assert controller.contextBudget > controller.contextTokens
    assert controller.contextSourceCount > 0
    assert any(
        _item(controller.instructions, row)["source"] == "goal"
        for row in range(controller.instructions.rowCount())
    )
    _wait_until(lambda: controller.usage.rowCount() == 3)
    assert _item(controller.usage, 0)["tokens"] > 0
    assert _item(controller.usage, 1)["label"] == "今日"
    assert "Provider 账户余额" not in str(_item(controller.usage, 1)["budget"])

    controller.compactContext()
    _wait_until(lambda: controller.contextCompactionStatus == "manual")
    assert controller.contextCompacted
    assert "下次运行" in controller.contextSummary

    session_id = controller.currentSessionId
    controller.newSession()
    assert not controller.hasActiveGoal
    controller.openSession(session_id)
    _wait_until(lambda: controller.currentSessionId == session_id)
    assert controller.currentGoal == "Ship a focused desktop workflow"
    assert controller.contextCompactionStatus == "stored"
    assert controller.contextCompacted
    controller.completeGoal()
    _wait_until(lambda: controller.goalStatus == "completed")
    controller.clearGoal()
    assert controller.currentGoal == ""
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_can_switch_configured_model_in_existing_session(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    controller = DesktopController()
    controller._config.models["mock-fast"] = ModelConfig(
        id="mock-fast",
        provider="mock",
        model="mock-fast",
        supports_native_tools=True,
        context_window=16_000,
        max_output_tokens=2_048,
    )

    controller.sendMessage("Start", "mock", "mock-default", "agent", "safe_auto")
    _wait_until(lambda: not controller.busy and bool(controller.currentSessionId))
    controller.sendMessage(
        "Continue with the faster model",
        "mock",
        "mock-fast",
        "balanced",
        "agent",
        "safe_auto",
    )
    _wait_until(lambda: not controller.busy and controller.currentSessionModel == "mock-fast")

    assert controller.messages.rowCount() == 4
    assert controller.modelDescription("mock-fast").endswith("16,000 context")
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_queues_follow_up_and_executes_reviewed_plan(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    controller = DesktopController()

    controller.sendMessage("First task", "mock", "mock-default", "agent", "safe_auto")
    controller.sendMessage("Queued task", "mock", "mock-default", "review", "deny_writes")
    assert controller.queueCount == 1
    _wait_until(lambda: not controller.busy and controller.queueCount == 0)

    assert controller.messages.rowCount() == 4
    assert _item(controller.messages, 2)["content"] == "Queued task"

    controller.sendMessage("Make a plan", "mock", "mock-default", "plan", "deny_writes")
    _wait_until(lambda: not controller.busy and controller.hasExecutablePlan)
    previous_count = controller.messages.rowCount()
    controller.executeLastPlan("mock", "mock-default", "safe_auto")
    _wait_until(lambda: not controller.busy and controller.messages.rowCount() > previous_count)

    execution_prompt = str(_item(controller.messages, previous_count)["content"])
    assert "已经审阅的计划" in execution_prompt
    assert "MockProvider" in execution_prompt
    controller.shutdown()


@pytest.mark.desktop
def test_new_session_resets_runtime_context_to_project_instructions(
    qt_application: QGuiApplication,
) -> None:
    controller = DesktopController()
    controller.seedPreview()
    controller.instructions.replace(
        [
            {
                "source": "runtime",
                "label": "Previous run",
                "path": "old.py",
                "scope": "runtime",
                "tokens": 42,
            }
        ]
    )

    controller.newSession()

    assert controller.instructions.rowCount() == 2
    assert _item(controller.instructions, 0)["path"] == "AGENTS.md"
    assert controller.contextSummary == "会话上下文将在下次运行时刷新"
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_image_attachment_keeps_transfer_choice_explicit(
    qt_application: QGuiApplication,
    tmp_path: Path,
) -> None:
    controller = DesktopController()
    controller._config.workspace = tmp_path
    image = tmp_path / "screen.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    controller.addImage(image.as_uri(), False)

    assert controller.attachmentCount == 1
    assert _item(controller.attachments, 0)["transfer"] == "仅本地"
    attachment_id = str(_item(controller.attachments, 0)["attachmentId"])
    controller.removeAttachment(attachment_id)
    assert controller.attachmentCount == 0
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_file_attachment_is_real_bounded_context(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    controller = DesktopController()
    controller._config.workspace = tmp_path
    notes = tmp_path / "notes.md"
    notes.write_text("桌面附件必须进入真实上下文", encoding="utf-8")

    controller.addFile(notes.as_uri())

    assert controller.attachmentCount == 1
    assert _item(controller.attachments, 0)["transfer"] == "作为上下文"
    controller.sendMessage(
        "总结附件",
        "mock",
        "mock-default",
        "balanced",
        "agent",
        "safe_auto",
    )
    _wait_until(lambda: not controller.busy and bool(controller.currentSessionId))

    assert controller.attachmentCount == 0
    assert any(
        _item(controller.instructions, row)["source"] == "attachment"
        and _item(controller.instructions, row)["path"] == "notes.md"
        for row in range(controller.instructions.rowCount())
    )
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_discovers_filters_and_runs_explicit_project_skill(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    skill = tmp_path / ".agents" / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: review\ndescription: Review a target\n---\nReview $ARGUMENTS",
        encoding="utf-8",
    )
    controller = DesktopController()

    assert controller.skillCount == 1
    assert controller.skillIdAt(0) == "codex:review"
    controller.filterSkills("$missing")
    assert controller.skillCount == 0
    controller.filterSkills("$rev")
    assert controller.skillIdAt(0) == "codex:review"

    controller.sendMessage(
        "$codex:review src/app.py",
        "mock",
        "mock-default",
        "balanced",
        "review",
        "deny_writes",
    )
    _wait_until(lambda: not controller.busy and bool(controller.currentSessionId))

    assert any(
        _item(controller.instructions, row)["source"] == "skill"
        for row in range(controller.instructions.rowCount())
    )
    controller.shutdown()


@pytest.mark.desktop
def test_desktop_opens_and_remembers_selected_workspace(
    qt_application: QGuiApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = tmp_path / "config"
    data = tmp_path / "data"
    project = tmp_path / "selected-project"
    project.mkdir()
    skill = project / ".agents" / "skills" / "selected" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: selected\ndescription: Selected workspace skill\n---\n"
        "Use SELECTED-WORKSPACE-CONTEXT",
        encoding="utf-8",
    )
    monkeypatch.setenv("YFH_CONFIG_DIR", str(config))
    monkeypatch.setenv("YFH_DATA_DIR", str(data))
    controller = DesktopController()

    controller.setWorkspace(project.as_uri())
    _wait_until(lambda: controller.statusText == "准备就绪")

    assert controller.workspacePath == str(project)
    assert controller.skillIdAt(0) == "codex:selected"
    assert '"workspace"' in (config / "desktop-state.json").read_text(encoding="utf-8")

    controller.sendMessage(
        "$codex:selected verify",
        "mock",
        "mock-default",
        "balanced",
        "review",
        "deny_writes",
    )
    _wait_until(lambda: not controller.busy and bool(controller.currentSessionId))
    assert any(
        _item(controller.instructions, row)["source"] == "skill"
        and _item(controller.instructions, row)["path"] == ".agents/skills/selected/SKILL.md"
        for row in range(controller.instructions.rowCount())
    )
    controller.shutdown()

    restored = DesktopController()
    assert restored.workspacePath == str(project)
    restored.shutdown()


@pytest.mark.desktop
def test_desktop_qml_smoke_starts_without_runtime_errors(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "YFH_CONFIG_DIR": str(tmp_path / "config"),
            "YFH_DATA_DIR": str(tmp_path / "data"),
        }
    )

    completed = subprocess.run(
        [sys.executable, "-m", "yfharness.desktop.app", "--smoke-test"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert "failed to load" not in completed.stderr.lower()
    assert "TypeError" not in completed.stderr
    assert "ReferenceError" not in completed.stderr
    qml = (
        Path(__file__).parents[2] / "src" / "yfharness" / "desktop" / "qml" / "Main.qml"
    ).read_text(encoding="utf-8")
    assert all(
        f'objectName: "{name}"' in qml
        for name in (
            "commandCenter",
            "sidebarSettings",
            "attachmentButton",
            "sendButton",
            "sessionTitle",
            "taskStatusBar",
            "composerActions",
            "taskEmptyState",
        )
    )
    assert "想做什么？直接说一句就好。" in qml
    assert all(removed not in qml for removed in ("理解这个项目", "规划一次改动", "检查当前风险"))
    assert all(
        contract in qml
        for contract in (
            "id: attachmentMenu",
            'text: "添加图片"',
            'text: "添加文件"',
            "fileMode: FileDialog.OpenFiles",
            "controller.addImage(",
            "controller.addFile(",
        )
    )


@pytest.mark.desktop
def test_desktop_qml_renders_inspector_preview(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "YFH_CONFIG_DIR": str(tmp_path / "config"),
            "YFH_DATA_DIR": str(tmp_path / "data"),
        }
    )
    screenshot = tmp_path / "inspector-preview.png"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "yfharness.desktop.app",
            "--screenshot",
            str(screenshot),
            "--preview-tab",
            "1",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert screenshot.stat().st_size > 10_000
    assert "TypeError" not in completed.stderr
    assert "ReferenceError" not in completed.stderr


@pytest.mark.desktop
def test_desktop_qml_renders_command_center_preview(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "YFH_CONFIG_DIR": str(tmp_path / "config"),
            "YFH_DATA_DIR": str(tmp_path / "data"),
        }
    )
    screenshot = tmp_path / "command-center-preview.png"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "yfharness.desktop.app",
            "--screenshot",
            str(screenshot),
            "--preview-command",
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert screenshot.stat().st_size > 10_000
    assert "TypeError" not in completed.stderr
    assert "ReferenceError" not in completed.stderr


@pytest.mark.desktop
@pytest.mark.parametrize(("width", "height"), [(1040, 720), (1280, 800), (1480, 824)])
def test_desktop_qml_keeps_composer_inside_responsive_window(
    tmp_path: Path,
    width: int,
    height: int,
) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "QT_QPA_PLATFORM": "offscreen",
            "QSG_RHI_BACKEND": "software",
            "YFH_CONFIG_DIR": str(tmp_path / "config"),
            "YFH_DATA_DIR": str(tmp_path / "data"),
        }
    )
    screenshot = tmp_path / f"responsive-{width}x{height}.png"
    report = tmp_path / f"responsive-{width}x{height}.json"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "yfharness.desktop.app",
            "--screenshot",
            str(screenshot),
            "--layout-report",
            str(report),
            "--stress-preview",
            "--width",
            str(width),
            "--height",
            str(height),
        ],
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    image = QImage(str(screenshot))
    assert (image.width(), image.height()) == (width, height)
    payload = json.loads(report.read_text(encoding="utf-8"))
    expected_items = {
        "sidebar",
        "workspace",
        "composer",
        "promptInput",
        "taskStatusBar",
        "composerActions",
        "sessionTitle",
        "sidebarSettings",
        "attachmentButton",
        "sendButton",
    }
    assert expected_items <= set(payload["items"])
    assert all(item["within_window"] for item in payload["items"].values())
    assert "TypeError" not in completed.stderr
    assert "ReferenceError" not in completed.stderr
