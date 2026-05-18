from __future__ import annotations

import asyncio

import models


def test_generate_audio_uses_announcement_voice_id(monkeypatch):
    calls = []
    audio = [b"fake-audio"]

    class FakeTextToSpeech:
        def convert(self, *, voice_id: str, text: str, model_id: str):
            calls.append(("convert", voice_id, text, model_id))
            return audio

    class FakeElevenLabs:
        def __init__(self, *, api_key: str | None):
            calls.append(("client", api_key))
            self.text_to_speech = FakeTextToSpeech()

    def fake_play(generated_audio):
        calls.append(("play", generated_audio))

    monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")
    monkeypatch.setattr(models, "ElevenLabs", FakeElevenLabs)
    monkeypatch.setattr(models, "play", fake_play)

    models.generate_audio("Test announcement")

    assert calls == [
        ("client", "test-key"),
        ("convert", models.ANNOUNCEMENT_VOICE_ID, "Test announcement", "eleven_multilingual_v2"),
        ("play", audio),
    ]


def test_audio_orchestration_uses_mocked_generation(monkeypatch):
    calls = []

    def fake_generate_speech(chore_name: str, chore_person: str) -> str:
        calls.append(("speech", chore_name, chore_person))
        return "Test announcement"

    def fake_generate_audio(text: str) -> None:
        calls.append(("audio", text))

    monkeypatch.setattr(models, "generate_speech", fake_generate_speech)
    monkeypatch.setattr(models, "generate_audio", fake_generate_audio)

    asyncio.run(models.generate_and_play_audio_async("dishwasher", "Guido"))

    assert calls == [
        ("speech", "dishwasher", "Guido"),
        ("audio", "Test announcement"),
    ]