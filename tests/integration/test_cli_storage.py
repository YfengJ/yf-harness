from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from yfharness.cli import app

runner = CliRunner()


def test_cli_persists_lists_and_exports_session(tmp_path: Path) -> None:
    env = {"YFH_DATA_DIR": str(tmp_path / "data"), "YFH_CONFIG_DIR": str(tmp_path / "config")}
    result = runner.invoke(app, ["run", "--output", "json", "persist me"], env=env)
    assert result.exit_code == 0, result.output
    session_id = json.loads(result.output)["session_id"]
    run_id = json.loads(result.output)["run_id"]

    listed = runner.invoke(app, ["sessions", "list"], env=env)
    assert listed.exit_code == 0, listed.output
    assert session_id in listed.output
    assert "persist me" in listed.output

    renamed = runner.invoke(app, ["sessions", "rename", session_id, "renamed"], env=env)
    archived = runner.invoke(app, ["sessions", "archive", session_id], env=env)
    visible = runner.invoke(app, ["sessions", "list"], env=env)
    archived_list = runner.invoke(app, ["sessions", "list", "--archived"], env=env)
    assert renamed.exit_code == 0, renamed.output
    assert archived.exit_code == 0, archived.output
    assert session_id not in visible.output
    assert session_id in archived_list.output
    assert "renamed" in archived_list.output

    exported = runner.invoke(app, ["sessions", "export", session_id, "--format", "json"], env=env)
    assert exported.exit_code == 0, exported.output
    payload = json.loads(exported.output)
    assert [message["role"] for message in payload["messages"]] == ["user", "assistant"]

    replayed = runner.invoke(app, ["replay", run_id], env=env)
    assert replayed.exit_code == 0, replayed.output
    replay_payload = json.loads(replayed.output)
    assert replay_payload["mode"] == "read_only_replay"
    assert replay_payload["run"]["run_id"] == run_id

    deleted = runner.invoke(app, ["sessions", "delete", session_id, "--yes"], env=env)
    assert deleted.exit_code == 0, deleted.output
