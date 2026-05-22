from __future__ import annotations

import asyncio
from unittest.mock import patch

from kitchen_agent import prepare_reachy_for_startup
from reachy.companion import (
    NoOpReachyCompanion,
    ReachyConfig,
    ReachyEmotion,
    RetryingReachyCompanion,
    SdkReachyCompanion,
    _smooth_target,
    run_reachy_companion,
)


class FakeMini:
    def __init__(self) -> None:
        self.calls = []

    def enable_motors(self) -> None:
        self.calls.append(("enable_motors",))

    def goto_target(self, **kwargs) -> None:
        self.calls.append(("goto_target", kwargs))

    def set_target(self, **kwargs) -> None:
        self.calls.append(("set_target", kwargs))

    def goto_sleep(self) -> None:
        self.calls.append(("goto_sleep",))

    def close(self) -> None:
        self.calls.append(("close",))


def fake_head_pose(**kwargs):
    return {"head_pose": kwargs}


def test_disabled_reachy_uses_noop_companion():
    companion = run_reachy_companion(ReachyConfig(enabled=False))

    assert isinstance(companion, NoOpReachyCompanion)


def test_enabled_reachy_uses_retrying_companion():
    companion = run_reachy_companion(ReachyConfig(enabled=True))

    assert isinstance(companion, RetryingReachyCompanion)


def test_retrying_companion_reconnects_after_initial_failure():
    mini = FakeMini()
    sdk = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )
    attempts = {"count": 0}

    def fake_create(_config: ReachyConfig) -> SdkReachyCompanion:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise ConnectionError("daemon unavailable")
        return sdk

    companion = RetryingReachyCompanion(
        ReachyConfig(enabled=True, face_tracking_enabled=False, connect_retry_seconds=0.01)
    )

    async def run() -> None:
        with patch("reachy.companion._create_sdk_companion", side_effect=fake_create):
            await companion.wake()
            for _ in range(20):
                if companion._companion is not None:
                    break
                await asyncio.sleep(0.02)
            await companion.close()

    asyncio.run(run())

    assert attempts["count"] >= 2
    assert ("enable_motors",) in mini.calls


def test_retrying_companion_replays_awake_state_on_connect():
    mini = FakeMini()
    sdk = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )
    companion = RetryingReachyCompanion(
        ReachyConfig(enabled=True, face_tracking_enabled=False, connect_retry_seconds=0.01)
    )

    async def run() -> None:
        companion._desired_awake = True
        with patch("reachy.companion._create_sdk_companion", return_value=sdk):
            await companion._get_or_connect()
            await companion.close()

    asyncio.run(run())

    assert ("enable_motors",) in mini.calls


def test_retrying_companion_sleep_on_first_connect_runs_once():
    mini = FakeMini()
    sdk = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )
    companion = RetryingReachyCompanion(
        ReachyConfig(enabled=True, face_tracking_enabled=False, connect_retry_seconds=0.01)
    )

    async def run() -> None:
        with patch("reachy.companion._create_sdk_companion", return_value=sdk):
            await companion.sleep()
            await companion.close()

    asyncio.run(run())

    assert mini.calls.count(("goto_sleep",)) == 1


def test_noop_companion_methods_are_async_safe():
    companion = NoOpReachyCompanion()

    async def run() -> None:
        await companion.wake()
        await companion.set_speaking(True)
        await companion.show_emotion("happy")
        await companion.sleep()
        await companion.close()

    asyncio.run(run())


def test_app_startup_sends_reachy_to_sleep():
    class FakeReachy:
        def __init__(self) -> None:
            self.calls = []

        async def sleep(self) -> None:
            self.calls.append("sleep")

    reachy = FakeReachy()

    asyncio.run(prepare_reachy_for_startup(reachy))

    assert reachy.calls == ["sleep"]


def test_wake_and_sleep_use_reachy_motion_api():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    async def run() -> None:
        await companion.wake()
        await companion.sleep()
        await companion.close()

    asyncio.run(run())

    assert mini.calls[0] == ("enable_motors",)
    assert mini.calls[1][0] == "goto_target"
    assert ("goto_sleep",) in mini.calls
    assert ("close",) in mini.calls


def test_show_emotion_queues_curated_motion():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    async def run() -> None:
        await companion.show_emotion(ReachyEmotion.CELEBRATE)
        assert companion._emotion_task is not None
        await companion._emotion_task
        await companion.close()

    asyncio.run(run())

    goto_calls = [call for call in mini.calls if call[0] == "goto_target"]
    assert len(goto_calls) == 4
    assert goto_calls[0][1]["method"] == "cartoon"


def test_unknown_emotion_is_ignored():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    async def run() -> None:
        await companion.show_emotion("not_real")
        await companion.close()

    asyncio.run(run())

    assert mini.calls == [("close",)]


def test_face_tracking_smoothing_reduces_target_jumps():
    assert _smooth_target((0.0, 0.0), (1.0, -1.0), alpha=0.25) == (0.25, -0.25)
