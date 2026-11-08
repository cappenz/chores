from __future__ import annotations

import asyncio
from types import SimpleNamespace

from speech_agent.events import AssistantEvent
from speech_agent.live import AudioLoop, ListeningComplete


class FakePyAudioModule:
    class PyAudio:
        def terminate(self) -> None:
            pass


class FakeChores:
    pass


def test_assistant_events_are_sent_to_live_session(monkeypatch):
    class FakeSession:
        def __init__(self):
            self.calls = []

        async def send_client_content(self, *, turns, turn_complete):
            self.calls.append((turns, turn_complete))

    async def scenario():
        events = asyncio.Queue()
        session = FakeSession()
        loop = AudioLoop(
            session,
            FakeChores(),
            debug=False,
            input_device_index=None,
            output_device_index=None,
            idle_timeout_seconds=300.0,
            assistant_events=events,
        )
        task = asyncio.create_task(loop.process_assistant_events())
        await events.put(AssistantEvent("timer_finished", "Announce the pizza timer."))
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return session.calls

    monkeypatch.setattr("speech_agent.live._pyaudio", lambda: FakePyAudioModule)

    calls = asyncio.run(scenario())

    assert calls == [
        (
            {
                "role": "user",
                "parts": [{"text": "Announce the pizza timer."}],
            },
            True,
        )
    ]


def test_idle_watchdog_does_not_sleep_while_timer_active(monkeypatch):
    async def scenario():
        loop = AudioLoop(
            object(),
            FakeChores(),
            debug=False,
            input_device_index=None,
            output_device_index=None,
            idle_timeout_seconds=0.01,
            timer_active=lambda: True,
        )
        task = asyncio.create_task(loop.idle_watchdog())
        await asyncio.sleep(0.03)
        still_running = not task.done()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return still_running

    monkeypatch.setattr("speech_agent.live._pyaudio", lambda: FakePyAudioModule)

    assert asyncio.run(scenario())


def test_goaway_returns_to_wake_word_mode(monkeypatch):
    class FakeSession:
        def receive(self):
            async def responses():
                yield SimpleNamespace(go_away=object())

            return responses()

    async def scenario():
        loop = AudioLoop(
            FakeSession(),
            FakeChores(),
            debug=False,
            input_device_index=None,
            output_device_index=None,
            idle_timeout_seconds=300.0,
        )
        loop.audio_in_queue = asyncio.Queue()
        try:
            await loop.receive_audio()
        except ListeningComplete:
            return loop.stop_reason
        raise AssertionError("expected ListeningComplete")

    monkeypatch.setattr("speech_agent.live._pyaudio", lambda: FakePyAudioModule)
    monkeypatch.setattr("speech_agent.live._genai_types", lambda: object())

    assert asyncio.run(scenario()) == "Gemini Live session duration reached"


def test_goaway_resumes_session_with_latest_handle(monkeypatch):
    update = SimpleNamespace(resumable=True, new_handle="handle-2")

    class FirstSession:
        def receive(self):
            async def responses():
                yield SimpleNamespace(session_resumption_update=update, go_away=None, tool_call=None, data=None, text=None, server_content=None)
                yield SimpleNamespace(go_away=object())

            return responses()

    class ResumedSession:
        def receive(self):
            async def responses():
                raise ListeningComplete()
                yield

            return responses()

    resumed = ResumedSession()
    handles = []

    async def reconnect(handle: str):
        handles.append(handle)
        return resumed

    async def scenario():
        loop = AudioLoop(
            FirstSession(),
            FakeChores(),
            debug=False,
            input_device_index=None,
            output_device_index=None,
            idle_timeout_seconds=300.0,
            reconnect=reconnect,
        )
        loop.audio_in_queue = asyncio.Queue()
        try:
            await loop.receive_audio()
        except ListeningComplete:
            return loop.session
        raise AssertionError("expected ListeningComplete")

    monkeypatch.setattr("speech_agent.live._pyaudio", lambda: FakePyAudioModule)
    monkeypatch.setattr("speech_agent.live._genai_types", lambda: object())

    assert asyncio.run(scenario()) is resumed
    assert handles == ["handle-2"]
