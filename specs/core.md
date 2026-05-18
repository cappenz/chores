# Core Infrastructure

## Purpose

The `core/` directory owns shared infrastructure used by multiple components. It includes people data loading, cross-component types, config helpers, logging, and shared model/audio helpers.

## Responsibilities

- Load people data from a TOML file.
- Expose `core.people` as the source of truth for family member identities and service metadata.
- Own shared message and result types used at component boundaries.
- Own shared configuration loading where it prevents duplication.
- Own shared logging setup.
- Own model invocation helpers that are used by more than one component.

## Non-Responsibilities

- Do not own chore state or chore rules.
- Do not contain UI rendering.
- Do not contain Discord client code.
- Do not contain wake-word or Gemini Live session loops.
- Do not become a dumping ground for unrelated helpers.

## People Data

People data should live in a TOML file, for example `data/people.toml`. The file is independent of any one service and should include:

- stable person id
- display name
- chore participation/order
- Discord user id or handle metadata
- image asset path under `assets/`

`core.people` should expose:

- `load_people(path: Path) -> PeopleRegistry`: load and validate people data from TOML.
- `get_person(person_id: PersonId) -> Person`: return a person by stable id.
- `get_chore_participants() -> list[Person]`: return people who participate in chore rotation order.
- `get_discord_identity(person_id: PersonId) -> DiscordIdentity | None`: return Discord metadata for adapters.
- `get_image_asset(person_id: PersonId) -> Path | None`: return the configured display image path.

## Assets

Person images and other local media assets should live under `assets/`. The TOML file stores paths relative to the repo or configured asset root. Components should handle missing assets gracefully.

## Model Invocation

Shared model invocation helpers belong here when more than one component may use them. For example:

- OpenAI text generation for chore announcements.
- ElevenLabs speech generation and playback wrappers.
- Future common LLM client setup or retry behavior.

Component-specific model behavior should stay with that component. Gemini Live streaming and tool-call handling belong in `speech_agent/`, not `core/`, because they are part of the speech agent runtime.

## Testing

Automated tests should cover people TOML loading, validation failures, asset path resolution, pure utilities, config parsing, and mocked model wrappers. Tests must not call paid model services or audio playback.
