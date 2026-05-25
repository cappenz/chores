from __future__ import annotations

import asyncio

from speech_agent.runner import (
    SpeechAgentConfig,
    _is_gemini_session_expiry_error,
    _wait_for_wake_word_with_retries,
)
from speech_agent.wake import _read_stream_chunk


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


def test_wake_word_read_timeout_becomes_audio_error(monkeypatch):
    class FakeStream:
        def read(self, *_args, **_kwargs):
            return b""

    async def stalled_to_thread(*_args, **_kwargs):
        await asyncio.Future()

    monkeypatch.setattr("speech_agent.wake.asyncio.to_thread", stalled_to_thread)

    try:
        asyncio.run(_read_stream_chunk(FakeStream(), {}, timeout_seconds=0.01))
    except OSError as error:
        assert "timed out" in str(error)
    else:
        raise AssertionError("expected OSError")


def test_gemini_session_expiry_error_is_recoverable():
    error = RuntimeError(
        "1008 None. Connection aborted because the client failed to close the "
        "connection after receiving a GoAway signal once the session duration expired"
    )

    assert _is_gemini_session_expiry_error(error)


def test_non_expiry_gemini_error_is_not_recoverable():
    assert not _is_gemini_session_expiry_error(RuntimeError("500 internal error"))
