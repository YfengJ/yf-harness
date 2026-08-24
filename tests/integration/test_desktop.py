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

    controller.sendMessage(
        "Desktop mock task",
        "mock",
        "mock-default",
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
