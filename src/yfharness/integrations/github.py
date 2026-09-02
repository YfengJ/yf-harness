"""GitHub CLI adapter scoped to the current workspace origin."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

from yfharness.core.exceptions import HarnessError
from yfharness.tools.security import github_cli_environment, resolve_executable, truncate_output

_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH = re.compile(r"^(?!/)(?!.*\.\.)(?!.*[~^:?*\[\\])[A-Za-z0-9._/-]+$")


class GitHubError(HarnessError):
    """A GitHub operation failed without exposing credentials."""


class GitHubService:
    def __init__(self, workspace: Path, *, output_limit: int = 100_000) -> None:
        self.workspace = workspace.resolve(strict=True)
        self.output_limit = output_limit
        self.repository = self._discover_repository()

    def snapshot(self) -> dict[str, Any]:
        account = self._gh(["api", "user", "--jq", ".login"]).strip()
        repository = self._json(
            self._gh(
                [
                    "repo",
                    "view",
                    self.repository,
                    "--json",
                    "nameWithOwner,isPrivate,visibility,url,defaultBranchRef",
                ]
            )
        )
        branch = self.current_branch()
        status = self._git(["status", "--porcelain=v2", "--branch"])
        ahead, behind = _ahead_behind(status)
        return {
            "account": account,
            "repository": repository.get("nameWithOwner", self.repository),
            "private": repository.get("isPrivate") is True,
            "visibility": repository.get("visibility", "UNKNOWN"),
            "url": repository.get("url", ""),
            "default_branch": (
                repository.get("defaultBranchRef", {}).get("name", "")
                if isinstance(repository.get("defaultBranchRef"), dict)
                else ""
            ),
            "branch": branch,
            "dirty": any(line and not line.startswith("#") for line in status.splitlines()),
            "ahead": ahead,
            "behind": behind,
        }

    def pull_requests(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._json_list(
            self._gh(
                [
                    "pr",
                    "list",
                    "--repo",
                    self.repository,
                    "--limit",
                    str(limit),
                    "--json",
                    "number,title,state,isDraft,headRefName,baseRefName,updatedAt,url",
                ]
            )
        )

    def issues(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._json_list(
            self._gh(
                [
                    "issue",
                    "list",
                    "--repo",
                    self.repository,
                    "--limit",
                    str(limit),
                    "--json",
                    "number,title,state,updatedAt,url,labels",
                ]
            )
        )

    def workflow_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._json_list(
            self._gh(
                [
                    "run",
                    "list",
                    "--repo",
                    self.repository,
                    "--limit",
                    str(limit),
                    "--json",
                    "databaseId,name,displayTitle,status,conclusion,headBranch,updatedAt,url",
                ]
            )
        )

    def fetch(self) -> str:
        return self._git(["fetch", "--prune", "origin"], timeout=120)

    def pull_ff(self) -> str:
        if self.snapshot()["dirty"]:
            raise GitHubError("工作区有未提交变更，拒绝自动 pull")
        return self._git(["pull", "--ff-only", "origin", self.current_branch()], timeout=120)

    def push(self) -> str:
        branch = self.current_branch()
        _validate_branch(branch)
        return self._git(["push", "origin", f"HEAD:refs/heads/{branch}"], timeout=120)

    def create_branch(self, name: str) -> str:
        _validate_branch(name)
        if self.snapshot()["dirty"]:
            raise GitHubError("工作区有未提交变更，拒绝切换分支")
        return self._git(["switch", "-c", name])

    def create_pull_request(
        self,
        *,
        title: str,
        body: str,
        base: str,
        draft: bool = False,
    ) -> str:
        arguments = [
            "pr",
            "create",
            "--repo",
            self.repository,
            "--title",
            title,
            "--body",
            body,
            "--base",
            base,
            "--head",
            self.current_branch(),
        ]
        if draft:
            arguments.append("--draft")
        return self._gh(arguments, timeout=120)

    def create_issue(self, *, title: str, body: str) -> str:
        return self._gh(
            [
                "issue",
                "create",
                "--repo",
                self.repository,
                "--title",
                title,
                "--body",
                body,
            ],
            timeout=120,
        )

    def comment(self, *, number: int, body: str) -> str:
        return self._gh(
            [
                "issue",
                "comment",
                str(number),
                "--repo",
                self.repository,
                "--body",
                body,
            ],
            timeout=120,
        )

    def rerun_failed(self, run_id: int) -> str:
        return self._gh(
            ["run", "rerun", str(run_id), "--failed", "--repo", self.repository],
            timeout=120,
        )

    def current_branch(self) -> str:
        branch = self._git(["branch", "--show-current"]).strip()
        if not branch:
            raise GitHubError("当前仓库处于 detached HEAD，无法执行远程写入")
        return branch

    def _discover_repository(self) -> str:
        remote = self._git(["remote", "get-url", "origin"]).strip()
        repository = _repository_from_remote(remote)
        if repository is None:
            raise GitHubError("当前 origin 不是受支持的 github.com 仓库")
        return repository

    def _git(self, arguments: list[str], *, timeout: float = 30) -> str:
        environment = github_cli_environment()
        environment["HOME"] = str(Path.home())
        environment["GIT_TERMINAL_PROMPT"] = "0"
        return self._run([resolve_executable("git"), *arguments], timeout, environment)

    def _gh(self, arguments: list[str], *, timeout: float = 30) -> str:
        return self._run([resolve_executable("gh"), *arguments], timeout, github_cli_environment())

    def _run(self, command: list[str], timeout: float, environment: dict[str, str]) -> str:
        try:
            completed = subprocess.run(
                command,
                cwd=self.workspace,
                env=environment,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise GitHubError(f"GitHub 命令无法完成: {exc}") from exc
        stdout, _ = truncate_output(completed.stdout, self.output_limit)
        stderr, _ = truncate_output(completed.stderr, 4_000)
        if completed.returncode != 0:
            raise GitHubError(stderr.strip() or f"GitHub 命令退出码 {completed.returncode}")
        return stdout.strip()

    @staticmethod
    def _json(value: str) -> dict[str, Any]:
        payload = json.loads(value)
        if not isinstance(payload, dict):
            raise GitHubError("GitHub 返回了无效对象")
        return payload

    @staticmethod
    def _json_list(value: str) -> list[dict[str, Any]]:
        payload = json.loads(value)
        if not isinstance(payload, list):
            raise GitHubError("GitHub 返回了无效列表")
        return [item for item in payload if isinstance(item, dict)]


def _repository_from_remote(value: str) -> str | None:
    remote = value.strip().removesuffix(".git")
    for prefix in ("https://github.com/", "ssh://git@github.com/"):
        if remote.startswith(prefix):
            candidate = remote[len(prefix) :]
            return candidate if _REPOSITORY.fullmatch(candidate) else None
    prefix = "git@github.com:"
    if remote.startswith(prefix):
        candidate = remote[len(prefix) :]
        return candidate if _REPOSITORY.fullmatch(candidate) else None
    return None


def _validate_branch(value: str) -> None:
    if not _BRANCH.fullmatch(value) or value.endswith(("/", ".")) or value.startswith("-"):
        raise ValueError("分支名称无效")


def _ahead_behind(status: str) -> tuple[int, int]:
    for line in status.splitlines():
        if line.startswith("# branch.ab "):
            parts = line.split()
            if len(parts) == 4:
                return int(parts[2].lstrip("+")), abs(int(parts[3]))
    return 0, 0
