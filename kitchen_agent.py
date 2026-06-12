from __future__ import annotations

import asyncio
import os
import sys

from chores import ChoreCommandResult, ChoresService
from core.audio_announcements import generate_and_play_audio_async, generate_and_play_timer_audio_async
from core.people import load_people
from discord_bot import ChoresBot, format_result_for_discord
from display import ScreenStatus, create_screen
from face_samples import FaceSampleCollector
from kitchen_timer import (
    KitchenTimerEvent,
    KitchenTimerService,
    KitchenTimerStatus,
    format_remaining,
)
from reachy import ReachyConfig, run_reachy_companion
from speech_agent import AssistantEvent, SpeechAgentConfig, run_speech_agent


class AppChoresApi:
    def __init__(
        self,
        chores: ChoresService,
        kitchen_timer: KitchenTimerService,
        bot: ChoresBot | None,
        after_result,
        after_timer_change,
        reachy,
    ) -> None:
        self.chores = chores
        self.kitchen_timer = kitchen_timer
        self.bot = bot
        self.after_result = after_result
        self.after_timer_change = after_timer_change
        self.reachy = reachy

    def mark_chore_done(self, chore: str, source: str = "speech") -> ChoreCommandResult:
        return self.write_chore(chore, "next", source=source)

    def read_chores(self) -> tuple[tuple[str, str], ...]:
        return self.chores.read_chores()

    def write_chore(self, chore: str, person: str, source: str = "speech") -> ChoreCommandResult:
        result = self.chores.write_chore(chore, person, source=source)
        asyncio.create_task(self.after_result(result))
        if self.bot:
            asyncio.create_task(self.bot.send_reply(format_result_for_discord(self.chores, result)))
        return result

    def get_status(self):
        return self.chores.get_status()

    def show_emotion(self, emotion: str) -> None:
        asyncio.create_task(self.reachy.show_emotion(emotion))

    def start_timer(self, time_period: str, name: str) -> str:
        result = self.kitchen_timer.start_timer(time_period, name)
        self.after_timer_change()
        return result.message

    def read_timer(self) -> str:
        return self.kitchen_timer.read_timer().message

    def stop_timer(self) -> str:
        result = self.kitchen_timer.stop_timer()
        self.after_timer_change()
        return result.message


def main() -> None:
    people = load_people()
    chores = ChoresService(people=people)
    kitchen_timer = KitchenTimerService()
    assistant_events: asyncio.Queue[AssistantEvent] = asyncio.Queue()
    bot: ChoresBot | None = None
    gemini_active = False
    screen = None

    def on_face_sample_saved(image_path) -> None:
        if screen:
            screen.add_face_sample(image_path)

    reachy = run_reachy_companion(
        _reachy_config_from_env(),
        face_sample_collector=FaceSampleCollector(),
        on_face_sample_saved=on_face_sample_saved,
    )

    async def after_result(result: ChoreCommandResult) -> None:
        refresh_screen_without_pump()
        if (
            result.ok
            and result.state_changed
            and chores.get_audio_enabled()
            and result.chore_display_name
            and result.next_person_display_name
        ):
            await generate_and_play_audio_async(result.chore_display_name, result.next_person_display_name)

    def refresh_screen() -> None:
        if screen:
            screen.refresh(chores.get_status())
            screen.set_status(_screen_status_from_timer(kitchen_timer.get_status()))
            screen.pump()

    def refresh_screen_without_pump() -> None:
        if screen:
            screen.refresh(chores.get_status())
            screen.set_status(_screen_status_from_timer(kitchen_timer.get_status()))

    def after_timer_change() -> None:
        refresh_screen_without_pump()

    def on_screen_chore_done(chore_id: str) -> None:
        if bot:
            bot.schedule_handle_text(chore_id)

    def on_audio_toggle(enabled: bool) -> None:
        chores.set_audio_enabled(enabled, source="display")

    def on_gemini_connection_active(active: bool) -> None:
        nonlocal gemini_active
        gemini_active = active
        if screen:
            screen.set_speech_active(active)

    async def on_assistant_awake(active: bool) -> None:
        if active:
            await reachy.wake()
        else:
            await reachy.sleep()

    async def on_assistant_speaking(active: bool) -> None:
        await reachy.set_speaking(active)

    async def watch_kitchen_timer() -> None:
        nonlocal gemini_active
        while True:
            event = await kitchen_timer.events().get()
            refresh_screen_without_pump()
            if event.kind == "wake_soon":
                await reachy.wake()
                continue
            if event.kind not in {"finished", "repeat_finished"} or event.status is None:
                continue

            await reachy.wake()
            assistant_event = _assistant_event_for_timer(event)
            if gemini_active:
                assistant_events.put_nowait(assistant_event)
            else:
                await generate_and_play_timer_audio_async(event.status.name)

    async def start_speech_agent() -> None:
        await prepare_reachy_for_startup(reachy)
        asyncio.create_task(watch_kitchen_timer())
        asyncio.create_task(
            run_speech_agent(
                AppChoresApi(
                    chores,
                    kitchen_timer,
                    bot,
                    after_result,
                    after_timer_change,
                    reachy,
                ),
                SpeechAgentConfig(
                    on_gemini_connection_active=on_gemini_connection_active,
                    on_assistant_awake=on_assistant_awake,
                    on_assistant_speaking=on_assistant_speaking,
                    assistant_events=assistant_events,
                    timer_active=kitchen_timer.is_active,
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


async def prepare_reachy_for_startup(reachy) -> None:
    await reachy.sleep()


def _screen_status_from_timer(status: KitchenTimerStatus | None) -> ScreenStatus | None:
    if status is None:
        return None
    return ScreenStatus(
        title=status.name,
        value=format_remaining(status.remaining_seconds),
        highlighted=True,
    )


def _assistant_event_for_timer(event: KitchenTimerEvent) -> AssistantEvent:
    assert event.status is not None
    kind = "timer_repeat" if event.kind == "repeat_finished" else "timer_finished"
    return AssistantEvent(
        kind,
        (
            f"The kitchen timer named {event.status.name!r} is finished. "
            "Announce that it is finished now. Keep it short and natural."
        ),
    )


def _reachy_config_from_env() -> ReachyConfig:
    return ReachyConfig(
        enabled=_env_bool("REACHY_ENABLED", default=True),
        face_tracking_enabled=_env_bool("REACHY_FACE_TRACKING", default=True),
        emotion_playback_enabled=_env_bool("REACHY_EMOTIONS", default=True),
        speaking_motion_enabled=_env_bool("REACHY_SPEAKING_MOTION", default=True),
        debug=_env_bool("REACHY_DEBUG", default=False),
        connect_retry_seconds=_env_float("REACHY_CONNECT_RETRY_SECONDS", default=3.0),
        max_connect_retry_seconds=_env_float_optional("REACHY_MAX_CONNECT_RETRY_SECONDS"),
        reconnect_on_command_failure=_env_bool("REACHY_RECONNECT_ON_FAILURE", default=True),
    )


def _env_bool(name: str, *, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.casefold() in {"1", "true", "yes", "on"}


def _env_float(name: str, *, default: float) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return float(value)


def _env_float_optional(name: str) -> float | None:
    value = os.getenv(name)
    if value is None or not value.strip():
        return None
    return float(value)


if __name__ == "__main__":
    main()
