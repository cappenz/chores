from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from kitchen_agent import prepare_reachy_for_startup
from reachy.companion import (
    DEFAULT_TRACKING_HZ,
    FaceCandidate,
    FaceDetection,
    NoOpReachyCompanion,
    ReachyConfig,
    ReachyEmotion,
    RetryingReachyCompanion,
    SdkReachyCompanion,
    _candidate_to_detection,
    _candidate_metadata,
    _nudge_tracking_angles,
    _parse_yunet_face,
    _should_rest_after_face_miss,
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


class FakeFaceDetector:
    def __init__(self) -> None:
        self.frames = []

    def detect(self, frame) -> FaceDetection | None:
        self.frames.append(frame)
        return None


def fake_head_pose(**kwargs):
    return {"head_pose": kwargs}


def test_disabled_reachy_uses_noop_companion():
    companion = run_reachy_companion(ReachyConfig(enabled=False))

    assert isinstance(companion, NoOpReachyCompanion)


def test_enabled_reachy_uses_retrying_companion():
    companion = run_reachy_companion(ReachyConfig(enabled=True))

    assert isinstance(companion, RetryingReachyCompanion)


def test_default_face_tracking_rate_is_five_hz():
    assert DEFAULT_TRACKING_HZ == 5.0
    assert ReachyConfig().tracking_hz == 5.0


def test_retrying_companion_reconnects_after_initial_failure():
    mini = FakeMini()
    sdk = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )
    attempts = {"count": 0}

    def fake_create(_config: ReachyConfig, **kwargs) -> SdkReachyCompanion:
        del kwargs
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


def test_sleep_does_not_start_face_detection():
    mini = FakeMini()
    detector = FakeFaceDetector()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=True),
        face_detector=detector,
    )

    async def run() -> None:
        await companion.sleep()
        await asyncio.sleep(0)
        await companion.close()

    asyncio.run(run())

    assert detector.frames == []


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


def test_parse_yunet_face_preserves_confidence_landmarks_and_target():
    detection = _parse_yunet_face(
        [50, 20, 40, 30, 60, 30, 80, 30, 70, 40, 62, 50, 78, 50, 0.91],
        frame_shape=(100, 200, 3),
        confidence_threshold=0.8,
        min_face_size_pixels=20,
    )

    assert detection is not None
    assert detection.box == (50, 20, 40, 30)
    assert detection.confidence == 0.91
    assert detection.landmarks == (
        (60.0, 30.0),
        (80.0, 30.0),
        (70.0, 40.0),
        (62.0, 50.0),
        (78.0, 50.0),
    )
    assert detection.target == pytest.approx((-0.3, -0.3))


def test_parse_yunet_face_rejects_low_confidence_or_tiny_boxes():
    low_confidence = _parse_yunet_face(
        [50, 20, 40, 30, 60, 30, 80, 30, 70, 40, 62, 50, 78, 50, 0.5],
        frame_shape=(100, 200, 3),
        confidence_threshold=0.8,
        min_face_size_pixels=20,
    )
    tiny = _parse_yunet_face(
        [50, 20, 10, 30, 60, 30, 80, 30, 70, 40, 62, 50, 78, 50, 0.91],
        frame_shape=(100, 200, 3),
        confidence_threshold=0.8,
        min_face_size_pixels=20,
    )

    assert low_confidence is None
    assert tiny is None


def test_raw_candidate_metadata_survives_threshold_rejection():
    candidate = FaceCandidate(
        target=(-0.3, -0.3),
        box=(50, 20, 40, 30),
        confidence=0.5,
        landmarks=((60.0, 30.0),),
    )

    detection = _candidate_to_detection(
        candidate,
        confidence_threshold=0.8,
        min_face_size_pixels=20,
    )

    assert detection is None
    assert _candidate_metadata(candidate) == {
        "box": {"x": 50, "y": 20, "width": 40, "height": 30},
        "confidence": 0.5,
        "landmarks": [{"x": 60.0, "y": 30.0}],
        "target": {"x": -0.3, "y": -0.3},
    }


def test_parse_yunet_face_allows_edge_clipped_boxes_for_tracking():
    detection = _parse_yunet_face(
        [50, 2, 40, 30, 60, 8, 80, 8, 70, 20, 62, 25, 78, 25, 0.91],
        frame_shape=(100, 200, 3),
        confidence_threshold=0.8,
        min_face_size_pixels=20,
    )

    assert detection is not None
    assert detection.box == (50, 2, 40, 30)


def test_face_tracking_uses_set_target_for_head_motion():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    angles, motion = asyncio.run(companion._look_at_normalized_target((0.5, 0.5), (10.0, 5.0)))

    assert angles == (8.0, 6.5)
    assert motion["previous_yaw"] == 10.0
    assert motion["previous_pitch"] == 5.0
    assert motion["delta_yaw"] == -2.0
    assert motion["delta_pitch"] == 1.5
    assert motion["skipped"] is False
    assert motion["method"] == "set_target"
    assert mini.calls == [
        (
            "set_target",
            {
                "head": {"head_pose": {"yaw": 8.0, "pitch": 6.5, "degrees": True}},
            },
        )
    ]


def test_face_tracking_uses_negative_pitch_for_faces_high_in_frame():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    angles, motion = asyncio.run(companion._look_at_normalized_target((0.0, -0.5), (0.0, 0.0)))

    assert angles == (0.0, -1.5)
    assert motion["pitch"] == -1.5
    assert mini.calls == [
        (
            "set_target",
            {
                "head": {"head_pose": {"yaw": 0.0, "pitch": -1.5, "degrees": True}},
            },
        )
    ]


def test_face_tracking_skips_motion_inside_deadband():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    angles, motion = asyncio.run(companion._look_at_normalized_target((0.05, -0.05), (10.0, -5.0)))

    assert angles == (10.0, -5.0)
    assert motion["skipped"] is True
    assert motion["delta_yaw"] == 0.0
    assert motion["delta_pitch"] == 0.0
    assert mini.calls == []


def test_face_tracking_returns_to_rest_without_face():
    mini = FakeMini()
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=fake_head_pose,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    asyncio.run(companion._look_at_rest())

    assert mini.calls == [
        (
            "goto_target",
            {
                "head": {"head_pose": {}},
                "duration": 0.4,
                "method": "minjerk",
            },
        )
    ]


def test_face_tracking_waits_before_resting_after_recent_face_miss():
    assert not _should_rest_after_face_miss(
        now=104.9,
        last_seen_at=100.0,
        grace_seconds=5.0,
        already_resting=False,
    )
    assert _should_rest_after_face_miss(
        now=105.0,
        last_seen_at=100.0,
        grace_seconds=5.0,
        already_resting=False,
    )
    assert not _should_rest_after_face_miss(
        now=110.0,
        last_seen_at=100.0,
        grace_seconds=5.0,
        already_resting=True,
    )


def test_face_tracking_nudges_angles_with_deadband_and_limits():
    assert _nudge_tracking_angles(
        target=(0.5, -0.5),
        current_angles=(10.0, -5.0),
        deadband=0.12,
        yaw_step_degrees=4.0,
        pitch_step_degrees=3.0,
        max_yaw_degrees=55.0,
        max_pitch_degrees=30.0,
    ) == (8.0, -6.5, -2.0, -1.5)
    assert _nudge_tracking_angles(
        target=(0.05, -0.05),
        current_angles=(10.0, -5.0),
        deadband=0.12,
        yaw_step_degrees=4.0,
        pitch_step_degrees=3.0,
        max_yaw_degrees=55.0,
        max_pitch_degrees=30.0,
    ) == (10.0, -5.0, 0.0, 0.0)
    assert _nudge_tracking_angles(
        target=(1.0, -1.0),
        current_angles=(54.0, -29.0),
        deadband=0.12,
        yaw_step_degrees=4.0,
        pitch_step_degrees=3.0,
        max_yaw_degrees=55.0,
        max_pitch_degrees=30.0,
    ) == (50.0, -30.0, -4.0, -1.0)
