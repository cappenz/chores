from __future__ import annotations

import asyncio

from speech_agent.runner import SpeechAgentConfig, _wait_for_wake_word_with_retries


def test_wake_word_audio_errors_are_retried():
    calls = 0
    sleeps = []

    async def wait_for_wake(**_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise OSError("Internal PortAudio error")

    async def sleep(seconds: float):
        sleeps.append(seconds)

    config = SpeechAgentConfig(wake_retry_delay_seconds=0.25)

    asyncio.run(_wait_for_wake_word_with_retries(config, wait_for_wake=wait_for_wake, sleep=sleep))

    assert calls == 2
    assert sleeps == [0.25]


def test_non_audio_wake_word_errors_are_not_retried():
    async def wait_for_wake(**_kwargs):
        raise RuntimeError("bad wake model")

    async def sleep(_seconds: float):
        raise AssertionError("unexpected retry sleep")

    config = SpeechAgentConfig(wake_retry_delay_seconds=0.25)

    try:
        asyncio.run(_wait_for_wake_word_with_retries(config, wait_for_wake=wait_for_wake, sleep=sleep))
    except RuntimeError as error:
        assert str(error) == "bad wake model"
    else:
        raise AssertionError("expected RuntimeError")
