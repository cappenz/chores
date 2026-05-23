from __future__ import annotations

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from speech_agent.events import AssistantEvent
from speech_agent.live import run_live
from speech_agent.tools import SpeechChoresApi, reset_web_search_counter
from speech_agent.wake import wait_for_wake_word

DEFAULT_WAKE_MODEL = "hey_jarvis"
DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
DEFAULT_WAKE_RETRY_DELAY_SECONDS = 1.0
SpeechConnectionCallback = Callable[[bool], Awaitable[None] | None]
SpeechResponseTextCallback = Callable[[str], Awaitable[None] | None]
TimerActiveCallback = Callable[[], bool]


@dataclass(frozen=True)
class SpeechAgentConfig:
    debug: bool = False
    input_device_index: int | None = None
    output_device_index: int | None = None
    wake_model: str = DEFAULT_WAKE_MODEL
    wake_config: str | None = None
    wake_retry_delay_seconds: float = DEFAULT_WAKE_RETRY_DELAY_SECONDS
    idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS
    on_gemini_connection_active: SpeechConnectionCallback | None = None
    on_assistant_awake: SpeechConnectionCallback | None = None
    on_assistant_speaking: SpeechConnectionCallback | None = None
    on_assistant_response_text: SpeechResponseTextCallback | None = None
    assistant_events: asyncio.Queue[AssistantEvent] | None = None
    timer_active: TimerActiveCallback | None = None


async def run_speech_agent(chores: SpeechChoresApi, config: SpeechAgentConfig) -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY to your Google AI Studio API key.")
    genai = _genai()

    while True:
        await _wait_for_wake_word_with_retries(config)
        reset_web_search_counter()
        await _notify_connection(config.on_assistant_awake, True)
        client = genai.Client(http_options={"api_version": "v1alpha"})
        try:
            await run_live(
                client,
                chores,
                debug=config.debug,
                input_device_index=config.input_device_index,
                output_device_index=config.output_device_index,
                idle_timeout_seconds=config.idle_timeout_seconds,
                on_connection_active=config.on_gemini_connection_active,
                on_assistant_speaking=config.on_assistant_speaking,
                on_assistant_response_text=config.on_assistant_response_text,
                assistant_events=config.assistant_events,
                timer_active=config.timer_active,
            )
        finally:
            await _notify_connection(config.on_assistant_awake, False)
        print("[sleeping] Returned to wake-word mode.", flush=True)


async def _wait_for_wake_word_with_retries(
    config: SpeechAgentConfig,
    wait_for_wake=wait_for_wake_word,
    sleep=asyncio.sleep,
) -> None:
    while True:
        try:
            await wait_for_wake(
                input_device_index=config.input_device_index,
                wake_model=config.wake_model,
                wake_config=config.wake_config,
                debug=config.debug,
            )
            return
        except OSError as error:
            print(
                f"[sleeping] Wake-word audio failed ({error!r}); "
                f"retrying in {config.wake_retry_delay_seconds:.1f}s.",
                flush=True,
            )
            await sleep(config.wake_retry_delay_seconds)


def _genai():
    from google import genai

    return genai


async def _notify_connection(callback: SpeechConnectionCallback | None, active: bool) -> None:
    if callback is None:
        return
    result = callback(active)
    if result is not None:
        await result

