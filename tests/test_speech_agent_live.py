from __future__ import annotations

import asyncio

from speech_agent.events import AssistantEvent
from speech_agent.live import AudioLoop


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
