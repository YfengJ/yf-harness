"""Small local-only codebase index for explainable context selection."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from yfharness.core.models import DomainModel
from yfharness.tools.security import WorkspaceGuard

_SKIP_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
}
_SKIP_SUFFIXES = {
    ".7z",
    ".dmg",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".lock",
    ".pdf",
    ".png",
    ".pyc",
    ".tar",
    ".webp",
    ".whl",
    ".zip",
}


class IndexedPath(DomainModel):
    path: str
    score: float
    reasons: list[str]


class ProjectIndex:
    """Rank text files with transparent lexical and Git-aware signals."""

    def __init__(
        self,
        workspace: Path,
        *,
        max_files: int = 2_000,
        sample_bytes: int = 24_000,
    ) -> None:
        self.guard = WorkspaceGuard(workspace)
        self.max_files = max_files
        self.sample_bytes = sample_bytes
        self._paths: list[str] | None = None
        self._changed: set[str] | None = None

    def select(self, query: str, *, limit: int = 5) -> list[IndexedPath]:
        terms = _query_terms(query)
        if not terms:
            return []
        ranked: list[IndexedPath] = []
        changed = self._changed_paths()
        for relative in self.paths():
            path_score, reasons = _path_score(relative, terms)
            content_score = 0.0
            path = self.guard.resolve(relative, must_exist=True)
            if path.stat().st_size <= 1_000_000:
                text = _sample_text(path, self.sample_bytes)
                if text is not None:
                    lowered = text.lower()
                    hits = sum(min(lowered.count(term), 4) for term in terms)
                    if hits:
                        content_score = min(float(hits), 8.0)
                        reasons.append(f"内容命中 {hits} 次")
            score = path_score + content_score
            if relative in changed and score > 0:
                score += 2.5
                reasons.append("Git 工作区已修改")
            if score > 0:
                ranked.append(IndexedPath(path=relative, score=score, reasons=reasons))
        ranked.sort(key=lambda item: (-item.score, item.path))
        return ranked[:limit]

    def paths(self) -> list[str]:
        if self._paths is None:
            self._paths = self._git_paths() or self._filesystem_paths()
        return list(self._paths)

    def _git_paths(self) -> list[str]:
        try:
            completed = subprocess.run(
                ["git", "ls-files", "-co", "--exclude-standard", "-z"],
                cwd=self.guard.root,
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return []
        if completed.returncode != 0:
            return []
        values = completed.stdout.decode("utf-8", errors="replace").split("\x00")
        return [value for value in values if value and self._eligible(value)][: self.max_files]

    def _filesystem_paths(self) -> list[str]:
        paths: list[str] = []
        for path in self.guard.root.rglob("*"):
            if len(paths) >= self.max_files:
                break
            if not path.is_file() or path.is_symlink():
                continue
            relative = self.guard.relative(path)
            if self._eligible(relative):
                paths.append(relative)
        return sorted(paths)

    def _changed_paths(self) -> set[str]:
        if self._changed is not None:
            return self._changed
        try:
            completed = subprocess.run(
                ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
                cwd=self.guard.root,
                capture_output=True,
                timeout=3,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            self._changed = set()
            return self._changed
        if completed.returncode != 0:
            self._changed = set()
            return self._changed
        entries = completed.stdout.decode("utf-8", errors="replace").split("\x00")
        self._changed = {
            entry[3:].split(" -> ")[-1] for entry in entries if len(entry) > 3 and entry[3:]
        }
        return self._changed

    def _eligible(self, relative: str) -> bool:
        path = Path(relative)
        return not any(part in _SKIP_PARTS for part in path.parts) and (
            path.suffix.lower() not in _SKIP_SUFFIXES
        )


def _query_terms(query: str) -> list[str]:
    terms = re.findall(r"[A-Za-z_][A-Za-z0-9_-]{2,}", query.lower())
    ignored = {
        "add",
        "and",
        "check",
        "code",
        "file",
        "fix",
        "please",
        "project",
        "the",
        "this",
        "update",
    }
    return list(dict.fromkeys(term for term in terms if term not in ignored))[:12]


def _path_score(relative: str, terms: list[str]) -> tuple[float, list[str]]:
    lowered = relative.lower()
    name = Path(relative).name.lower()
    score = 0.0
    reasons: list[str] = []
    for term in terms:
        if term in name:
            score += 7.0
            reasons.append(f"文件名匹配 {term}")
        elif term in lowered:
            score += 3.5
            reasons.append(f"路径匹配 {term}")
    return score, reasons


def _sample_text(path: Path, limit: int) -> str | None:
    raw = path.read_bytes()[:limit]
    if b"\x00" in raw[:8192]:
        return None
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
