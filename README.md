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

## Features

- Tracks chores for a group of people
- Displays the current date and time
- Integrates with Discord for chore management
- Uses voice announcements for chore assignments
