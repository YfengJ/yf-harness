"""Workspace confinement and secret-safe subprocess environments."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from yfharness.core.exceptions import PolicyDeniedError

_SAFE_ENVIRONMENT_KEYS = {
    "PATH",
    "PATHEXT",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "TMP",
    "TEMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "TERM",
    "COLORTERM",
    "PYTHONPATH",
    "VIRTUAL_ENV",
}
_SECRET_MARKERS = ("KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH", "CREDENTIAL")


class WorkspaceGuard:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("workspace root must be a directory")

    def resolve(self, path: str | Path, *, must_exist: bool = False) -> Path:
        requested = Path(path)
        candidate = requested if requested.is_absolute() else self.root / requested
        try:
            resolved = candidate.resolve(strict=must_exist)
        except (FileNotFoundError, RuntimeError) as exc:
            raise PolicyDeniedError(f"路径不存在或无法安全解析: {path}") from exc
        if not resolved.is_relative_to(self.root):
            raise PolicyDeniedError(f"路径超出 workspace: {path}")
        if not must_exist:
            self._verify_existing_ancestors(candidate)
        return resolved

    def relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix() or "."

    def _verify_existing_ancestors(self, candidate: Path) -> None:
        current = candidate
        while not current.exists() and current != current.parent:
            current = current.parent
        try:
            resolved_parent = current.resolve(strict=True)
        except (FileNotFoundError, RuntimeError) as exc:
            raise PolicyDeniedError(f"无法验证路径父目录: {candidate}") from exc
        if not resolved_parent.is_relative_to(self.root):
            raise PolicyDeniedError(f"路径通过符号链接逃逸 workspace: {candidate}")


def sanitized_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    environment = source if source is not None else dict(os.environ)
    return {
        key: value
        for key, value in environment.items()
        if key in _SAFE_ENVIRONMENT_KEYS
        and not any(marker in key.upper() for marker in _SECRET_MARKERS)
    }


def truncate_output(value: str, limit: int) -> tuple[str, bool]:
    if len(value) <= limit:
        return value, False
    omitted = len(value) - limit
    return f"{value[:limit]}\n... <truncated {omitted} characters>", True


def resolve_executable(value: str) -> str:
    """Resolve GUI-launched helper tools without executing a login shell."""

    requested = Path(value).expanduser()
    if requested.parent != Path("."):
        if requested.is_file() and os.access(requested, os.X_OK):
            return str(requested.resolve())
        raise FileNotFoundError(f"找不到可执行文件: {value}")
    if resolved := shutil.which(value):
        return resolved
    for root in (Path.home() / ".local/bin", Path("/opt/homebrew/bin"), Path("/usr/local/bin")):
        candidate = root / value
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise FileNotFoundError(f"找不到可执行文件: {value}")


def github_cli_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Allow gh to find its own config while keeping unrelated secrets out."""

    original = source if source is not None else dict(os.environ)
    environment = sanitized_environment(original)
    environment["HOME"] = str(Path.home())
    configured = original.get("GH_CONFIG_DIR")
    default = Path.home() / ".config" / "gh"
    if configured:
        environment["GH_CONFIG_DIR"] = configured
    elif default.is_dir():
        environment["GH_CONFIG_DIR"] = str(default)
    return environment
