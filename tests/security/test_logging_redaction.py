from __future__ import annotations

from pathlib import Path

from yfharness.observability.logging import configure_logging
from yfharness.observability.tracing import TraceContext, trace_scope


def test_logs_redact_keys_bearer_tokens_and_trace_context(tmp_path: Path) -> None:
    logger = configure_logging(directory=tmp_path)
    with trace_scope(TraceContext(run_id="run-1", trace_id="trace-1")):
        logger.info(
            "request %s",
            {"Authorization": "Bearer super-secret", "api_key": "sk-test-secret"},
        )
    for handler in logger.handlers:
        handler.flush()

    jsonl = (tmp_path / "debug.jsonl").read_text(encoding="utf-8")
    text = (tmp_path / "yfharness.log").read_text(encoding="utf-8")
    combined = jsonl + text
    assert "super-secret" not in combined
    assert "sk-test-secret" not in combined
    assert "run-1" in combined
    assert "trace-1" in combined
