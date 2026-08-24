from __future__ import annotations

from pathlib import Path

import pytest
from textual.widgets import TextArea

from yfharness.tui.application import YFHarnessApp


@pytest.mark.asyncio
async def test_tui_mounts_creates_session_and_runs_mock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    app = YFHarnessApp()

    async with app.run_test(size=(120, 40)) as pilot:
        assert app.query_one("#run-state").renderable == "空闲"  # type: ignore[attr-defined]
        await pilot.press("ctrl+n")
        # Session creation runs in a Textual worker.  A single event-loop tick is
        # not enough on slower Windows runners, so wait for the worker contract
        # instead of relying on scheduler timing.
        await app.workers.wait_for_complete()
        assert app.current_session_id is not None

        prompt = app.query_one("#prompt", TextArea)
        prompt.load_text("TUI mock task")
        app.action_submit_prompt()
        for _ in range(30):
            await pilot.pause(0.02)
            messages = await app.sessions.messages(app.current_session_id)
            if len(messages) >= 2:
                break
        else:
            pytest.fail("TUI MockProvider run did not finish")

        # Message persistence happens before trace/session refresh. Wait for the
        # whole Textual worker so the app exits with no background coroutine.
        await app.workers.wait_for_complete()

        assert [message.role.value for message in messages] == ["user", "assistant"]
        assert "MockProvider" in messages[-1].text_content
        assert app.active_runner is None
        app.action_history_previous()
        assert prompt.text == "TUI mock task"


@pytest.mark.asyncio
async def test_tui_help_and_responsive_panels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    app = YFHarnessApp()

    async with app.run_test(size=(50, 15)) as pilot:
        await pilot.pause()
        assert app.query_one("#size-warning").display is True
        assert app.query_one("#sidebar").display is False
        assert app.query_one("#right-panel").display is False
        await pilot.press("f1")
        await pilot.pause()
        assert len(app.screen_stack) == 2
        await pilot.press("escape")
        await pilot.pause()
        assert len(app.screen_stack) == 1
