from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.skill_install import create_project_skill, install_local_skill
from yfharness.core.skills import SkillCatalog


def test_create_project_skill_is_immediately_invocable(tmp_path: Path) -> None:
    result = create_project_skill(
        tmp_path,
        name="focused-review",
        description="Review a target",
        instructions="Review $ARGUMENTS",
        allowed_tools=["read_file", "git_diff"],
    )

    assert result.id == "codex:focused-review"
    invocation = SkillCatalog(tmp_path).invoke(result.id, "src/app.py")
    assert invocation.instructions == "Review src/app.py"
    assert invocation.summary.requested_tools == ["read_file", "git_diff"]


def test_import_copies_resources_but_never_executes_scripts(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: imported\ndescription: Imported\n---\nUse resources",
        encoding="utf-8",
    )
    script = source / "scripts" / "run.sh"
    script.parent.mkdir()
    script.write_text("touch should-not-exist", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    result = install_local_skill(workspace, source)

    assert "附带资源不会自动执行或加载" in result.warnings
    assert (workspace / ".agents/skills/imported/scripts/run.sh").is_file()
    assert not (workspace / "should-not-exist").exists()


def test_import_rejects_symlink_and_existing_destination(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "SKILL.md").write_text(
        "---\nname: safe\ndescription: Safe\n---\nInspect",
        encoding="utf-8",
    )
    outside = tmp_path / "outside"
    outside.write_text("secret", encoding="utf-8")
    link = source / "assets" / "escape"
    link.parent.mkdir()
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    workspace = tmp_path / "workspace"
    workspace.mkdir()

    with pytest.raises(ValueError, match="符号链接"):
        install_local_skill(workspace, source)

    link.unlink()
    install_local_skill(workspace, source)
    with pytest.raises(FileExistsError, match="已存在"):
        install_local_skill(workspace, source)


@pytest.mark.parametrize(
    "name",
    ["../escape", "contains spaces", "", "slash/name"],
)
def test_create_rejects_unsafe_names(tmp_path: Path, name: str) -> None:
    with pytest.raises(ValueError, match="名称"):
        create_project_skill(
            tmp_path,
            name=name,
            description="unsafe",
            instructions="do work",
        )
