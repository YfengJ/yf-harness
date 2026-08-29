from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.skills import SkillCatalog, parse_skill_reference


def _write_skill(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_catalog_discovers_cross_tool_metadata_and_defers_body(tmp_path: Path) -> None:
    secret_marker = "BODY-MUST-ONLY-APPEAR-AFTER-INVOKE"
    _write_skill(
        tmp_path,
        ".agents/skills/review/SKILL.md",
        "---\r\nname: review\r\ndescription: Review changes\r\n"
        "allowed-tools: read_file, git_diff\r\n---\r\n"
        f"Review $ARGUMENTS {secret_marker}",
    )
    _write_skill(tmp_path, ".claude/commands/explain.md", "Explain $1 to $2")
    _write_skill(
        tmp_path,
        ".cursor/commands/test.md",
        "---\ndescription: Run focused tests\n---\nTest $ARGUMENTS",
    )

    catalog = SkillCatalog(tmp_path)
    items = catalog.discover()

    assert [item.id for item in items] == [
        "codex:review",
        "claude-command:explain",
        "cursor-command:test",
    ]
    assert secret_marker not in str(items)
    assert items[0].requested_tools == ["read_file", "git_diff"]
    assert "不会授予权限" in items[0].warnings[0]

    invocation = catalog.invoke("codex:review", "src/app.py")
    assert f"Review src/app.py {secret_marker}" == invocation.instructions
    assert "不能更改运行模式" in invocation.render()


def test_bare_name_requires_explicit_namespace_when_ambiguous(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        ".agents/skills/review/SKILL.md",
        "---\nname: review\ndescription: Codex review\n---\nCodex",
    )
    _write_skill(
        tmp_path,
        ".claude/skills/review/SKILL.md",
        "---\nname: review\ndescription: Claude review\n---\nClaude",
    )

    catalog = SkillCatalog(tmp_path)

    with pytest.raises(ValueError, match="多个来源"):
        catalog.resolve("review")
    assert catalog.invoke("claude:review").instructions == "Claude"
    assert all("必须使用完整" in item.warnings[-1] for item in catalog.discover())


def test_catalog_rejects_symlinks_invalid_names_and_oversized_files(tmp_path: Path) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside-skill.md"
    outside.write_text("---\nname: escaped\ndescription: no\n---\nsecret", encoding="utf-8")
    link = tmp_path / ".agents/skills/escaped/SKILL.md"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks are unavailable")
    _write_skill(
        tmp_path,
        ".agents/skills/invalid/SKILL.md",
        "---\nname: ../invalid\ndescription: no\n---\nbody",
    )
    _write_skill(
        tmp_path,
        ".agents/skills/large/SKILL.md",
        "---\nname: large\ndescription: no\n---\n" + "x" * 256,
    )

    assert SkillCatalog(tmp_path, read_limit=128).discover() == []


def test_invocation_substitutes_raw_and_positional_arguments_as_text(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        ".claude/commands/compare.md",
        "Compare $1 with $2. Raw: ${ARGUMENTS}. Literal command: `echo $1`.",
    )

    invocation = SkillCatalog(tmp_path).invoke("compare", '"alpha beta" gamma')

    assert "Compare alpha beta with gamma" in invocation.instructions
    assert 'Raw: "alpha beta" gamma' in invocation.instructions
    assert "Literal command: `echo alpha beta`" in invocation.instructions


def test_parse_skill_reference_only_accepts_leading_dollar() -> None:
    assert parse_skill_reference("please mention $codex:review") is None
    assert parse_skill_reference(" $codex:review inspect this ") == (
        "codex:review",
        "inspect this",
    )
    with pytest.raises(ValueError, match="技能名"):
        parse_skill_reference("$")
    assert parse_skill_reference("$codex:review\ninspect") == ("codex:review", "inspect")


def test_non_user_invocable_and_same_source_conflicts_cannot_run(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        ".agents/skills/hidden/SKILL.md",
        "---\nname: hidden\ndescription: hidden\nuser-invocable: false\n---\nHidden",
    )
    _write_skill(
        tmp_path,
        ".agents/skills/first/SKILL.md",
        "---\nname: duplicate\ndescription: first\n---\nFirst",
    )
    _write_skill(
        tmp_path,
        ".agents/skills/second/SKILL.md",
        "---\nname: duplicate\ndescription: second\n---\nSecond",
    )
    catalog = SkillCatalog(tmp_path)

    with pytest.raises(ValueError, match="不允许用户"):
        catalog.invoke("hidden")
    with pytest.raises(ValueError, match="同一来源中冲突"):
        catalog.invoke("duplicate")
    duplicate = next(item for item in catalog.discover() if item.name == "duplicate")
    assert duplicate.conflicted
    assert "ID 冲突" in duplicate.warnings[-1]


def test_bracketed_allowed_tools_are_normalized(tmp_path: Path) -> None:
    _write_skill(
        tmp_path,
        ".agents/skills/tools/SKILL.md",
        "---\nname: tools\ndescription: tools\nallowed-tools: [read_file, git_diff]\n---\nInspect",
    )

    assert SkillCatalog(tmp_path).discover()[0].requested_tools == ["read_file", "git_diff"]
