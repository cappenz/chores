## What is does

Family Chores board with silly announcements. It is excellent.

## Structure

The application consists of three main classes:

- **ChoresApp** (`chores.py`): Core application logic that manages chore state, coordinates between UI and Discord bot, and handles chore completion. Maintains state for three chores (dishwasher, kitchen trash, Wednesday trash) and rotates assignments among family members.

- **ChoresUI** (`ui.py`): Tkinter-based graphical interface that displays the current date/time and shows which person is assigned to each chore. Displays person images and allows clicking to mark chores as done.

- **ChoresBot** (`chores_bot.py`): Discord bot integration that listens for messages, processes chore-related commands, and sends replies. Also manages UI refresh loop to keep the display updated.

- **models.py**: Contains voice announcement functionality using OpenAI to generate speech text and ElevenLabs to convert it to audio and play it.

The main entry point (`chores()` function in `chores.py`) initializes all components and connects them via callback functions.

## Dependencies

This package uses uv. To run it:
- Install uv
- Make sure your python installation supports tkinter
- Create a Discord bot and register the bot with your familie's Discord server
- Create a .env file with valid tokens for Discord, OpenAI and ElevenLabs

Then run the chores app with:
```
uv run --env-file .env python3 chores.py
```

## Features

- Tracks chores for a group of people
- Displays the current date and time
- Integrates with Discord for chore management
- Uses voice announcements for chore assignments
