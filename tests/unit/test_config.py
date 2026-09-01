from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from yfharness.config.loader import ConfigError, load_config


def test_example_config_keeps_root_keys_at_document_scope() -> None:
    path = Path(__file__).parents[2] / "examples" / "config.example.toml"

    payload = tomllib.loads(path.read_text(encoding="utf-8"))

    assert payload["default_workflow"] == "balanced"
    assert "default_workflow" not in payload["usage"]


def test_config_precedence_and_environment_expansion(tmp_path: Path) -> None:
    user = tmp_path / "user.toml"
    project = tmp_path / "project.toml"
    user.write_text('language = "en"\ndefault_model = "custom"\n', encoding="utf-8")
    project.write_text(
        """
default_provider = "remote"

[providers.remote]
type = "openai_compatible"
base_url = "${TEST_BASE_URL}"
api_key_env = "TEST_API_KEY"

[models.custom]
id = "custom"
provider = "remote"
model = "user-model"
supports_streaming = true
""",
        encoding="utf-8",
    )

    config = load_config(
        workspace=tmp_path,
        user_path=user,
        project_path=project,
        environ={"TEST_BASE_URL": "http://localhost:9999/v1", "YFH_LANGUAGE": "zh-CN"},
        cli_overrides={"language": "zh-Hans"},
    )

    assert config.language == "zh-Hans"
    assert config.providers["remote"].base_url == "http://localhost:9999/v1"
    assert config.models["custom"].model == "user-model"


def test_missing_interpolation_variable_is_config_error(tmp_path: Path) -> None:
    project = tmp_path / "config.toml"
    project.write_text(
        '[providers.remote]\ntype="openai_compatible"\nbase_url="${MISSING_URL}"\n',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="MISSING_URL"):
        load_config(workspace=tmp_path, project_path=project, user_path=tmp_path / "none")


def test_redacted_config_never_resolves_api_key(tmp_path: Path) -> None:
    project = tmp_path / "config.toml"
    project.write_text(
        """
default_provider = "remote"
default_model = "custom"
[providers.remote]
type = "openai_compatible"
base_url = "https://example.test/v1"
api_key_env = "SECRET_KEY"
[models.custom]
id = "custom"
provider = "remote"
model = "custom"
""",
        encoding="utf-8",
    )
    config = load_config(
        workspace=tmp_path,
        project_path=project,
        user_path=tmp_path / "none",
        environ={"SECRET_KEY": "super-secret"},
    )

    assert "super-secret" not in str(config.redacted_dict())
    assert config.redacted_dict()["providers"]["remote"]["api_key_env"] == "SECRET_KEY"  # type: ignore[index]


def test_versioned_workflow_profiles_merge_and_validate_references(tmp_path: Path) -> None:
    project = tmp_path / "config.toml"
    project.write_text(
        """
default_workflow = "review-only"

[workflows.review-only]
version = 1
id = "review-only"
label = "Review only"
mode = "review"
permissions = "deny_writes"
allowed_tools = ["read_*", "git_diff", "git_status"]
denied_tools = ["git_log"]

[[workflows.review-only.hooks]]
id = "audit-reads"
event = "pre_tool_use"
tools = ["read_*"]
action = "observe"
""",
        encoding="utf-8",
    )

    config = load_config(
        workspace=tmp_path,
        project_path=project,
        user_path=tmp_path / "none",
    )

    profile = config.workflow()
    assert profile.id == "review-only"
    assert profile.exposes("read_file")
    assert not profile.exposes("git_log")
    assert "balanced" in config.workflows

    project.write_text('default_workflow = "missing"\n', encoding="utf-8")
    with pytest.raises(ConfigError, match="default_workflow"):
        load_config(
            workspace=tmp_path,
            project_path=project,
            user_path=tmp_path / "none",
        )


def test_local_usage_budgets_are_optional_and_validated(tmp_path: Path) -> None:
    project = tmp_path / "config.toml"
    project.write_text(
        """
[usage]
daily_token_budget = 100000
monthly_token_budget = 2000000
daily_cost_budget = 2.5
monthly_cost_budget = 50.0
""",
        encoding="utf-8",
    )

    config = load_config(
        workspace=tmp_path,
        project_path=project,
        user_path=tmp_path / "none",
    )

    assert config.usage.daily_token_budget == 100_000
    assert config.usage.monthly_cost_budget == 50.0

    project.write_text("[usage]\ndaily_token_budget = 0\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="daily_token_budget"):
        load_config(
            workspace=tmp_path,
            project_path=project,
            user_path=tmp_path / "none",
        )
