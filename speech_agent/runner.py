from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from speech_agent.live import run_live
from speech_agent.tools import SpeechChoresApi
from speech_agent.wake import wait_for_wake_word

DEFAULT_WAKE_MODEL = "hey_jarvis"
DEFAULT_IDLE_TIMEOUT_SECONDS = 300.0
SpeechConnectionCallback = Callable[[bool], Awaitable[None] | None]
SpeechResponseTextCallback = Callable[[str], Awaitable[None] | None]


@dataclass(frozen=True)
class SpeechAgentConfig:
    debug: bool = False
    input_device_index: int | None = None
    output_device_index: int | None = None
    wake_model: str = DEFAULT_WAKE_MODEL
    wake_config: str | None = None
    idle_timeout_seconds: float = DEFAULT_IDLE_TIMEOUT_SECONDS
    on_gemini_connection_active: SpeechConnectionCallback | None = None
    on_assistant_awake: SpeechConnectionCallback | None = None
    on_assistant_speaking: SpeechConnectionCallback | None = None
    on_assistant_response_text: SpeechResponseTextCallback | None = None


async def run_speech_agent(chores: SpeechChoresApi, config: SpeechAgentConfig) -> None:
    if not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError("Set GEMINI_API_KEY to your Google AI Studio API key.")
    genai = _genai()

    while True:
        await wait_for_wake_word(
            input_device_index=config.input_device_index,
            wake_model=config.wake_model,
            wake_config=config.wake_config,
            debug=config.debug,
        )
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
            )
        finally:
            await _notify_connection(config.on_assistant_awake, False)
        print("[sleeping] Returned to wake-word mode.", flush=True)


def _genai():
    from google import genai

    return genai


async def _notify_connection(callback: SpeechConnectionCallback | None, active: bool) -> None:
    if callback is None:
        return
    result = callback(active)
    if result is not None:
        await result

