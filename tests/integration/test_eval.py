from __future__ import annotations

from pathlib import Path

import anyio
import pytest

from yfharness.evals.runner import EvalRunner


@pytest.mark.asyncio
async def test_all_twenty_offline_evals_pass_and_write_report(tmp_path: Path) -> None:
    report = await EvalRunner().run(report_directory=tmp_path)

    assert report.total == 20
    assert report.passed == 20
    assert report.failed == 0
    assert report.pass_rate == 1.0
    assert await anyio.Path(report.report_path).is_file()
