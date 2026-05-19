# Kitchen Agent Overview

## Purpose

This `chores` app is a full agentic helper in the kitchen of a family.
It can interact with family members via:
- A speech-driven agent that can converse with the end user using a speech-to-speech model
- A screen to show information to the user and play audio
- A Discord bot that allows communicating with the agent via Discord
It runs on a macMini.

Currently the core functionality of the agent is to answer questions and to track who needs
to do which chores next.

## Top-Level Code Structure

The software is organized around these top-level directories:

- `chores/`: domain state, chore rules, persistence, and command results.
- `display/`: Tk UI component.
- `discord_bot/`: Discord component.
- `speech_agent/`: wake-word and Gemini Live component.
- `reachy/`: Reachy Mini companion component.
- `core/`: shared infrastructure such as people loading, model invocation, config, message types, logging, and cross-component utilities.

The top-level Python entry point should be intentionally short. It should construct shared services, start the component runners as asyncio tasks, coordinate shutdown, and avoid owning domain logic.

## Component Boundaries

No component may reach into another component's internals. Cross-component interaction must happen through public APIs, command objects, event objects, or callback interfaces declared for that purpose.

The `chores/` domain owns chore state and chore behavior. The other components are adapters:

- `display/` turns local clicks into chore commands and renders chore state.
- `discord_bot/` turns Discord messages into chore commands and sends Discord responses.
- `speech_agent/` turns Gemini tool calls into chore commands and speaks assistant responses.
- `reachy/` turns speech lifecycle events into robot motion and vision behavior.

The adapters may call the public API of `chores/`. The `chores/` domain must not import `display/`, `discord_bot/`, `speech_agent/`, or `reachy/`.

## Architecture

The main concurrent components are:

- UI display runner.
- Discord bot runner.
- Speech agent runner.
- Reachy Mini companion runner, when enabled.

These should run as asyncio tasks under one application supervisor where practical. Blocking libraries, especially PyAudio, may use worker threads behind the owning component boundary. If a component requires a dedicated OS thread later, it must still communicate through the same public APIs/messages and marshal domain calls safely back to the owning event loop.

## Specs

- `specs/chores.md`: chore domain, state, commands, events, and persistence.
- `specs/display.md`: Tk display component.
- `specs/discord_bot.md`: Discord component.
- `specs/speech_agent.md`: wake-word and Gemini Live component.
- `specs/reachy.md`: Reachy Mini companion component.
- `specs/core.md`: shared infrastructure and people data.
- `specs/audio.md`: generated chore announcement audio.

## Testing Policy

Always use `make test` for the regular automated test suite. Do not use `uv run pytest` directly for normal validation because manual tests may involve paid services, audio hardware, or external integrations.

Automated tests must not call OpenAI, Gemini, ElevenLabs, audio playback, microphone input, or paid/external write-capable services. They may test pure parsing, domain behavior, API boundaries, and mocked adapters.

Manual tests are explicit one-case entry points. Manual audio, microphone, Gemini Live, Discord write, and other hardware or paid-service checks must be marked as manual and excluded from `make test`.
