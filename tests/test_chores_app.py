from __future__ import annotations

import asyncio
import sys
import types

from chores import ChoresApp, ChoresState


def test_state_is_saved_and_loaded(isolated_data_dir):
    app = ChoresApp()
    app.update_state(1, 2, 3)

    reloaded = ChoresApp()

    assert reloaded.state == ChoresState(1, 2, 3)
    assert (isolated_data_dir / "status.json").exists()


def test_on_message_reports_status_without_external_services(isolated_data_dir):
    app = ChoresApp()
    replies = []

    async def reply(message: str) -> None:
        replies.append(message)

    app.set_reply_callback(reply)

    asyncio.run(app.on_message("status please"))

    assert len(replies) == 1
    assert "dishwasher" in replies[0]
    assert "kitchen trash" in replies[0]
    assert "Wednesday trash" in replies[0]


def test_mark_chore_done_rotates_assignment_without_audio(isolated_data_dir, monkeypatch):
    fake_bot = types.SimpleNamespace(
        chore_people_discord=[
            "Isabelle, <@1>",
            "Guido, <@2>",
            "Daniel, <@3>",
            "Charlotte, <@4>",
            "Thomas, <@5>",
        ]
    )
    monkeypatch.setitem(sys.modules, "chores_bot", types.SimpleNamespace(ChoresBot=fake_bot))

    async def fail_if_audio_called(chore_name: str, chore_person: str) -> None:
        raise AssertionError(f"Audio should not run for {chore_name}/{chore_person}")

    monkeypatch.setitem(
        sys.modules,
        "models",
        types.SimpleNamespace(generate_and_play_audio_async=fail_if_audio_called),
    )

    app = ChoresApp()
    app.audio_enabled = False
    replies = []
    refreshes = []

    async def reply(message: str) -> None:
        replies.append(message)

    app.set_reply_callback(reply)
    app.set_ui_refresh_callback(lambda: refreshes.append("refresh"))

    asyncio.run(app.mark_chore_done("dishwasher"))

    assert app.state == ChoresState(1, 0, 0)
    assert replies == ["It's Guido, <@2>'s turn to do the dishwasher"]
    assert refreshes == ["refresh"]
