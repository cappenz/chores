from __future__ import annotations
import tkinter as tk
import os
import json
import sys
from dataclasses import dataclass, asdict
from typing import Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from ui import ChoresUI
    from chores_bot import ChoresBot

@dataclass(frozen=True)
class ChoresState:
    dishwasher_status: int
    kitchen_status: int
    wednesday_status: int

# This is the main class that handles:
# 1. Who has to do what chores
# 2. What happens when a chore is marked as done
# It also takes care of initializing the other modules.

class ChoresApp:

    chore_people = ["Isabelle", "Guido", "Daniel", "Charlotte", "Thomas"]
    data_dir = "data"
    data_file = "status.json"

    def __init__(self):
        self.load_state()
        self.audio_enabled = True
        self.chores_ui: "ChoresUI | None" = None
        self.chores_bot: "ChoresBot | None" = None
        self.reply_callback: Callable[[str], Awaitable[None]] | None = None
        self.ui_refresh_callback: Callable[[], None] | None = None

    # Three functions to update the chores data and load/save it to disk

    def load_state(self) -> None:
        file_name = os.path.join(ChoresApp.data_dir, ChoresApp.data_file)
        if os.path.exists(file_name):
            with open(file_name, "r") as file:
                status = json.load(file)
                self.state = ChoresState(**status)
            print(f"Loaded chore status: {self.state.dishwasher_status}/{self.state.kitchen_status}/{self.state.wednesday_status}") 
        else:
            self.state = ChoresState(0, 0, 0)
            self.save_state()

    def save_state(self) -> None:
        if not os.path.exists(ChoresApp.data_dir):
            os.makedirs(ChoresApp.data_dir)
        file_name = os.path.join(ChoresApp.data_dir, ChoresApp.data_file)
        with open(file_name, "w") as file:
            json.dump(asdict(self.state), file)

    def update_state(self, dishwasher_status, kitchen_status, wednesday_status):
        self.state = ChoresState(dishwasher_status, kitchen_status, wednesday_status)
        self.save_state()

    # These methods allow external components (like the Discord bot or UI) to register callback functions.
    # 
    # set_reply_callback: Registers an async function that sends messages to Discord. It's async because
    # sending network messages takes time and we don't want to block. The function takes a message string
    # and returns a coroutine (Awaitable[None]) that must be awaited when called.
    #
    # set_ui_refresh_callback: Registers a regular (synchronous) function that updates the UI display.
    # This is synchronous because UI updates are typically fast and happen on the main thread.

    def set_reply_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self.reply_callback = callback

    def set_ui_refresh_callback(self, callback: Callable[[], None]) -> None:
        self.ui_refresh_callback = callback

    # This method is called when a chore is marked as done. 
    # - Input is one of "dishwasher", "wednesday trash", or "kitchen"
    # - It updates the state, the UI, sends a message to Discord, and plays an audio file.

    async def mark_chore_done(self, chore_type: str) -> None:
        from models import generate_and_play_audio_async
        from chores_bot import ChoresBot  # Mapping of names to discord IDs

        people_count = len(ChoresApp.chore_people)

        if chore_type == "dishwasher":
            new_status = (self.state.dishwasher_status + 1) % people_count
            self.update_state(new_status, self.state.kitchen_status, self.state.wednesday_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do the dishwasher")
        elif chore_type == "wednesday trash":
            new_status = (self.state.wednesday_status + 1) % people_count
            self.update_state(self.state.dishwasher_status, self.state.kitchen_status, new_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do Wednesday trash")
        elif chore_type == "kitchen":
            print(f"Kitchen status: {self.state.kitchen_status}")
            new_status = (self.state.kitchen_status + 1) % people_count
            self.update_state(self.state.dishwasher_status, new_status, self.state.wednesday_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do kitchen trash")
        
        if self.audio_enabled:
            await generate_and_play_audio_async(chore_type, ChoresApp.chore_people[new_status])
        
        if self.ui_refresh_callback:
            self.ui_refresh_callback()

    # This method reacts to an action from the user. It may be from Discord, voice commands, or a web interface.
    # Input is some text string, right now it does keyword matching.

    async def on_message(self, message_content: str) -> None:
        chore_people_discord = ["Isabelle, <@663405556312047633>", "Guido, <@339570174451646469>", "Daniel, <@341262399531122689>", "Charlotte, <@340964475135983618>", "Thomas,<@869351880155885600>"]
        
        content_lower = message_content.lower()
        
        if 'dish' in content_lower:
            await self.mark_chore_done("dishwasher")
        elif 'wednesday' in content_lower or 'outside' in content_lower:
            await self.mark_chore_done("wednesday trash")
        elif 'kitchen' in content_lower:
            await self.mark_chore_done("kitchen")
        elif 'info' in content_lower or 'status' in content_lower:
            if self.reply_callback:
                await self.reply_callback(f"It's {chore_people_discord[self.state.dishwasher_status]}'s turn to do the dishwasher,\n"
                                   f"It's {chore_people_discord[self.state.kitchen_status]}'s turn to do the kitchen trash,\n"
                                   f"It's {chore_people_discord[self.state.wednesday_status]}'s turn to do the Wednesday trash.")
        else:
            if self.reply_callback:
                await self.reply_callback("Please use the words 'dishwasher', 'wednesday' or 'kitchen' to talk about what you need.")

# This is the main entry point for the app. It creates the UI and the Discord bot,
# and sets up the callbacks.

def chores():
    from ui import ChoresUI
    from chores_bot import ChoresBot
    
    window = tk.Tk()
    
    window_mode = os.getenv("WINDOWMODE")
    if window_mode:
        try:
            dimensions = window_mode.replace(" ", "").split("x")
            width = int(dimensions[0])
            height = int(dimensions[1])
            window.geometry(f"{width}x{height}")
            window.attributes('-fullscreen', False)
        except (ValueError, IndexError):
            print("Invalid WINDOWMODE format. Expected format: '1280 x 800'")
            sys.exit(1)
    else:
        window.attributes('-fullscreen', True)
    
    chores_app = ChoresApp()
    chores_ui = ChoresUI(window, chores_app)
    chores_app.chores_ui = chores_ui
    
    chores_bot = ChoresBot(chores_app)
    chores_app.chores_bot = chores_bot
    chores_app.set_reply_callback(chores_bot.send_reply)
    chores_app.set_ui_refresh_callback(chores_bot.refresh_ui)
    
    chores_bot.run()

if __name__ == "__main__":
    chores()
