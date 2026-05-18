# Speech Agent Component

## Purpose

The `speech_agent/` directory owns the wake-word-gated Gemini Live assistant. It runs separately from the display and Discord bot, and interacts with chores only through public domain commands exposed as Gemini tools.

## Responsibilities

- Stay dormant in wake-word mode using local Microwakeword inference.
- Open Gemini Live only after the wake word is detected.
- Stream microphone audio to Gemini while listening.
- Play Gemini audio responses.
- Handle Gemini tool calls.
- Expose a chore-completion tool that delegates to the chore domain API.
- Return to wake-word mode when the user says a stop phrase or when idle timeout is reached.
- Provide manual diagnostics for audio device listing and mic/speaker self-test.

## Non-Responsibilities

- Do not own chore state.
- Do not import or call Discord internals.
- Do not import or call display internals.
- Do not persist chore state directly.
- Do not update Tk widgets.
- Do not send Discord messages directly.

## Runtime Modes

### Sleeping

- Owns the microphone.
- Runs local wake-word inference.
- Does not connect to Gemini Live.
- Does not stream audio to external services.

### Listening

- Owns microphone and speaker playback.
- Connects to Gemini Live.
- Streams 16 kHz mono PCM microphone input.
- Plays 24 kHz Gemini audio output.
- Sends silence upstream while model audio is playing to reduce echo.
- Handles tool calls and transcripts.

The speech agent is the only component that should own the microphone.

## Public API

The component should expose:

- `run_speech_agent(chores: SpeechChoresApi, config: SpeechAgentConfig) -> Awaitable[None]`: start wake-word mode, Gemini Live listening mode, and component-owned Gemini tool handling.
- `list_audio_devices() -> AudioDeviceReport`: return available PortAudio input and output devices for diagnostics.
- `run_audio_selftest(config: AudioSelfTestConfig) -> AudioSelfTestResult`: record microphone audio, play it back, and return diagnostic details.
- `close() -> Awaitable[None]`: stop wake/listen mode and release microphone, speaker, and Gemini resources.

The runner should accept a chore-facing API rather than concrete Discord or display objects. Gemini tool declarations and tool-call handling remain inside `speech_agent/`.

## Gemini Tools

The first chore tool should be a completion command:

- tool name: `mark_chore_done`
- arguments: chore name or chore id
- behavior: validate the chore, call the chore domain API, return a short result string to Gemini

Future tools may include chore status queries, but the first integration should keep the bridge narrow.

## Configuration

Required for live assistant mode:

- `GEMINI_API_KEY`

Runtime configuration should support:

- input device index
- output device index
- wake model
- custom wake config path
- idle timeout seconds
- debug logging

The development wake model is `hey_jarvis`. The desired product wake phrase is "Hey Schroedinger", which requires a trained Microwakeword model artifact and config.

## Testing

Automated tests should cover tool argument handling and domain delegation with fakes. Tests must not open the microphone, play speaker audio, connect to Gemini, or require `GEMINI_API_KEY`.

Manual tests should cover:

- listing audio devices
- audio self-test
- wake-word detection
- Gemini Live session
- chore tool call from speech
