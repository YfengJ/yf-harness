"""Read-only diagnostics shared by CLI and the future TUI."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel

from yfharness.config.models import AppConfig
from yfharness.config.paths import config_dir, data_dir, database_file
from yfharness.core.models import HealthStatus
from yfharness.providers.registry import provider_from_config
from yfharness.storage.database import Database
from yfharness.storage.migrations import SCHEMA_VERSION

try:
    import textual
except ImportError:  # pragma: no cover - package dependency normally guarantees this
    textual = None  # type: ignore[assignment]


class DoctorCheck(BaseModel):
    name: str
    status: HealthStatus
    message: str


async def run_doctor(config: AppConfig, *, check_network: bool = True) -> list[DoctorCheck]:
    database = Database(database_file())
    try:
        await database.initialize()
        current_schema = await database.schema_version()
        database_check = DoctorCheck(
            name="database",
            status=HealthStatus.OK if current_schema == SCHEMA_VERSION else HealthStatus.ERROR,
            message=f"schema {current_schema}/{SCHEMA_VERSION}: {database.path}",
        )
    except (OSError, RuntimeError) as exc:
        database_check = DoctorCheck(name="database", status=HealthStatus.ERROR, message=str(exc))
    checks = [
        DoctorCheck(
            name="python",
            status=HealthStatus.OK if sys.version_info >= (3, 12) else HealthStatus.ERROR,
            message=sys.version.split()[0],
        ),
        _directory_check("config_dir", config_dir()),
        _directory_check("data_dir", data_dir()),
        database_check,
        DoctorCheck(
            name="workspace",
            status=HealthStatus.OK if os.access(config.workspace, os.R_OK) else HealthStatus.ERROR,
            message=str(config.workspace),
        ),
        DoctorCheck(
            name="git",
            status=HealthStatus.OK if shutil.which("git") else HealthStatus.WARNING,
            message=shutil.which("git") or "未找到 git",
        ),
        DoctorCheck(
            name="shell",
            status=HealthStatus.OK
            if shutil.which("sh") or os.name == "nt"
            else HealthStatus.WARNING,
            message=shutil.which("sh")
            or ("Windows subprocess" if os.name == "nt" else "未找到 sh"),
        ),
        DoctorCheck(
            name="textual",
            status=HealthStatus.OK if textual is not None else HealthStatus.ERROR,
            message=(
                getattr(textual, "__version__", "已安装") if textual is not None else "未安装"
            ),
        ),
    ]
    for name, settings in config.providers.items():
        provider = provider_from_config(config, name)
        problems = provider.validate_config()
        checks.append(
            DoctorCheck(
                name=f"provider:{name}:config",
                status=HealthStatus.ERROR if problems else HealthStatus.OK,
                message="; ".join(problems) if problems else "配置完整",
            )
        )
        if check_network and not problems:
            health = await provider.health_check()
            checks.append(
                DoctorCheck(
                    name=f"provider:{name}:health",
                    status=health.status,
                    message=health.message,
                )
            )
        else:
            checks.append(
                DoctorCheck(
                    name=f"provider:{name}:health",
                    status=HealthStatus.SKIPPED,
                    message="网络检查已跳过" if not check_network else "配置不完整，跳过健康检查",
                )
            )
        if settings.api_key_env:
            key_present = bool(os.environ.get(settings.api_key_env))
            checks.append(
                DoctorCheck(
                    name=f"provider:{name}:api_key",
                    status=HealthStatus.OK if key_present else HealthStatus.WARNING,
                    message=f"环境变量 {settings.api_key_env} "
                    + ("已设置" if key_present else "未设置"),
                )
            )
    return checks


def _directory_check(name: str, path: Path) -> DoctorCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        writable = os.access(path, os.W_OK)
    except OSError as exc:
        return DoctorCheck(name=name, status=HealthStatus.ERROR, message=str(exc))
    return DoctorCheck(
        name=name,
        status=HealthStatus.OK if writable else HealthStatus.ERROR,
        message=str(path),
    )
