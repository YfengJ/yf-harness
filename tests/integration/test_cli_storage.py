from __future__ import annotations

import json
from pathlib import Path

import pytest
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
    assert payload["messages"][0]["content"][0]["text"] == "persist me"
    assert "附加文件上下文" not in payload["messages"][0]["content"][0]["text"]

    replayed = runner.invoke(app, ["replay", run_id], env=env)
    assert replayed.exit_code == 0, replayed.output
    replay_payload = json.loads(replayed.output)
    assert replay_payload["mode"] == "read_only_replay"
    assert replay_payload["run"]["run_id"] == run_id

    usage = runner.invoke(app, ["usage", "--session", session_id, "--output", "json"], env=env)
    assert usage.exit_code == 0, usage.output
    usage_payload = json.loads(usage.output)
    assert usage_payload["source"] == "local_usage_records"
    assert usage_payload["provider_balance"] == "unavailable"
    assert usage_payload["overview"]["session"]["run_count"] == 1
    assert usage_payload["overview"]["session"]["unknown_cost_runs"] == 1

    usage_text = runner.invoke(app, ["usage", "--session", session_id], env=env)
    assert usage_text.exit_code == 0, usage_text.output
    assert "1 次成本未知" in usage_text.output

    compacted = runner.invoke(app, ["sessions", "compact", session_id], env=env)
    assert compacted.exit_code == 0, compacted.output
    assert "已压缩会话" in compacted.output

    continued = runner.invoke(
        app,
        ["run", "--session", session_id, "--output", "json", "continue after compaction"],
        env=env,
    )
    assert continued.exit_code == 0, continued.output
    continued_payload = json.loads(continued.output)
    assert continued_payload["context"]["compaction_status"] == "reused"
    assert continued_payload["context"]["compacted"] is True

    deleted = runner.invoke(app, ["sessions", "delete", session_id, "--yes"], env=env)
    assert deleted.exit_code == 0, deleted.output


def test_invalid_skill_fails_before_creating_persistent_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    skill = tmp_path / ".agents" / "skills" / "hidden" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: hidden\ndescription: hidden\nuser-invocable: false\n---\nHidden",
        encoding="utf-8",
    )
    env = {"YFH_DATA_DIR": str(tmp_path / "data"), "YFH_CONFIG_DIR": str(tmp_path / "config")}

    failed = runner.invoke(app, ["run", "--skill", "hidden", "task"], env=env)
    listed = runner.invoke(app, ["sessions", "list"], env=env)

    assert failed.exit_code == 1
    assert "不允许用户显式调用" in failed.output
    assert listed.exit_code == 0
    assert listed.output == ""
