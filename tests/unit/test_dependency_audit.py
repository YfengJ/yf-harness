from __future__ import annotations

import runpy
from datetime import date
from pathlib import Path

import pytest

check_report = runpy.run_path(
    str(Path(__file__).parents[2] / "scripts" / "check_dependency_audit.py")
)["check_report"]


def report(
    name: str = "nltk", version: str = "3.10.3", identifier: str = "PYSEC-2026-3740"
) -> dict:
    return {"dependencies": [{"name": name, "version": version, "vulns": [{"id": identifier}]}]}


def test_only_exact_dated_exception_is_accepted() -> None:
    assert check_report(report(), today=date(2026, 9, 5)) == []
    assert check_report(report(), today=date(2026, 10, 5))
    assert check_report(report(name="other"), today=date(2026, 9, 5))
    assert check_report(report(version="3.10.4"), today=date(2026, 9, 5))
    assert check_report(report(identifier="new-issue"), today=date(2026, 9, 5))


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        {},
        {"dependencies": []},
        {"dependencies": [None]},
        {"dependencies": [{"name": "skipped", "skip_reason": "unknown"}]},
    ],
)
def test_audit_errors_fail_closed(invalid: object) -> None:
    assert check_report(invalid)


def test_clean_report_is_accepted() -> None:
    assert not check_report({"dependencies": [{"name": "safe", "version": "1", "vulns": []}]})
