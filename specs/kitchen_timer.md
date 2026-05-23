# Kitchen Timer Component

## Purpose

The `kitchen_timer/` directory owns kitchen timer state and scheduling. It supports one active timer at a time and emits timer lifecycle events for the application supervisor.

## Responsibilities

- Parse timer durations such as `15:00`, `1:15:00`, and `15 minutes`.
- Start, read, and stop the single active kitchen timer.
- Report immutable timer status snapshots for adapters.
- Emit events one minute before the timer ends, when it finishes, and once per minute after finish until stopped.

## Non-Responsibilities

- Do not render Tk widgets.
- Do not call Gemini, OpenAI, ElevenLabs, Discord, or Reachy directly.
- Do not own microphone, speaker, or robot state.
- Do not own chore assignments.

## Public API

The component exposes:

- `KitchenTimerService.start_timer(time_period: str, name: str) -> KitchenTimerCommandResult`
- `KitchenTimerService.read_timer() -> KitchenTimerCommandResult`
- `KitchenTimerService.stop_timer() -> KitchenTimerCommandResult`
- `KitchenTimerService.get_status() -> KitchenTimerStatus | None`
- `KitchenTimerService.events() -> asyncio.Queue[KitchenTimerEvent]`
- `KitchenTimerService.is_active() -> bool`

`kitchen_agent.py` owns cross-component reactions to timer events:

- update the display status card
- keep Gemini Live from idle-sleeping while a timer is active
- wake Reachy one minute before finish
- ask Gemini Live to announce finished and repeated finished events
- use generated audio as a fallback if Gemini Live is unavailable

## Testing

Automated tests should cover duration parsing, single-active-timer behavior, start/read/stop commands, status snapshots, and event scheduling with fake clocks/sleeps. Tests must not call model, audio, Discord, or hardware services.
