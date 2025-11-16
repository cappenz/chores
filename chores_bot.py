import discord
from discord.ext import tasks
import os
from chores import ChoreStatus

token = os.getenv("DISCORD_TOKEN")
if token is None:
    print("No token found")
    exit()

class ChoresBot:

    chore_people_discord: list[str] = [
        "Isabelle, <@663405556312047633>",
        "Guido, <@339570174451646469>",
        "Daniel, <@341262399531122689>",
        "Charlotte, <@340964475135983618>",
        "Thomas,<@869351880155885600>"
    ]

    def __init__(self, chore_status: ChoreStatus):
        self.chore_status = chore_status
        self.last_channel = None
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.setup_events()
        
    def setup_events(self):
        @self.client.event
        async def on_ready():
            if not self.myLoop.is_running():
                self.myLoop.start()
            print(f'We have logged in as {self.client.user}')

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            self.last_channel = message.channel
            await self.chore_status.on_message(message.content)

        @tasks.loop(seconds=1)
        async def myLoop():
            if self.chore_status.chores_ui:
                self.chore_status.chores_ui.window.update_idletasks()
                self.chore_status.chores_ui.refresh_labels()
                self.chore_status.chores_ui.window.update()
        
        self.myLoop = myLoop

    async def send_reply(self, message: str):
        if self.last_channel:
            await self.last_channel.send(message)

    def refresh_ui(self):
        if self.chore_status.chores_ui:
            self.chore_status.chores_ui.refresh_labels()
            self.chore_status.chores_ui.window.update_idletasks()
            self.chore_status.chores_ui.window.update()

    def run(self):
        self.client.run(token)





