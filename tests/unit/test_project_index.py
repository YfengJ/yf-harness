from __future__ import annotations

import subprocess
from pathlib import Path

from yfharness.core.project_index import ProjectIndex


def test_project_index_ranks_filename_content_and_git_changes(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "src").mkdir(parents=True)
    (workspace / "docs").mkdir()
    (workspace / "src" / "parser.py").write_text(
        "def validate_parser_input(value: str) -> bool:\n    return bool(value)\n",
        encoding="utf-8",
    )
    (workspace / "src" / "other.py").write_text("VALUE = 1\n", encoding="utf-8")
    (workspace / "docs" / "guide.md").write_text("Parser overview\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
    subprocess.run(["git", "add", "."], cwd=workspace, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.com",
            "commit",
            "-qm",
            "init",
        ],
        cwd=workspace,
        check=True,
    )
    (workspace / "src" / "parser.py").write_text(
        "def validate_parser_input(value: str) -> bool:\n    return value.isidentifier()\n",
        encoding="utf-8",
    )

    selected = ProjectIndex(workspace).select("improve parser validation")

    assert selected
    assert selected[0].path == "src/parser.py"
    assert "Git 工作区已修改" in selected[0].reasons


def test_project_index_falls_back_outside_git_and_skips_build_outputs(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "dist").mkdir()
    (tmp_path / "src" / "router.py").write_text("route_registry = {}", encoding="utf-8")
    (tmp_path / "dist" / "router.py").write_text("generated route_registry", encoding="utf-8")

    selected = ProjectIndex(tmp_path).select("router registry")

    assert [item.path for item in selected] == ["src/router.py"]


def test_project_index_reuses_samples_but_invalidates_changed_file(tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text("parser token", encoding="utf-8")
    index = ProjectIndex(tmp_path)

    assert index.select("parser")[0].path == "module.py"
    path.write_text("renderer token with different size", encoding="utf-8")

    assert index.select("renderer")[0].path == "module.py"
