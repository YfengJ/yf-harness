"""Execute offline eval cases and produce an evidence-bearing report."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import Field

from yfharness.config.paths import data_dir
from yfharness.core.models import DomainModel
from yfharness.evals.cases import CASES, temporary_workspace


class EvalCaseResult(DomainModel):
    name: str
    passed: bool
    duration: float
    steps: int = 0
    tool_errors: int = 0
    reason: str = ""


class EvalReport(DomainModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    total: int
    passed: int
    failed: int
    pass_rate: float
    duration: float
    average_steps: float
    tool_errors: int
    cases: list[EvalCaseResult]
    report_path: str = ""


class EvalRunner:
    async def run(self, *, report_directory: Path | None = None) -> EvalReport:
        started = time.monotonic()
        results: list[EvalCaseResult] = []
        for name, function in CASES:
            case_started = time.monotonic()
            with temporary_workspace() as directory:
                workspace = Path(directory)
                try:
                    passed, steps, tool_errors, reason = await function(workspace)
                except Exception as exc:
                    passed, steps, tool_errors, reason = False, 0, 1, f"{type(exc).__name__}: {exc}"
            results.append(
                EvalCaseResult(
                    name=name,
                    passed=passed,
                    duration=time.monotonic() - case_started,
                    steps=steps,
                    tool_errors=tool_errors,
                    reason=reason,
                )
            )
        passed_count = sum(result.passed for result in results)
        target = report_directory or data_dir() / "evals"
        target.mkdir(parents=True, exist_ok=True)
        path = target / f"eval-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
        report = EvalReport(
            total=len(results),
            passed=passed_count,
            failed=len(results) - passed_count,
            pass_rate=passed_count / len(results) if results else 0,
            duration=time.monotonic() - started,
            average_steps=sum(result.steps for result in results) / len(results) if results else 0,
            tool_errors=sum(result.tool_errors for result in results),
            cases=results,
            report_path=str(path),
        )
        path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
        return report
