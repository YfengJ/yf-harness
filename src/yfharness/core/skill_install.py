"""Safe creation and installation of project-scoped skills."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from pydantic import Field

from yfharness.core.models import DomainModel
from yfharness.core.skills import SkillCatalog, SkillSummary
from yfharness.tools.security import github_cli_environment, resolve_executable

_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")
_REPOSITORY_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_TOOL_PATTERN = re.compile(r"^[A-Za-z0-9_.?*-]+$")
_MAX_FILES = 200
_MAX_FILE_BYTES = 1_000_000
_MAX_TOTAL_BYTES = 5_000_000


class SkillInstallResult(DomainModel):
    id: str
    name: str
    path: str
    files: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def create_project_skill(
    workspace: Path,
    *,
    name: str,
    description: str,
    instructions: str,
    allowed_tools: list[str] | None = None,
) -> SkillInstallResult:
    normalized = _validate_name(name)
    body = instructions.strip()
    if not body:
        raise ValueError("Skill 指令不能为空")
    if len(body.encode("utf-8")) > 128_000:
        raise ValueError("Skill 指令不能超过 128 KB")
    tools = allowed_tools or []
    if any(not _TOOL_PATTERN.fullmatch(item) for item in tools):
        raise ValueError("工具名称包含无效字符")
    safe_description = " ".join(description.split()).strip()[:500] or normalized
    frontmatter = ["---", f"name: {normalized}", f"description: {safe_description}"]
    if tools:
        frontmatter.append("allowed-tools: " + ", ".join(tools))
    frontmatter.extend(["user-invocable: true", "---", body, ""])
    with tempfile.TemporaryDirectory(prefix="yfh-skill-create-") as temporary:
        source = Path(temporary) / normalized
        source.mkdir()
        (source / "SKILL.md").write_text("\n".join(frontmatter), encoding="utf-8")
        return install_local_skill(workspace, source)


def install_local_skill(workspace: Path, source: Path) -> SkillInstallResult:
    requested = source.expanduser()
    if requested.is_symlink():
        raise ValueError("请选择包含 SKILL.md 的普通文件夹；不允许符号链接")
    source = requested.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("请选择包含 SKILL.md 的普通文件夹")
    files = _validate_tree(source)
    summary = _validate_catalog(source)
    destination_root = workspace.resolve(strict=True) / ".agents" / "skills"
    destination = destination_root / summary.name
    if destination.exists():
        raise FileExistsError(f"Skill 已存在：{summary.name}；请先重命名或移除旧版本")
    destination_root.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{summary.name}.", dir=destination_root))
    try:
        for relative in files:
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / relative, target, follow_symlinks=False)
        temporary.replace(destination)
    except BaseException:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    installed = SkillCatalog(workspace).resolve(f"codex:{summary.name}")
    return SkillInstallResult(
        id=installed.id,
        name=installed.name,
        path=installed.path,
        files=[path.as_posix() for path in files],
        warnings=installed.warnings,
    )


def install_github_skill(
    workspace: Path,
    *,
    repository: str,
    skill_path: str,
    ref: str = "",
) -> SkillInstallResult:
    repo = _normalize_repository(repository)
    relative = Path(skill_path)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ValueError("GitHub Skill 路径必须是仓库内的相对目录")
    with tempfile.TemporaryDirectory(prefix="yfh-github-skill-") as temporary:
        checkout = Path(temporary) / "repository"
        command = [
            resolve_executable("gh"),
            "repo",
            "clone",
            repo,
            str(checkout),
            "--",
            "--depth=1",
            "--filter=blob:none",
        ]
        if ref.strip():
            command.extend(["--branch", ref.strip()])
        completed = subprocess.run(
            command,
            cwd=temporary,
            env=github_cli_environment(),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if completed.returncode != 0:
            detail = completed.stderr.strip()[-1_000:]
            raise RuntimeError(f"GitHub Skill 下载失败：{detail or 'gh 返回非零状态'}")
        source = (checkout / relative).resolve(strict=True)
        if not source.is_relative_to(checkout.resolve(strict=True)):
            raise ValueError("GitHub Skill 路径逃逸仓库")
        return install_local_skill(workspace, source)


def _validate_tree(source: Path) -> list[Path]:
    files: list[Path] = []
    total = 0
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Skill 不允许符号链接：{path.relative_to(source)}")
        if not path.is_file():
            continue
        relative = path.relative_to(source)
        if ".git" in relative.parts:
            continue
        size = path.stat().st_size
        if size > _MAX_FILE_BYTES:
            raise ValueError(f"Skill 文件超过 1 MB：{relative}")
        total += size
        if total > _MAX_TOTAL_BYTES:
            raise ValueError("Skill 总大小不能超过 5 MB")
        files.append(relative)
        if len(files) > _MAX_FILES:
            raise ValueError("Skill 文件数不能超过 200")
    if Path("SKILL.md") not in files:
        raise ValueError("所选目录缺少 SKILL.md")
    return files


def _validate_catalog(source: Path) -> SkillSummary:
    with tempfile.TemporaryDirectory(prefix="yfh-skill-validate-") as temporary:
        root = Path(temporary)
        staged = root / ".agents" / "skills" / source.name
        staged.parent.mkdir(parents=True)
        shutil.copytree(source, staged, symlinks=True)
        items = SkillCatalog(root).discover()
        if len(items) != 1:
            raise ValueError("SKILL.md 元数据无效，或 Skill 无法安全发现")
        SkillCatalog(root).inspect(items[0].id)
        return items[0]


def _validate_name(value: str) -> str:
    normalized = value.strip()
    if not _NAME_PATTERN.fullmatch(normalized):
        raise ValueError("Skill 名称只能包含字母、数字、点、下划线和连字符")
    return normalized


def _normalize_repository(value: str) -> str:
    normalized = value.strip()
    prefix = "https://github.com/"
    if normalized.startswith(prefix):
        normalized = normalized[len(prefix) :].removesuffix(".git").strip("/")
    if not _REPOSITORY_PATTERN.fullmatch(normalized):
        raise ValueError("GitHub 仓库格式应为 owner/repo")
    return normalized
