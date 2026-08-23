from __future__ import annotations

from pathlib import Path

import pytest

from yfharness.core.exceptions import ToolProtocolError
from yfharness.core.tool_protocol import parse_fallback_tool_calls


def test_multiline_fallback_call() -> None:
    calls = parse_fallback_tool_calls(
        """
<YFH_TOOL_CALL>
{
  "tool": "read_file",
  "arguments": {"path": "README.md"}
}
</YFH_TOOL_CALL>
"""
    )

    assert calls is not None
    assert calls[0].name == "read_file"
    assert calls[0].arguments == {"path": "README.md"}


@pytest.mark.parametrize(
    "text",
    [
        '<YFH_TOOL_CALL>{"tool":"x","arguments":{}}',
        '<YFH_TOOL_CALL>```json\n{"tool":"x","arguments":{}}\n```</YFH_TOOL_CALL>',
        'explain <YFH_TOOL_CALL>{"tool":"x","arguments":{}}</YFH_TOOL_CALL>',
        '<YFH_TOOL_CALL>{"tool":"x","arguments":[]} </YFH_TOOL_CALL>',
        '<YFH_TOOL_CALL>{"tool":"x","arguments":{},"extra":1}</YFH_TOOL_CALL>',
    ],
)
def test_malformed_or_mixed_fallback_is_rejected(text: str) -> None:
    with pytest.raises(ToolProtocolError):
        parse_fallback_tool_calls(text)


def test_plain_markdown_and_code_never_trigger_tool(tmp_path: Path) -> None:
    marker = tmp_path / "executed"
    payload = f"```python\nopen({str(marker)!r}, 'w').write('bad')\n```"

    assert parse_fallback_tool_calls(payload) is None
    assert not marker.exists()
