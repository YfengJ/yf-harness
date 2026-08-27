from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

from yfharness.cli import app

runner = CliRunner()


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
    config_path = runner.invoke(app, ["config", "path"], env=env)
    config_show = runner.invoke(app, ["config", "show"], env=env)
    doctor = runner.invoke(app, ["doctor", "--no-network"], env=env)

    assert providers.exit_code == 0 and "mock" in providers.output
    assert models.exit_code == 0 and "mock-default" in models.output
    assert tools.exit_code == 0 and "read_file" in tools.output
    assert config_path.exit_code == 0 and str(tmp_path / "config") in config_path.output
    assert config_show.exit_code == 0 and '"default_provider": "mock"' in config_show.output
    assert doctor.exit_code == 0 and "[OK] database" in doctor.output


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
