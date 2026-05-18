from __future__ import annotations

import os

import pytest


pytestmark = pytest.mark.manual


def test_audio_generation_plays_on_default_speakers():
    if os.getenv("CHORES_TEST_AUDIO") != "1":
        pytest.skip("Run this explicit manual case with `make test-audio`.")
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY is required for the manual audio test.")
    if not os.getenv("ELEVENLABS_API_KEY"):
        pytest.skip("ELEVENLABS_API_KEY is required for the manual audio test.")

    from core.audio_announcements import generate_audio, generate_speech

    speech = generate_speech("dishwasher", "Guido")

    assert speech
    generate_audio(speech)
