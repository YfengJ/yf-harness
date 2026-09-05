"""Fail closed on audit errors; accept only the dated, reviewed optional NLTK issue."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

EXPIRES = date(2026, 10, 5)
ADVISORIES = {"PYSEC-2026-3740", "GHSA-8mgp-746c-j5xp", "CVE-2026-81726"}


def check_report(report: object, *, today: date | None = None) -> list[str]:
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        return ["Invalid or missing pip-audit dependencies report"]
    dependencies = report["dependencies"]
    if not dependencies:
        return ["Empty dependency audit"]
    errors: list[str] = []
    for dependency in dependencies:
        if not isinstance(dependency, dict) or not isinstance(dependency.get("vulns"), list):
            errors.append("Invalid or skipped dependency audit entry")
            continue
        name, version = dependency.get("name"), dependency.get("version")
        if not isinstance(name, str) or not isinstance(version, str) or "skip_reason" in dependency:
            errors.append("Invalid or skipped dependency audit entry")
            continue
        for vulnerability in dependency["vulns"]:
            if not isinstance(vulnerability, dict) or not isinstance(vulnerability.get("id"), str):
                errors.append(f"Invalid vulnerability entry: {name}")
                continue
            identifier = vulnerability["id"]
            if (
                name == "nltk"
                and version == "3.10.3"
                and identifier in ADVISORIES
                and (today or date.today()) < EXPIRES
            ):
                print(f"KNOWN UNFIXED: {name} {version} {identifier}; review before {EXPIRES}")
            else:
                errors.append(f"Unaccepted vulnerability: {name} {version} {identifier}")
    return errors


def main() -> None:
    try:
        report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        errors = check_report(report)
    except (OSError, ValueError, IndexError) as exc:
        raise SystemExit(f"Cannot validate dependency audit: {exc}") from exc
    if errors:
        raise SystemExit("\n".join(errors))
    print("Dependency audit accepted (see any KNOWN UNFIXED notices above).")


if __name__ == "__main__":
    main()
