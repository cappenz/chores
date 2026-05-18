from __future__ import annotations

import asyncio
import os
import sys

from chores import ChoreCommandResult, ChoresService
from core.audio_announcements import generate_and_play_audio_async
from core.people import load_people
from discord_bot import ChoresBot, format_result_for_discord
from display import create_screen
from speech_agent import SpeechAgentConfig, run_speech_agent


class AppChoresApi:
    def __init__(self, chores: ChoresService, bot: ChoresBot | None, after_result) -> None:
        self.chores = chores
        self.bot = bot
        self.after_result = after_result

    def mark_chore_done(self, chore: str, source: str = "speech") -> ChoreCommandResult:
        result = self.chores.mark_chore_done(chore, source=source)
        asyncio.create_task(self.after_result(result))
        if self.bot:
            asyncio.create_task(self.bot.send_reply(format_result_for_discord(self.chores, result)))
        return result

    def get_status(self):
        return self.chores.get_status()


def main() -> None:
    people = load_people()
    chores = ChoresService(people=people)
    bot: ChoresBot | None = None

    async def after_result(result: ChoreCommandResult) -> None:
        if screen:
            screen.refresh(chores.get_status())
        if result.ok and chores.get_audio_enabled() and result.chore_display_name and result.next_person_display_name:
            await generate_and_play_audio_async(result.chore_display_name, result.next_person_display_name)

    def refresh_screen() -> None:
        if screen:
            screen.refresh(chores.get_status())
            screen.pump()

    def on_screen_chore_done(chore_id: str) -> None:
        if bot:
            bot.schedule_handle_text(chore_id)

    def on_audio_toggle(enabled: bool) -> None:
        chores.set_audio_enabled(enabled, source="display")

    def on_gemini_connection_active(active: bool) -> None:
        if screen:
            screen.set_speech_active(active)

    async def start_speech_agent() -> None:
        asyncio.create_task(
            run_speech_agent(
                AppChoresApi(chores, bot, after_result),
                SpeechAgentConfig(on_gemini_connection_active=on_gemini_connection_active),
            )
        )

    try:
        screen = create_screen(
            people,
            chores.get_status(),
            on_chore_done=on_screen_chore_done,
            on_audio_toggle=on_audio_toggle,
            window_mode=os.getenv("WINDOWMODE"),
        )
    except (ValueError, IndexError):
        print("Invalid WINDOWMODE format. Expected format: '1280 x 800'")
        sys.exit(1)

    bot = ChoresBot(
        chores,
        after_result=after_result,
        refresh_ui=refresh_screen,
        on_ready_callback=start_speech_agent,
    )
    bot.run()


if __name__ == "__main__":
    main()
