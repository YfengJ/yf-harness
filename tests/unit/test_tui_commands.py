from __future__ import annotations

import pytest

from yfharness.tui.commands import (
    SlashCommandError,
    command_suggestions,
    parse_slash_command,
)


def test_slash_command_parses_quoted_arguments_client_side() -> None:
    command = parse_slash_command('/rename "新的 会话"')

    assert command is not None
    assert command.name == "rename"
    assert command.arguments == ("新的 会话",)


def test_plain_text_is_not_a_slash_command() -> None:
    assert parse_slash_command("explain /help in prose") is None


def test_unknown_command_suggests_nearest_name() -> None:
    with pytest.raises(SlashCommandError, match="/context"):
        parse_slash_command("/contex")


def test_command_completion_filters_prefix() -> None:
    assert command_suggestions("/pro") == ["/provider — 查看或切换 Provider"]
