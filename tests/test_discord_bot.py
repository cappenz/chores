from __future__ import annotations

from chores import ChoresService
from discord_bot.bot import format_result_for_discord, format_status_for_discord, parse_discord_message


def test_discord_status_format_owns_mentions(isolated_data_dir):
    chores = ChoresService()

    message = format_status_for_discord(chores.get_status(), chores)

    assert "Isabelle, <@663405556312047633>" in message
    assert "Dishwasher" in message
    assert "Kitchen trash" in message
    assert "Wednesday trash" in message


def test_discord_parser_marks_chore_done(isolated_data_dir):
    chores = ChoresService()

    result = parse_discord_message(chores, "dishwasher is done")

    assert result.ok
    assert format_result_for_discord(chores, result) == (
        "It's Guido, <@339570174451646469>'s turn to do the Dishwasher"
    )


def test_discord_parser_reports_status(isolated_data_dir):
    chores = ChoresService()

    result = parse_discord_message(chores, "status please")

    assert result.ok
    assert "Kitchen trash" in result.message
