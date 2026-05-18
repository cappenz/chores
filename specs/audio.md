# Audio Generation

## Purpose

Audio announcements make chore rotations more playful. They are optional at runtime and disabled from the regular automated test suite.

## Runtime Flow

When the chores domain advances a chore and audio announcements are enabled, the app may request a generated announcement. The helper generates short announcement text, generates speech audio, and plays it on the host speaker.

This behavior should live behind a small API in `core/` if it remains shared infrastructure. The chores domain should not import OpenAI or ElevenLabs directly.

## Components

`generate_speech(chore_name, chore_person)` creates an OpenAI client and asks for a very short chore announcement. It returns the generated text.

`generate_audio(text)` creates an ElevenLabs client using `ELEVENLABS_API_KEY`, generates speech with the configured announcement voice ID (`QvlD90AkjGTCqc9685Rq`) and the `eleven_multilingual_v2` model, then plays the result through the host's default audio output.

`generate_and_play_audio_async(chore_name, chore_person)` runs speech generation and audio playback in background threads so the async chore handler does not block the event loop. It catches and prints errors instead of crashing the app.

## Credentials

Real audio generation requires:

- `OPENAI_API_KEY`
- `ELEVENLABS_API_KEY`

The normal app run loads credentials from `.env` with `uv run --env-file .env python3 kitchen_agent.py`. The manual audio smoke test loads the same file through `make test-audio`.

## Testing

Use `make test` for regular automated tests. These tests must mock or bypass audio generation and must not call OpenAI, ElevenLabs, or speaker playback.

Use `make test-audio` only when you intentionally want to spend API credits and hear the generated announcement through the default speakers on the host running the test.
