from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication

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
