"""Discover scoped project guidance without coupling to one coding assistant."""

from __future__ import annotations

import fnmatch
import re
from collections.abc import Iterable
from pathlib import Path

from pydantic import Field

from yfharness.config.paths import config_dir
from yfharness.core.models import DomainModel
from yfharness.tools.security import truncate_output


class InstructionDocument(DomainModel):
    """A single, explainable instruction source in effective priority order."""

    source: str
    label: str
    path: str
    content: str
    priority: int = Field(ge=0)
    scope: str = "workspace"


class InstructionResolver:
    """Resolve YF-Harness, Codex, Claude Code, and Cursor project guidance."""

    def __init__(
        self,
        workspace: Path,
        *,
        read_limit: int = 200_000,
        global_config_dir: Path | None = None,
    ) -> None:
        self.workspace = workspace.resolve()
        self.read_limit = read_limit
        self.global_config_dir = (global_config_dir or config_dir()).resolve()

    def discover(self, relevant_paths: Iterable[str] = ()) -> list[InstructionDocument]:
        directories = self._scoped_directories(relevant_paths)
        documents: list[InstructionDocument] = []
        self._append_file(
            documents,
            self.global_config_dir / "instructions.md",
            source="yfh-global",
            label="全局 YF-Harness 指令",
            priority=10,
            scope="global",
        )
        self._append_file(
            documents,
            self.workspace / "YF_HARNESS.md",
            source="yfh-project",
            label="项目 YF_HARNESS.md",
            priority=20,
        )
        for depth, directory in enumerate(directories):
            relative_scope = self._relative_scope(directory)
            self._append_file(
                documents,
                directory / "CLAUDE.md",
                source="claude",
                label=f"Claude 项目记忆 · {relative_scope}",
                priority=30 + depth,
                scope=relative_scope,
            )
        documents.extend(self._cursor_rules(relevant_paths))
        for depth, directory in enumerate(directories):
            override = directory / "AGENTS.override.md"
            agents = override if override.is_file() else directory / "AGENTS.md"
            self._append_file(
                documents,
                agents,
                source="codex",
                label=f"Codex 项目指令 · {self._relative_scope(directory)}",
                priority=50 + depth,
                scope=self._relative_scope(directory),
            )
        self._append_file(
            documents,
            self.workspace / ".yfh" / "instructions.md",
            source="yfh-local",
            label="项目本地覆盖 · .yfh/instructions.md",
            priority=100,
            scope="workspace",
        )
        return sorted(documents, key=lambda item: (item.priority, item.path))[:32]

    def _scoped_directories(self, relevant_paths: Iterable[str]) -> list[Path]:
        directories = {self.workspace}
        for relative in relevant_paths:
            candidate = (self.workspace / relative).resolve(strict=False)
            try:
                candidate.relative_to(self.workspace)
            except ValueError:
                continue
            current = candidate if candidate.is_dir() else candidate.parent
            while current != self.workspace:
                directories.add(current)
                current = current.parent
        return sorted(directories, key=lambda item: (len(item.parts), str(item)))

    def _cursor_rules(self, relevant_paths: Iterable[str]) -> list[InstructionDocument]:
        rules_dir = self.workspace / ".cursor" / "rules"
        if not rules_dir.is_dir():
            return []
        relevant = list(relevant_paths)
        documents: list[InstructionDocument] = []
        for path in sorted(rules_dir.glob("*.mdc")):
            content = self._read_text(path)
            metadata, body = _split_frontmatter(content)
            always = metadata.get("alwaysApply", "").lower() == "true"
            globs = _split_globs(metadata.get("globs", ""))
            matches = any(
                fnmatch.fnmatch(relative, pattern) for relative in relevant for pattern in globs
            )
            if not always and globs and not matches:
                continue
            description = metadata.get("description") or path.stem
            documents.append(
                InstructionDocument(
                    source="cursor",
                    label=f"Cursor 规则 · {description}",
                    path=self._display_path(path),
                    content=body.strip(),
                    priority=40,
                    scope=", ".join(globs) if globs else "workspace",
                )
            )
        return documents

    def _append_file(
        self,
        documents: list[InstructionDocument],
        path: Path,
        *,
        source: str,
        label: str,
        priority: int,
        scope: str = "workspace",
    ) -> None:
        if not path.is_file():
            return
        documents.append(
            InstructionDocument(
                source=source,
                label=label,
                path=self._display_path(path),
                content=self._read_text(path),
                priority=priority,
                scope=scope,
            )
        )

    def _read_text(self, path: Path) -> str:
        raw = path.read_bytes()[: self.read_limit]
        if b"\x00" in raw[:8192]:
            return "<疑似二进制文件，未读取>"
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return "<非 UTF-8 文件，未读取>"
        return truncate_output(text, self.read_limit)[0]

    def _display_path(self, path: Path) -> str:
        try:
            return path.resolve().relative_to(self.workspace).as_posix()
        except ValueError:
            return str(path.resolve())

    def _relative_scope(self, directory: Path) -> str:
        relative = directory.relative_to(self.workspace).as_posix()
        return "workspace" if relative == "." else relative


def _split_frontmatter(content: str) -> tuple[dict[str, str], str]:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    if not content.startswith("---\n"):
        return {}, content
    end = content.find("\n---\n", 4)
    if end < 0:
        return {}, content
    metadata: dict[str, str] = {}
    for line in content[4:end].splitlines():
        key, separator, value = line.partition(":")
        if separator:
            metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, content[end + 5 :]


def _split_globs(value: str) -> list[str]:
    return [item.strip().strip("'\"") for item in re.split(r"[,\s]+", value) if item.strip()]
