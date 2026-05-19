from __future__ import annotations

import asyncio

from reachy.companion import (
    NoOpReachyCompanion,
    ReachyConfig,
    ReachyEmotion,
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


def test_noop_companion_methods_are_async_safe():
    companion = NoOpReachyCompanion()

    async def run() -> None:
        await companion.wake()
        await companion.set_speaking(True)
        await companion.show_emotion("happy")
        await companion.sleep()
        await companion.close()

    asyncio.run(run())


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
