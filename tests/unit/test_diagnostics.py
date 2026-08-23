from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.config.models import AppConfig, ProviderSettings
from yfharness.core.models import HealthStatus, ModelConfig, Usage
from yfharness.diagnostics import _directory_check, run_doctor
from yfharness.observability.usage import calculate_cost


@pytest.mark.asyncio
async def test_doctor_checks_local_runtime_and_mock_health(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))

    checks = await run_doctor(AppConfig(workspace=tmp_path))
    by_name = {check.name: check for check in checks}

    assert by_name["python"].status is HealthStatus.OK
    assert by_name["database"].status is HealthStatus.OK
    assert by_name["workspace"].status is HealthStatus.OK
    assert by_name["textual"].status is HealthStatus.OK
    assert by_name["provider:mock:config"].status is HealthStatus.OK
    assert by_name["provider:mock:health"].status is HealthStatus.OK


@pytest.mark.asyncio
async def test_doctor_reports_missing_remote_key_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("YFH_CONFIG_DIR", str(tmp_path / "config"))
    monkeypatch.setenv("YFH_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("REMOTE_API_KEY", raising=False)
    config = AppConfig(
        workspace=tmp_path,
        default_provider="remote",
        default_model="remote-model",
        providers={
            "remote": ProviderSettings(
                type="openai_compatible",
                base_url="https://example.test/v1",
                api_key_env="REMOTE_API_KEY",
            )
        },
        models={
            "remote-model": ModelConfig(
                id="remote-model",
                provider="remote",
                model="remote-model",
            )
        },
    )

    checks = await run_doctor(config, check_network=False)
    by_name = {check.name: check for check in checks}

    assert by_name["provider:remote:health"].status is HealthStatus.SKIPPED
    assert by_name["provider:remote:api_key"].status is HealthStatus.WARNING
    assert "未设置" in by_name["provider:remote:api_key"].message


def test_directory_check_reports_path_collision(tmp_path: Path) -> None:
    collision = tmp_path / "not-a-directory"
    collision.write_text("occupied", encoding="utf-8")

    check = _directory_check("collision", collision)

    assert check.status is HealthStatus.ERROR
    assert check.message


def test_calculate_cost_uses_configured_per_million_prices() -> None:
    usage = Usage(input_tokens=250_000, output_tokens=100_000)
    unpriced = ModelConfig(id="free", provider="mock", model="free")
    priced = ModelConfig(
        id="priced",
        provider="mock",
        model="priced",
        input_price=2.0,
        output_price=8.0,
    )

    assert calculate_cost(usage, unpriced) is None
    assert calculate_cost(usage, priced) == pytest.approx(1.3)
