from __future__ import annotations
import tkinter as tk
import os
import json
import sys
from typing import Callable, Awaitable, TYPE_CHECKING

if TYPE_CHECKING:
    from ui import ChoresUI
    from chores_bot import ChoresBot

class ChoreStatus:

    chore_people = ["Isabelle", "Guido", "Daniel", "Charlotte", "Thomas"]
    data_dir = "data"
    data_file = "status.json"

    def __init__(self):
        self.dishwasher_status = 0
        self.kitchen_status = 0
        self.wednesday_status = 0
        self.chores_ui: "ChoresUI | None" = None
        self.chores_bot: "ChoresBot | None" = None
        self.reply_callback: Callable[[str], Awaitable[None]] | None = None
        self.ui_refresh_callback: Callable[[], None] | None = None
        self.load_status()

    def load_status(self):
        file_name = os.path.join(ChoreStatus.data_dir, ChoreStatus.data_file)
        if os.path.exists(file_name):
            with open(file_name, "r") as file:
                self.status = json.load(file)
                self.dishwasher_status = self.status["dishwasher_status"]
                self.kitchen_status = self.status["kitchen_status"]
                self.wednesday_status = self.status["wednesday_status"]
            print(f"Loaded chore status: {self.dishwasher_status}/{self.kitchen_status}/{self.wednesday_status}") 
        else:
            self.save_status()

    def save_status(self):
        if not os.path.exists(ChoreStatus.data_dir):
            os.makedirs(ChoreStatus.data_dir)
        file_name = os.path.join(ChoreStatus.data_dir, ChoreStatus.data_file)
        with open(file_name, "w") as file:
            json.dump({"dishwasher_status": self.dishwasher_status, 
                       "kitchen_status": self.kitchen_status, 
                       "wednesday_status": self.wednesday_status}, file)

    def update_labels(self, dishwasher_status, kitchen_status, wednesday_status):
        self.dishwasher_status = dishwasher_status
        self.kitchen_status = kitchen_status
        self.wednesday_status = wednesday_status
        self.save_status()

    def set_reply_callback(self, callback: Callable[[str], Awaitable[None]]) -> None:
        self.reply_callback = callback

    def set_ui_refresh_callback(self, callback: Callable[[], None]) -> None:
        self.ui_refresh_callback = callback

    async def mark_chore_done(self, chore_type: str) -> None:
        from models import generate_speech, generate_audio
        from chores_bot import ChoresBot  # Mapping of names to discord IDs

        people_count = len(ChoreStatus.chore_people)

        if chore_type == "dishwasher":
            new_status = (self.dishwasher_status + 1) % people_count
            self.update_labels(new_status, self.kitchen_status, self.wednesday_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do the dishwasher")
        elif chore_type == "wednesday trash":
            new_status = (self.wednesday_status + 1) % people_count
            self.update_labels(self.dishwasher_status, self.kitchen_status, new_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do Wednesday trash")
        elif chore_type == "kitchen":
            print(f"Kitchen status: {self.kitchen_status}")
            new_status = (self.kitchen_status + 1) % people_count
            self.update_labels(self.dishwasher_status, new_status, self.wednesday_status)
            if self.reply_callback:
                await self.reply_callback(f"It's {ChoresBot.chore_people_discord[new_status]}'s turn to do kitchen trash")
        
        speech = generate_speech(chore_type, ChoreStatus.chore_people[new_status])
        generate_audio(speech)
        
        if self.ui_refresh_callback:
            self.ui_refresh_callback()

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
                await self.reply_callback(f"It's {chore_people_discord[self.dishwasher_status]}'s turn to do the dishwasher,\n"
                                   f"It's {chore_people_discord[self.kitchen_status]}'s turn to do the kitchen trash,\n"
                                   f"It's {chore_people_discord[self.wednesday_status]}'s turn to do the Wednesday trash.")
        else:
            if self.reply_callback:
                await self.reply_callback("Please use the words 'dishwasher', 'wednesday' or 'kitchen' to talk about what you need.")

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
    
    chore_status = ChoreStatus()
    chores_ui = ChoresUI(window, chore_status)
    chore_status.chores_ui = chores_ui
    
    chores_bot = ChoresBot(chore_status)
    chore_status.chores_bot = chores_bot
    chore_status.set_reply_callback(chores_bot.send_reply)
    chore_status.set_ui_refresh_callback(chores_bot.refresh_ui)
    
    chores_bot.run()

if __name__ == "__main__":
    chores()

 




    
