## What it does

Kitchen agent for a family. It tracks chores, runs a local screen, talks through Discord, and can optionally run a wake-word speech agent.

## Structure

The app is split into top-level components:

- `chores/`: chore domain state, rules, persistence, and command results.
- `display/`: Tk screen and speaker output.
- `discord_bot/`: Discord connection, parsing, and replies.
- `speech_agent/`: wake word, Gemini Live, microphone, speaker playback, and Gemini tools.
- `core/`: people data, shared model/audio helpers, config, and shared types.

The main entry point is `kitchen_agent.py`.

## Dependencies

This package uses uv. To run it:
- Install uv
- Make sure your python installation supports tkinter
- Create a Discord bot and register the bot with your family's Discord server
- Create a `.env` file with valid tokens for Discord, OpenAI, ElevenLabs, and Gemini if the speech agent is enabled

Then run the chores app with:
```
uv run --env-file .env python3 kitchen_agent.py
```

## Reachy Mini daemon (Mac mini deployment)

The chores app connects to a local Reachy Mini daemon. On a Mac mini, install the daemon as a per-user LaunchAgent so `launchd` keeps it running.

Add daemon settings to `.env` (Makefile loads `.env` automatically):

```bash
REACHY_DAEMON_MODE=real
REACHY_DAEMON_LOG_LEVEL=INFO
```

Use `sim` or `mockup-sim` on a dev machine without hardware.

Install, manage, and inspect the daemon:

```bash
make reachy-daemon-install
make reachy-daemon-status
make reachy-daemon-logs
make reachy-daemon-stop
make reachy-daemon-start
make reachy-daemon-uninstall
make reachy-daemon-print
```

Changing `REACHY_DAEMON_MODE` requires reinstalling: `make reachy-daemon-install`.

Optional daemon env vars: `REACHY_DAEMON_NO_MEDIA`, `REACHY_DAEMON_PORT`, `REACHY_DAEMON_EXTRA_ARGS`, `REACHY_DAEMON_LOG_DIR`.

The app retries daemon connection in the background (`REACHY_CONNECT_RETRY_SECONDS`, `REACHY_RECONNECT_ON_FAILURE`). If the daemon starts after the app, Reachy reconnects automatically.

## Features

- Tracks chores for a group of people
- Displays the current date and time
- Integrates with Discord for chore management
- Uses voice announcements for chore assignments
