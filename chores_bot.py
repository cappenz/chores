import discord
from discord.ext import tasks
import os
from chores import ChoresApp

token = os.getenv("DISCORD_TOKEN")
if token is None:
    print("No token found")
    exit()


# This class handles the Discord bot.

class ChoresBot:

    chore_people_discord: list[str] = [
        "Isabelle, <@663405556312047633>",
        "Guido, <@339570174451646469>",
        "Daniel, <@341262399531122689>",
        "Charlotte, <@340964475135983618>",
        "Thomas,<@869351880155885600>"
    ]

    def __init__(self, chores_app: ChoresApp):
        self.chores_app = chores_app
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
            if self.last_channel is None:
                for guild in self.client.guilds:
                    if guild.name == "Appenzellers":
                        for channel in guild.text_channels:
                            if channel.permissions_for(guild.me).send_messages:
                                self.last_channel = channel
                                print(f'Set default channel to: {channel.name} in {guild.name}')
                                break
                        if self.last_channel:
                            break

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            self.last_channel = message.channel
            await self.chores_app.on_message(message.content)

        @tasks.loop(seconds=0.05)
        async def myLoop():
            if self.chores_app.chores_ui:
                self.chores_app.chores_ui.window.update_idletasks()
                self.chores_app.chores_ui.refresh_labels()
                self.chores_app.chores_ui.window.update()
        
        self.myLoop = myLoop

    async def send_reply(self, message: str):
        if self.last_channel:
            await self.last_channel.send(message)

    def refresh_ui(self):
        if self.chores_app.chores_ui:
            self.chores_app.chores_ui.refresh_labels()
            self.chores_app.chores_ui.window.update_idletasks()
            self.chores_app.chores_ui.window.update()

    def schedule_on_message(self, message_content: str):
        import asyncio
        loop = self.client.loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self.chores_app.on_message(message_content),
                loop
            )

    def run(self):
        self.client.run(token)





