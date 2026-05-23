from __future__ import annotations

import asyncio
import datetime
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Literal


TimerEventKind = Literal["wake_soon", "finished", "repeat_finished", "stopped"]


@dataclass(frozen=True)
class KitchenTimerStatus:
    name: str
    started_at: datetime.datetime
    ends_at: datetime.datetime
    remaining_seconds: int
    expired: bool = False


@dataclass(frozen=True)
class KitchenTimerEvent:
    kind: TimerEventKind
    status: KitchenTimerStatus | None


@dataclass(frozen=True)
class KitchenTimerCommandResult:
    ok: bool
    message: str
    status: KitchenTimerStatus | None = None


class KitchenTimerService:
    def __init__(
        self,
        *,
        now: Callable[[], datetime.datetime] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
        repeat_seconds: float = 60.0,
    ) -> None:
        self._now = now or datetime.datetime.now
        self._sleep = sleep or asyncio.sleep
        self._repeat_seconds = repeat_seconds
        self._event_queue: asyncio.Queue[KitchenTimerEvent] = asyncio.Queue()
        self._active: KitchenTimerStatus | None = None
        self._event_task: asyncio.Task | None = None
        self._generation = 0

    def start_timer(self, time_period: str, name: str) -> KitchenTimerCommandResult:
        timer_name = name.strip()
        if not timer_name:
            return KitchenTimerCommandResult(False, "Please provide a timer name.")
        if self._active is not None:
            return KitchenTimerCommandResult(
                False,
                (
                    f"A timer named {self._active.name} is already active. "
                    "Stop it before starting a new timer."
                ),
                self.get_status(),
            )

        try:
            duration_seconds = parse_duration_seconds(time_period)
        except ValueError as error:
            return KitchenTimerCommandResult(False, str(error))

        started_at = self._now()
        ends_at = started_at + datetime.timedelta(seconds=duration_seconds)
        status = KitchenTimerStatus(
            name=timer_name,
            started_at=started_at,
            ends_at=ends_at,
            remaining_seconds=duration_seconds,
        )
        self._active = status
        self._generation += 1
        self._schedule_events(self._generation)
        return KitchenTimerCommandResult(
            True,
            f"Started timer {timer_name} for {format_remaining(duration_seconds)}.",
            status,
        )

    def read_timer(self) -> KitchenTimerCommandResult:
        status = self.get_status()
        if status is None:
            return KitchenTimerCommandResult(True, "No timer is active.")
        if status.expired:
            return KitchenTimerCommandResult(True, f"{status.name} is finished.", status)
        return KitchenTimerCommandResult(
            True,
            f"{status.name} has {format_remaining(status.remaining_seconds)} left.",
            status,
        )

    def stop_timer(self) -> KitchenTimerCommandResult:
        status = self.get_status()
        if status is None:
            return KitchenTimerCommandResult(True, "No timer is active.")

        self._generation += 1
        self._active = None
        if self._event_task is not None:
            self._event_task.cancel()
            self._event_task = None
        self._event_queue.put_nowait(KitchenTimerEvent("stopped", status))
        return KitchenTimerCommandResult(True, f"Stopped the {status.name} timer.")

    def get_status(self) -> KitchenTimerStatus | None:
        if self._active is None:
            return None
        return self._status_at(self._now())

    def events(self) -> asyncio.Queue[KitchenTimerEvent]:
        return self._event_queue

    def is_active(self) -> bool:
        return self._active is not None

    def _status_at(self, now: datetime.datetime) -> KitchenTimerStatus:
        assert self._active is not None
        remaining_seconds = max(0, int((self._active.ends_at - now).total_seconds()))
        return KitchenTimerStatus(
            name=self._active.name,
            started_at=self._active.started_at,
            ends_at=self._active.ends_at,
            remaining_seconds=remaining_seconds,
            expired=remaining_seconds == 0,
        )

    def _schedule_events(self, generation: int) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._event_task = loop.create_task(self._run_events(generation))

    async def _run_events(self, generation: int) -> None:
        try:
            status = self.get_status()
            if status is None:
                return
            if status.remaining_seconds > 60:
                await self._sleep(status.remaining_seconds - 60)
                if not self._is_generation_active(generation):
                    return
                self._event_queue.put_nowait(KitchenTimerEvent("wake_soon", self.get_status()))

            status = self.get_status()
            if status is None:
                return
            if status.remaining_seconds > 0:
                await self._sleep(status.remaining_seconds)
            if not self._is_generation_active(generation):
                return

            self._event_queue.put_nowait(KitchenTimerEvent("finished", self.get_status()))
            while self._is_generation_active(generation):
                await self._sleep(self._repeat_seconds)
                if self._is_generation_active(generation):
                    self._event_queue.put_nowait(KitchenTimerEvent("repeat_finished", self.get_status()))
        except asyncio.CancelledError:
            pass

    def _is_generation_active(self, generation: int) -> bool:
        return self._generation == generation and self._active is not None


def parse_duration_seconds(value: str) -> int:
    text = value.strip().casefold()
    if not text:
        raise ValueError("Please provide a timer duration.")

    if re.fullmatch(r"\d+", text):
        seconds = int(text)
    elif re.fullmatch(r"\d{1,2}:\d{2}", text):
        minutes, seconds_part = (int(part) for part in text.split(":"))
        if seconds_part >= 60:
            raise ValueError("Timer seconds must be less than 60.")
        seconds = minutes * 60 + seconds_part
    elif re.fullmatch(r"\d{1,2}:\d{2}:\d{2}", text):
        hours, minutes, seconds_part = (int(part) for part in text.split(":"))
        if minutes >= 60 or seconds_part >= 60:
            raise ValueError("Timer minutes and seconds must be less than 60.")
        seconds = hours * 3600 + minutes * 60 + seconds_part
    else:
        seconds = _parse_words_duration(text)

    if seconds <= 0:
        raise ValueError("Timer duration must be greater than zero.")
    return seconds


def _parse_words_duration(text: str) -> int:
    matches = re.findall(
        r"(\d+)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)",
        text,
    )
    if not matches:
        raise ValueError("Use a timer duration like 15:00, 1:15:00, or 15 minutes.")

    total = 0
    for amount_text, unit in matches:
        amount = int(amount_text)
        if unit.startswith(("hour", "hr", "h")):
            total += amount * 3600
        elif unit.startswith(("minute", "min", "m")):
            total += amount * 60
        else:
            total += amount
    return total


def format_remaining(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds_part:02d}"
    return f"{minutes}:{seconds_part:02d}"
