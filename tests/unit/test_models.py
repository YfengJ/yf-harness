from __future__ import annotations

import pytest
from pydantic import ValidationError

from yfharness.core.models import Message, MessageRole, Usage


def test_message_text_round_trip() -> None:
    message = Message.text(MessageRole.USER, "你好")

    assert message.role is MessageRole.USER
    assert message.text_content == "你好"
    assert message.id


def test_usage_fills_total() -> None:
    usage = Usage(input_tokens=3, output_tokens=5)

    assert usage.total_tokens == 8


def test_usage_rejects_inconsistent_total() -> None:
    with pytest.raises(ValidationError):
        Usage(input_tokens=3, output_tokens=5, total_tokens=4)
