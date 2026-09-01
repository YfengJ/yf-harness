from __future__ import annotations

import json
import os
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

import pytest
from typer.testing import CliRunner

from yfharness import __version__
from yfharness.cli import app

runner = CliRunner()


def test_runtime_version_matches_installed_metadata() -> None:
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == __version__ == version("yf-harness")


def test_run_mock_streams_text() -> None:
    result = runner.invoke(app, ["run", "--no-save", "--provider", "mock", "你好"])

    assert result.exit_code == 0, result.output
    assert "MockProvider" in result.output


def test_run_mock_json_output() -> None:
    result = runner.invoke(app, ["run", "--no-save", "--output", "json", "你好"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["context"]["estimated_tokens"] > 0
    assert payload["context"]["sources"]
    assert payload["provider"] == "mock"
    assert payload["workflow"]["id"] == "balanced"
    assert "read_file" in payload["workflow"]["visible_tools"]
    assert payload["usage"]["estimated"] is True


def test_run_reads_stdin() -> None:
    result = runner.invoke(app, ["run", "--no-save", "--output", "json"], input="stdin task")

    assert result.exit_code == 0, result.output


def test_run_rejects_empty_input() -> None:
    result = runner.invoke(app, ["run"], input="")

    assert result.exit_code == 2
    assert "任务内容不能为空" in result.output


def test_unknown_provider_is_nonzero() -> None:
    result = runner.invoke(app, ["run", "--no-save", "--provider", "missing", "hello"])

    assert result.exit_code == 1
    assert "unknown provider" in result.output


def test_run_reads_task_file(tmp_path: Path) -> None:
    task = tmp_path / "task.md"
    task.write_text("file task", encoding="utf-8")

    result = runner.invoke(app, ["run", "--no-save", "--output", "json", "--file", str(task)])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["text"]


def test_run_rejects_argument_and_file_together(tmp_path: Path) -> None:
    task = tmp_path / "task.md"
    task.write_text("file task", encoding="utf-8")

    result = runner.invoke(app, ["run", "--no-save", "argument", "--file", str(task)])

    assert result.exit_code == 2


def test_discovery_config_and_doctor_commands(tmp_path: Path) -> None:
    env = {
        "YFH_CONFIG_DIR": str(tmp_path / "config"),
        "YFH_DATA_DIR": str(tmp_path / "data"),
    }

    providers = runner.invoke(app, ["providers", "list"], env=env)
    models = runner.invoke(app, ["models", "list"], env=env)
    tools = runner.invoke(app, ["tools", "list"], env=env)
    workflows = runner.invoke(app, ["workflows", "list"], env=env)
    config_path = runner.invoke(app, ["config", "path"], env=env)
    config_show = runner.invoke(app, ["config", "show"], env=env)
    doctor = runner.invoke(app, ["doctor", "--no-network"], env=env)

    assert providers.exit_code == 0 and "mock" in providers.output
    assert models.exit_code == 0 and "mock-default" in models.output
    assert tools.exit_code == 0 and "read_file" in tools.output
    assert workflows.exit_code == 0 and "* balanced" in workflows.output
    assert "plan" in workflows.output and "guarded" in workflows.output
    assert config_path.exit_code == 0 and str(tmp_path / "config") in config_path.output
    assert config_show.exit_code == 0 and '"default_provider": "mock"' in config_show.output
    assert doctor.exit_code == 0 and "[OK] database" in doctor.output


def test_run_uses_selected_workflow_and_rejects_unknown_name() -> None:
    selected = runner.invoke(
        app,
        ["run", "--no-save", "--output", "json", "--workflow", "plan", "plan this"],
    )
    missing = runner.invoke(
        app,
        ["run", "--no-save", "--workflow", "missing", "hello"],
    )

    assert selected.exit_code == 0, selected.output
    workflow = json.loads(selected.output)["workflow"]
    assert workflow["id"] == "plan"
    assert workflow["mode"] == "plan"
    assert "write_file" not in workflow["visible_tools"]
    assert missing.exit_code == 1
    assert "unknown workflow" in missing.output


def test_skills_list_show_and_explicit_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    skill = tmp_path / ".agents" / "skills" / "review" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        "---\nname: review\ndescription: Review a target\n---\nReview $ARGUMENTS",
        encoding="utf-8",
    )
    env = {
        "YFH_CONFIG_DIR": str(tmp_path / "config"),
        "YFH_DATA_DIR": str(tmp_path / "data"),
    }

    listed = runner.invoke(app, ["skills", "list"], env=env)
    shown = runner.invoke(app, ["skills", "show", "review"], env=env)
    executed = runner.invoke(
        app,
        ["run", "--no-save", "--output", "json", "--skill", "review", "src/app.py"],
        env=env,
    )

    assert listed.exit_code == 0 and "codex:review" in listed.output
    assert shown.exit_code == 0 and "Review" in shown.output
    assert executed.exit_code == 0, executed.output
    payload = json.loads(executed.output)
    assert payload["skill"]["id"] == "codex:review"
    assert any(item["kind"] == "skill" for item in payload["context"]["sources"])


def test_run_reports_local_image_without_remote_upload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    image = tmp_path / "screen.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\nimage")

    result = runner.invoke(
        app,
        ["run", "--no-save", "--output", "json", "--image", str(image), "inspect"],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["attachments"] == [
        {
            "name": "screen.png",
            "mime_type": "image/png",
            "size_bytes": len(b"\x89PNG\r\n\x1a\nimage"),
            "transfer": "local_only",
        }
    ]


def test_mcp_list_discovers_only_explicitly_enabled_tool(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".yfh"
    config_dir.mkdir()
    server = Path(__file__).parents[1] / "fixtures" / "mcp_stdio_server.py"
    command = json.dumps([sys.executable, str(server)])
    (config_dir / "config.toml").write_text(
        f'[mcp_servers.fixture]\ncommand = {command}\nenabled = true\nenabled_tools = ["echo"]\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["mcp", "list"])

    assert result.exit_code == 0, result.output
    assert result.output.strip() == "mcp__fixture__echo"


def test_module_entrypoint_overrides_legacy_stdio_encoding(tmp_path: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONIOENCODING": "cp1252",
            "YFH_CONFIG_DIR": str(tmp_path / "config"),
            "YFH_DATA_DIR": str(tmp_path / "data"),
        }
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "yfharness",
            "eval",
            "--output",
            str(tmp_path / "report"),
        ],
        env=environment,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr.decode("utf-8", errors="replace")
    assert "通过率: 100.0%" in completed.stdout.decode("utf-8")
