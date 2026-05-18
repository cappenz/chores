# Display Component

## Purpose

The `display/` directory owns the local Tk display. It renders chore status and local controls, and turns user clicks into chore commands.

## Responsibilities

- Create and manage the Tk window.
- Render the date/time, chore names, assigned people, and person images.
- Load person image metadata from `core.people` and image files from `assets/`.
- Render local controls such as the audio toggle.
- Convert UI interactions into calls to the public chore domain API.
- Refresh visual state after chore state changes.

## Non-Responsibilities

- Do not own chore state.
- Do not parse Discord messages.
- Do not call Gemini or wake-word APIs.
- Do not send Discord replies.
- Do not perform model invocation or audio generation directly.

## Public API

The Screen component should expose an async-friendly runner and a narrow interface:

- `run_screen(commands: ScreenCommandSink, state: ScreenStateSource) -> Awaitable[None]`: start the Tk screen runner and emit user commands through the provided command sink.
- `refresh(status: ChoresStatus) -> None`: redraw chore assignments, labels, and local state from the latest domain status.
- `set_speech_active(active: bool) -> None`: show whether the Gemini Live connection is currently active.
- `play_audio(audio: AudioPayload) -> Awaitable[None]`: play already-generated audio through the screen speaker.
- `close() -> None`: stop the screen runner and release local UI resources.

If Tk requires periodic pumping from the app event loop, that detail should remain inside `display/`. Other components should not call Tk widget methods directly.

## Inputs

The display consumes:

- current chore status
- chore command results
- audio-enabled state
- shutdown signals

## Outputs

The display emits:

- mark chore done command
- set audio enabled command
- optional status refresh request

Outputs should go through the chore domain API or an application message bus, not through Discord or speech internals.

## Assets

Person images are loaded from paths declared in the people TOML file and stored under `assets/`. Missing images should result in a local fallback image and should not crash the app.

## Testing

Automated tests should focus on pure helpers and adapter boundaries where possible. Full Tk rendering and click behavior may be manual or narrowly tested with mocks because it depends on the host display environment.
