# Chores Domain

## Purpose

The `chores/` directory owns the core chore state and rules. It is the domain layer used by the display, Discord bot, speech agent, tests, and future components.

## Responsibilities

- Define chore identities, display names, aliases, and configured people.
- Use `core.people` as the source of truth for people and chore participation.
- Own `ChoresState` and persistence to `data/status.json`.
- Validate and normalize chore commands from adapters.
- Rotate assignments when a chore is marked done.
- Return structured results that adapters can present in their own medium.
- Expose read-only status queries.

## Non-Responsibilities

- Do not import Tk, Discord, Gemini, PyAudio, OpenAI, or ElevenLabs.
- Do not send Discord messages.
- Do not update Tk widgets.
- Do not call microphone or speaker APIs.
- Do not perform model invocation.
- Do not own Discord handles, image paths, or other service-specific person metadata.

## Public API

The domain should expose a small service API, likely named `ChoresService`:

- `get_status() -> ChoresStatus`: return current chore assignments and audio state.
- `mark_chore_done(chore: ChoreId | str, source: CommandSource) -> ChoreCommandResult`: normalize, validate, rotate, persist, and return the completion result.
- `set_audio_enabled(enabled: bool, source: CommandSource) -> ChoreCommandResult`: update the audio-announcement preference and return the new setting.
- `get_audio_enabled() -> bool`: return whether generated chore announcements are enabled.

Inputs from components should be normalized at the boundary. Unknown chores should produce a typed rejection result, not raise a generic exception.

## State

`ChoresState` stores assignment indexes into the chore participant list loaded by `core.people` for:

- Dishwasher
- Kitchen trash
- Wednesday trash

State should remain serializable to JSON. If the schema changes, the domain spec and migration behavior must be updated before implementation.

## Results And Events

Domain methods should return structured data, not preformatted component-specific strings. A chore completion result should include:

- chore id
- chore display name
- previous person
- next person
- whether state changed
- a short human-readable message suitable for default presentation

Adapters may format richer Discord, display, or speech responses from this result.

## Persistence

The domain owns reading and writing `data/status.json`. Persistence should be deterministic and covered by unit tests using an isolated data directory.

## Testing

Automated tests should cover:

- default state creation
- loading and saving state
- chore rotation
- status queries
- alias normalization
- unknown chore rejection
- audio-enabled state if it remains domain-owned

These tests must not import or initialize UI, Discord, speech, model, or audio components.
