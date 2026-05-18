# Discord Bot Component

## Purpose

The `discord_bot/` directory owns Discord connectivity. It adapts Discord messages into chore domain commands and sends Discord responses based on command results.

## Responsibilities

- Create and run the Discord client.
- Manage Discord intents and authentication.
- Track the channel used for replies.
- Parse inbound Discord messages into chore commands or status requests.
- Load Discord user IDs/handles from `core.people`.
- Format chore domain results for Discord users.
- Send Discord replies.

## Non-Responsibilities

- Do not own chore state.
- Do not update Tk widgets.
- Do not call speech-agent internals.
- Do not call Gemini or wake-word APIs.
- Do not generate chore announcement audio directly.

## Public API

The component should expose:

- `run_discord_bot(commands: DiscordCommandSink, config: DiscordConfig) -> Awaitable[None]`: start the Discord client and emit parsed user commands through the provided command sink.
- `send_reply(message: str) -> Awaitable[None]`: send a formatted response using the component-owned default or last-seen Discord channel.
- `close() -> Awaitable[None]`: disconnect the Discord client and release resources.

Inbound message handling should call the chore domain API or emit application commands. It should not call display or speech APIs.

## Inputs

The Discord bot consumes:

- Discord messages
- chore command results
- status results
- shutdown signals

## Outputs

The Discord bot emits:

- mark chore done command
- chore status request
- optional unknown-command response

Discord-specific formatting, including mentions, belongs in this component or in a Discord formatter owned by this component. Discord mention data comes from `core.people`; formatted mention strings should not live in the chore domain.

## Configuration

Required environment:

- `DISCORD_TOKEN`

Optional configuration may include guild/channel defaults if the current automatic channel selection becomes too implicit.

## Testing

Automated tests should cover message parsing and response formatting with fake Discord objects. Tests must not write to Discord. Real Discord login or write behavior must be manual.
