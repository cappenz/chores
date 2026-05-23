from __future__ import annotations

import asyncio
import datetime

from kitchen_timer import KitchenTimerService, format_remaining, parse_duration_seconds


def test_parse_duration_seconds_accepts_timer_formats():
    assert parse_duration_seconds("15:00") == 900
    assert parse_duration_seconds("1:02:03") == 3723
    assert parse_duration_seconds("15 minutes") == 900
    assert parse_duration_seconds("1 hour 5 minutes 3 seconds") == 3903
    assert parse_duration_seconds("45") == 45


def test_parse_duration_seconds_rejects_invalid_values():
    for value in ("", "soon", "0", "12:99", "1:75:00"):
        try:
            parse_duration_seconds(value)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected ValueError for {value!r}")


def test_format_remaining_uses_countdown_style():
    assert format_remaining(65) == "1:05"
    assert format_remaining(3661) == "1:01:01"
    assert format_remaining(0) == "0:00"


def test_start_read_and_stop_timer():
    now = datetime.datetime(2026, 5, 22, 13, 0, 0)
    service = KitchenTimerService(now=lambda: now)

    started = service.start_timer("15:00", "Pizza is Ready")

    assert started.ok
    assert started.status is not None
    assert started.status.name == "Pizza is Ready"
    assert started.status.remaining_seconds == 900
    assert service.read_timer().message == "Pizza is Ready has 15:00 left."

    stopped = service.stop_timer()

    assert stopped.ok
    assert stopped.message == "Stopped the Pizza is Ready timer."
    assert service.get_status() is None


def test_only_one_timer_can_be_active():
    now = datetime.datetime(2026, 5, 22, 13, 0, 0)
    service = KitchenTimerService(now=lambda: now)

    service.start_timer("5:00", "Tea")
    second = service.start_timer("10:00", "Pizza")

    assert not second.ok
    assert "already active" in second.message
    assert service.get_status().name == "Tea"


def test_timer_status_expires_from_clock():
    current = datetime.datetime(2026, 5, 22, 13, 0, 0)

    def now():
        return current

    service = KitchenTimerService(now=now)
    service.start_timer("1:00", "Cookies")
    current = datetime.datetime(2026, 5, 22, 13, 1, 2)

    status = service.get_status()

    assert status is not None
    assert status.expired
    assert status.remaining_seconds == 0


def test_timer_events_wake_finish_and_repeat():
    async def scenario():
        current = datetime.datetime(2026, 5, 22, 13, 0, 0)
        sleep_calls = []

        async def sleep(seconds: float) -> None:
            nonlocal current
            sleep_calls.append(seconds)
            current += datetime.timedelta(seconds=seconds)
            if len(sleep_calls) > 3:
                await asyncio.Future()

        service = KitchenTimerService(now=lambda: current, sleep=sleep, repeat_seconds=60.0)
        service.start_timer("1:01", "Pasta")

        await asyncio.sleep(0)
        events = service.events()

        first = events.get_nowait()
        second = events.get_nowait()
        third = events.get_nowait()
        service.stop_timer()

        return sleep_calls, first.kind, second.kind, third.kind

    sleep_calls, first_kind, second_kind, third_kind = asyncio.run(scenario())

    assert sleep_calls[:3] == [1, 60, 60.0]
    assert (first_kind, second_kind, third_kind) == ("wake_soon", "finished", "repeat_finished")
