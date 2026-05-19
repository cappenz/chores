from __future__ import annotations

import asyncio
import os
import sys

from chores import ChoreCommandResult, ChoresService
from core.audio_announcements import generate_and_play_audio_async
from core.people import load_people
from discord_bot import ChoresBot, format_result_for_discord
from display import create_screen
from reachy import ReachyConfig, run_reachy_companion
from speech_agent import SpeechAgentConfig, run_speech_agent


class AppChoresApi:
    def __init__(self, chores: ChoresService, bot: ChoresBot | None, after_result, reachy) -> None:
        self.chores = chores
        self.bot = bot
        self.after_result = after_result
        self.reachy = reachy

    def mark_chore_done(self, chore: str, source: str = "speech") -> ChoreCommandResult:
        result = self.chores.mark_chore_done(chore, source=source)
        asyncio.create_task(self.after_result(result))
        if self.bot:
            asyncio.create_task(self.bot.send_reply(format_result_for_discord(self.chores, result)))
        return result

    def get_status(self):
        return self.chores.get_status()

    def show_emotion(self, emotion: str) -> None:
        asyncio.create_task(self.reachy.show_emotion(emotion))


def main() -> None:
    people = load_people()
    chores = ChoresService(people=people)
    bot: ChoresBot | None = None
    reachy = run_reachy_companion(_reachy_config_from_env())

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

    async def on_assistant_awake(active: bool) -> None:
        if active:
            await reachy.wake()
        else:
            await reachy.sleep()

    async def on_assistant_speaking(active: bool) -> None:
        await reachy.set_speaking(active)

    async def start_speech_agent() -> None:
        asyncio.create_task(
            run_speech_agent(
                AppChoresApi(chores, bot, after_result, reachy),
                SpeechAgentConfig(
                    on_gemini_connection_active=on_gemini_connection_active,
                    on_assistant_awake=on_assistant_awake,
                    on_assistant_speaking=on_assistant_speaking,
                ),
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
    try:
        bot.run()
    finally:
        asyncio.run(reachy.close())


def _reachy_config_from_env() -> ReachyConfig:
    return ReachyConfig(
        enabled=_env_bool("REACHY_ENABLED", default=True),
        face_tracking_enabled=_env_bool("REACHY_FACE_TRACKING", default=True),
        emotion_playback_enabled=_env_bool("REACHY_EMOTIONS", default=True),
        speaking_motion_enabled=_env_bool("REACHY_SPEAKING_MOTION", default=True),
        debug=_env_bool("REACHY_DEBUG", default=False),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.casefold() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    main()
