This package uses uv. To run it:
- Install uv
- Make sure you have python 3.13 installed
- Make sure your python 3.13 installation supports tkinter
- Create a .env file with a valid DISCORD_TOKEN

Then run the chores app with:
```
uv run --env-file .env python3 chores.py
```

## Features

- Tracks chores for a group of people
- Displays the current date and time in Japanese format (e.g., 2025年3月14日 15時30分45秒)
- Integrates with Discord for chore management
- Uses voice announcements for chore assignments
