from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

import discord
from discord.ext import tasks

from chores import ChoreCommandResult, ChoresService, ChoresStatus

ResultCallback = Callable[[ChoreCommandResult], Awaitable[None] | None]
StatusCallback = Callable[[], None]
ReadyCallback = Callable[[], Awaitable[None] | None]


class ChoresBot:
    def __init__(
        self,
        chores: ChoresService,
        *,
        after_result: ResultCallback | None = None,
        refresh_ui: StatusCallback | None = None,
        on_ready_callback: ReadyCallback | None = None,
    ) -> None:
        self.chores = chores
        self.after_result = after_result
        self.refresh_ui = refresh_ui
        self.on_ready_callback = on_ready_callback
        self._ready_callback_started = False
        self.last_channel = None
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.setup_events()

    def setup_events(self) -> None:
        @self.client.event
        async def on_ready():
            if not self.my_loop.is_running():
                self.my_loop.start()
            print(f"We have logged in as {self.client.user}")
            if self.last_channel is None:
                self._set_default_channel()
            if self.on_ready_callback and not self._ready_callback_started:
                self._ready_callback_started = True
                callback_result = self.on_ready_callback()
                if callback_result is not None:
                    await callback_result

        @self.client.event
        async def on_message(message):
            if message.author == self.client.user:
                return
            self.last_channel = message.channel
            await self.handle_text(message.content)

        @tasks.loop(seconds=0.05)
        async def my_loop():
            if self.refresh_ui:
                self.refresh_ui()

        self.my_loop = my_loop

    async def handle_text(self, message_content: str) -> ChoreCommandResult | None:
        result = parse_discord_message(self.chores, message_content)
        if result is None:
            return None
        await self.send_reply(format_result_for_discord(self.chores, result))
        await self._notify_result(result)
        return result

    async def send_reply(self, message: str) -> None:
        if self.last_channel:
            await self.last_channel.send(message)

    def run(self) -> None:
        token = os.getenv("DISCORD_TOKEN")
        if token is None:
            raise RuntimeError("No DISCORD_TOKEN found")
        self.client.run(token)

    async def close(self) -> None:
        await self.client.close()

    def schedule_handle_text(self, message_content: str) -> None:
        import asyncio

        loop = self.client.loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self.handle_text(message_content), loop)

    async def _notify_result(self, result: ChoreCommandResult) -> None:
        if self.after_result is None:
            return
        callback_result = self.after_result(result)
        if callback_result is not None:
            await callback_result

    def _set_default_channel(self) -> None:
        for guild in self.client.guilds:
            if guild.name != "Appenzellers":
                continue
            for channel in guild.text_channels:
                if channel.permissions_for(guild.me).send_messages:
                    self.last_channel = channel
                    print(f"Set default channel to: {channel.name} in {guild.name}")
                    return


def parse_discord_message(chores: ChoresService, message_content: str) -> ChoreCommandResult | None:
    content_lower = message_content.lower()
    if "info" in content_lower or "status" in content_lower:
        return ChoreCommandResult(
            ok=True,
            message=format_status_for_discord(chores.get_status(), chores),
            status=chores.get_status(),
        )

    result = chores.mark_chore_done(message_content, source="discord")
    return result


def format_result_for_discord(chores: ChoresService, result: ChoreCommandResult) -> str:
    if result.chore_id is None:
        return result.message
    if not result.ok:
        return result.message
    mention = _person_mention(chores, result.next_person_id)
    return f"It's {mention}'s turn to do the {result.chore_display_name}"


def format_status_for_discord(status: ChoresStatus, chores: ChoresService) -> str:
    lines = []
    for assignment in status.assignments:
        mention = _person_mention(chores, assignment.person_id)
        lines.append(f"It's {mention}'s turn to do the {assignment.chore_display_name}")
    return ",\n".join(lines) + "."


def _person_mention(chores: ChoresService, person_id: str | None) -> str:
    if person_id is None:
        return "someone"
    person = chores.people.get_person(person_id)
    discord_identity = chores.people.get_discord_identity(person_id)
    if discord_identity is None:
        return person.display_name
    return f"{person.display_name}, {discord_identity.mention}"

