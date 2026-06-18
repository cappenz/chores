from __future__ import annotations

import asyncio
import hashlib
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from face_samples import FaceSampleCollector

DEFAULT_TRACKING_HZ = 2.0
DEFAULT_MEDIA_BACKEND = "default"
NO_MEDIA_BACKEND = "no_media"
DEFAULT_CONNECT_RETRY_SECONDS = 3.0
YUNET_RAW_SCORE_THRESHOLD = 0.0
DEFAULT_FACE_CONFIDENCE_THRESHOLD = 0.8
DEFAULT_MIN_FACE_SIZE_PIXELS = 40
DEFAULT_FACE_MISS_GRACE_SECONDS = 5.0
LOG_THROTTLE_SECONDS = 30.0
YUNET_MODEL_PATH = Path(__file__).resolve().parent / "models" / "face_detection_yunet_2023mar.onnx"
YUNET_MODEL_URL = (
    "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/"
    "models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
)
YUNET_MODEL_SHA256 = "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"


class ReachyEmotion(StrEnum):
    HAPPY = "happy"
    CURIOUS = "curious"
    THINKING = "thinking"
    CONFUSED = "confused"
    CELEBRATE = "celebrate"
    SAD = "sad"


class ReachyCompanion(Protocol):
    async def wake(self) -> None:
        ...

    async def sleep(self) -> None:
        ...

    async def set_speaking(self, active: bool) -> None:
        ...

    async def show_emotion(self, emotion: ReachyEmotion | str) -> None:
        ...

    async def close(self) -> None:
        ...

    def diagnostics(self) -> dict:
        ...


@dataclass(frozen=True)
class ReachyConfig:
    enabled: bool = False
    face_tracking_enabled: bool = True
    emotion_playback_enabled: bool = True
    speaking_motion_enabled: bool = True
    tracking_hz: float = DEFAULT_TRACKING_HZ
    debug: bool = False
    media_backend: str = DEFAULT_MEDIA_BACKEND
    connect_retry_seconds: float = DEFAULT_CONNECT_RETRY_SECONDS
    max_connect_retry_seconds: float | None = None
    reconnect_on_command_failure: bool = True
    face_confidence_threshold: float = DEFAULT_FACE_CONFIDENCE_THRESHOLD
    min_face_size_pixels: int = DEFAULT_MIN_FACE_SIZE_PIXELS
    face_miss_grace_seconds: float = DEFAULT_FACE_MISS_GRACE_SECONDS


@dataclass(frozen=True)
class FaceCandidate:
    target: tuple[float, float]
    box: tuple[int, int, int, int]
    confidence: float
    landmarks: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class FaceDetection:
    target: tuple[float, float]
    box: tuple[int, int, int, int]
    confidence: float = 1.0
    landmarks: tuple[tuple[float, float], ...] = ()
    sample_path: Path | None = None


@dataclass(frozen=True)
class FaceDetectionAttempt:
    frame: Any | None
    detection: FaceDetection | None
    candidates: tuple[FaceCandidate, ...] = ()


class NoOpReachyCompanion:
    def __init__(self, reason: str = "disabled") -> None:
        self.reason = reason

    async def wake(self) -> None:
        pass

    async def sleep(self) -> None:
        pass

    async def set_speaking(self, active: bool) -> None:
        pass

    async def show_emotion(self, emotion: ReachyEmotion | str) -> None:
        pass

    async def close(self) -> None:
        pass

    def diagnostics(self) -> dict:
        return {"state": "disabled", "reason": self.reason}


class SdkReachyCompanion:
    def __init__(
        self,
        mini,
        *,
        create_head_pose: Callable[..., Any],
        config: ReachyConfig,
        face_detector: "FaceDetector | None" = None,
        face_sample_collector: FaceSampleCollector | None = None,
        on_face_sample_saved: Callable[[Path], None] | None = None,
    ) -> None:
        self._mini = mini
        self._create_head_pose = create_head_pose
        self._config = config
        self._face_detector = face_detector
        self._face_sample_collector = face_sample_collector
        self._on_face_sample_saved = on_face_sample_saved
        self._motion_lock = asyncio.Lock()
        self._face_task: asyncio.Task | None = None
        self._speaking_task: asyncio.Task | None = None
        self._emotion_task: asyncio.Task | None = None
        self._closed = False
        self._awake = False

    async def wake(self) -> None:
        if self._closed:
            return
        self._awake = True
        async with self._motion_lock:
            await asyncio.to_thread(self._call_if_present, "enable_motors")
            await asyncio.to_thread(
                self._mini.goto_target,
                head=self._create_head_pose(),
                antennas=[-0.15, 0.15],
                duration=0.6,
                method="minjerk",
            )
        self._start_face_tracking()

    async def sleep(self) -> None:
        self._awake = False
        self._stop_face_tracking()
        await self.set_speaking(False)
        self._cancel_task(self._emotion_task)
        self._emotion_task = None
        if self._closed:
            return
        async with self._motion_lock:
            if hasattr(self._mini, "goto_sleep"):
                await asyncio.to_thread(self._mini.goto_sleep)
            else:
                await asyncio.to_thread(
                    self._mini.goto_target,
                    head=self._create_head_pose(pitch=-20, degrees=True),
                    antennas=[-3.05, 3.05],
                    duration=1.0,
                    method="minjerk",
                )

    async def set_speaking(self, active: bool) -> None:
        if not self._config.speaking_motion_enabled or self._closed:
            return
        if active:
            if self._speaking_task is None or self._speaking_task.done():
                self._speaking_task = asyncio.create_task(self._speaking_loop())
            return
        self._cancel_task(self._speaking_task)
        self._speaking_task = None

    async def show_emotion(self, emotion: ReachyEmotion | str) -> None:
        if not self._config.emotion_playback_enabled or self._closed:
            return
        parsed = _parse_emotion(emotion)
        if parsed is None:
            if self._config.debug:
                print(f"[reachy] Ignoring unknown emotion: {emotion}", flush=True)
            return
        self._cancel_task(self._emotion_task)
        self._emotion_task = asyncio.create_task(self._play_emotion(parsed))

    async def close(self) -> None:
        self._closed = True
        self._awake = False
        face_task = self._face_task
        self._cancel_task(face_task)
        self._face_task = None
        self._cancel_task(self._speaking_task)
        self._cancel_task(self._emotion_task)
        await asyncio.gather(
            *(
                task
                for task in (
                    self._speaking_task,
                    self._emotion_task,
                    face_task,
                )
                if task
            ),
            return_exceptions=True,
        )
        await asyncio.to_thread(self._close_mini)

    def diagnostics(self) -> dict:
        try:
            status = self._mini.client.get_status(wait=False)
            return _daemon_status_to_dict(status)
        except Exception as error:
            return {"state": "error", "error": str(error)}

    def _start_face_tracking(self) -> None:
        if (
            self._closed
            or not self._awake
            or not self._config.face_tracking_enabled
            or self._face_detector is None
        ):
            return
        if self._face_task is None or self._face_task.done():
            self._face_task = asyncio.create_task(self._face_tracking_loop())

    def _stop_face_tracking(self) -> None:
        self._cancel_task(self._face_task)
        self._face_task = None

    async def _speaking_loop(self) -> None:
        phase = 0
        try:
            while True:
                phase += 1
                offset = 0.08 if phase % 2 else -0.08
                async with self._motion_lock:
                    await asyncio.to_thread(
                        self._mini.set_target,
                        antennas=[-0.15 + offset, 0.15 + offset],
                    )
                await asyncio.sleep(0.35)
        except asyncio.CancelledError:
            pass

    async def _play_emotion(self, emotion: ReachyEmotion) -> None:
        self._stop_face_tracking()
        try:
            for move in _emotion_moves(emotion):
                async with self._motion_lock:
                    await asyncio.to_thread(
                        self._mini.goto_target,
                        head=self._create_head_pose(**move.head),
                        antennas=move.antennas,
                        duration=move.duration,
                        method=move.method,
                    )
                await asyncio.sleep(move.duration)
        finally:
            self._start_face_tracking()

    async def _face_tracking_loop(self) -> None:
        interval = 1.0 / max(self._config.tracking_hz, 1.0)
        smoothed: tuple[float, float] | None = None
        last_seen_at: float | None = None
        resting_after_miss = False
        try:
            while self._awake and not self._closed:
                started = time.monotonic()
                attempt = await asyncio.to_thread(self._detect_face)
                detection = attempt.detection
                motion: dict[str, Any] | None = None
                motion_error: str | None = None
                if detection is not None:
                    last_seen_at = started
                    resting_after_miss = False
                    smoothed = _smooth_target(smoothed, detection.target)
                    try:
                        motion = await self._look_at_normalized_target(smoothed)
                    except Exception as error:
                        motion_error = str(error)
                else:
                    if _should_rest_after_face_miss(
                        now=started,
                        last_seen_at=last_seen_at,
                        grace_seconds=self._config.face_miss_grace_seconds,
                        already_resting=resting_after_miss,
                    ):
                        smoothed = None
                        resting_after_miss = True
                        try:
                            motion = await self._look_at_rest()
                        except Exception as error:
                            motion_error = str(error)
                sample_path = await asyncio.to_thread(
                    self._save_face_attempt,
                    attempt,
                    motion,
                    motion_error,
                )
                if sample_path is not None and self._on_face_sample_saved is not None:
                    self._on_face_sample_saved(sample_path)
                if motion_error is not None:
                    raise RuntimeError(f"Face tracking motion failed: {motion_error}")
                elapsed = time.monotonic() - started
                await asyncio.sleep(max(0.0, interval - elapsed))
        except asyncio.CancelledError:
            pass
        except Exception as error:
            print(f"[reachy] Face tracking loop stopped: {error}", flush=True)

    def _detect_face(self) -> FaceDetectionAttempt:
        frame = self._mini.media.get_frame()
        assert self._face_detector is not None
        if frame is None:
            return FaceDetectionAttempt(None, None)
        candidates = self._face_detector.detect_candidates(frame)
        detection = self._face_detector.select_detection(candidates)
        return FaceDetectionAttempt(frame, detection, tuple(candidates))

    def _save_face_attempt(
        self,
        attempt: FaceDetectionAttempt,
        motion: dict[str, Any] | None,
        motion_error: str | None,
    ) -> Path | None:
        if attempt.frame is None or self._face_sample_collector is None:
            return None
        detection = attempt.detection
        sample = self._face_sample_collector.maybe_save(
            attempt.frame,
            detection.box if detection is not None else None,
            confidence=detection.confidence if detection is not None else None,
            landmarks=detection.landmarks if detection is not None else (),
            candidates=[_candidate_metadata(candidate) for candidate in attempt.candidates],
            tracking_target=detection.target if detection is not None else None,
            motion=motion,
            motion_error=motion_error,
        )
        return sample.image_path if sample is not None else None

    async def _look_at_normalized_target(self, target: tuple[float, float]) -> dict[str, Any]:
        x, y = target
        yaw = max(-25.0, min(25.0, x * 25.0))
        pitch = max(-15.0, min(15.0, y * 15.0))
        command = {
            "kind": "track_face",
            "target": {"x": x, "y": y},
            "yaw": yaw,
            "pitch": pitch,
            "duration": 0.25,
            "method": "minjerk",
        }
        async with self._motion_lock:
            await asyncio.to_thread(
                self._mini.goto_target,
                head=self._create_head_pose(yaw=yaw, pitch=pitch, degrees=True),
                duration=command["duration"],
                method=command["method"],
            )
        return command

    async def _look_at_rest(self) -> dict[str, Any]:
        command = {
            "kind": "no_face_rest",
            "yaw": 0.0,
            "pitch": 0.0,
            "duration": 0.4,
            "method": "minjerk",
        }
        async with self._motion_lock:
            await asyncio.to_thread(
                self._mini.goto_target,
                head=self._create_head_pose(),
                duration=command["duration"],
                method=command["method"],
            )
        return command

    def _call_if_present(self, name: str) -> None:
        method = getattr(self._mini, name, None)
        if method:
            method()

    def _close_mini(self) -> None:
        close = getattr(self._mini, "close", None)
        if close:
            close()
            return
        exit_method = getattr(self._mini, "__exit__", None)
        if exit_method:
            exit_method(None, None, None)

    @staticmethod
    def _cancel_task(task: asyncio.Task | None) -> None:
        if task and not task.done():
            task.cancel()


class FaceDetector:
    def __init__(
        self,
        *,
        confidence_threshold: float = DEFAULT_FACE_CONFIDENCE_THRESHOLD,
        min_face_size_pixels: int = DEFAULT_MIN_FACE_SIZE_PIXELS,
        model_path: Path = YUNET_MODEL_PATH,
    ) -> None:
        cv2 = _cv2()
        self._cv2 = cv2
        self._confidence_threshold = confidence_threshold
        self._min_face_size_pixels = min_face_size_pixels
        self._model_path = model_path
        _verify_model_artifact(model_path)
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path),
            "",
            (320, 320),
            YUNET_RAW_SCORE_THRESHOLD,
            0.3,
            5000,
        )

    def detect(self, frame) -> FaceDetection | None:
        return self.select_detection(self.detect_candidates(frame))

    def detect_candidates(self, frame) -> list[FaceCandidate]:
        if frame is None:
            return []
        height, width = frame.shape[:2]
        self._detector.setInputSize((width, height))
        _, faces = self._detector.detect(frame)
        if faces is None or len(faces) == 0:
            return []
        return [
            candidate
            for face in faces
            if (
                candidate := _parse_yunet_candidate(
                    face,
                    frame_shape=frame.shape,
                )
            )
            is not None
        ]

    def select_detection(self, candidates: list[FaceCandidate]) -> FaceDetection | None:
        detections = [
            detection
            for candidate in candidates
            if (
                detection := _candidate_to_detection(
                    candidate,
                    confidence_threshold=self._confidence_threshold,
                    min_face_size_pixels=self._min_face_size_pixels,
                )
            )
            is not None
        ]
        if not detections:
            return None
        return max(
            detections,
            key=lambda detection: detection.confidence * detection.box[2] * detection.box[3],
        )


@dataclass(frozen=True)
class EmotionMove:
    head: dict
    antennas: list[float]
    duration: float
    method: str = "minjerk"


class RetryingReachyCompanion:
    def __init__(
        self,
        config: ReachyConfig,
        *,
        face_sample_collector: FaceSampleCollector | None = None,
        on_face_sample_saved: Callable[[Path], None] | None = None,
    ) -> None:
        self._config = config
        self._face_sample_collector = face_sample_collector
        self._on_face_sample_saved = on_face_sample_saved
        self._companion: SdkReachyCompanion | None = None
        self._desired_awake = False
        self._desired_speaking = False
        self._closed = False
        self._lock = asyncio.Lock()
        self._retry_task: asyncio.Task | None = None
        self._last_log_time = 0.0
        self._retry_started_at: float | None = None
        self._connected_once = False

    async def wake(self) -> None:
        self._desired_awake = True
        await self._run_on_companion(lambda companion: companion.wake())

    async def sleep(self) -> None:
        self._desired_awake = False
        self._desired_speaking = False
        await self._run_on_companion(lambda companion: companion.sleep())

    async def set_speaking(self, active: bool) -> None:
        self._desired_speaking = active
        await self._run_on_companion(lambda companion: companion.set_speaking(active))

    async def show_emotion(self, emotion: ReachyEmotion | str) -> None:
        await self._run_on_companion(lambda companion: companion.show_emotion(emotion))

    async def close(self) -> None:
        self._closed = True
        self._cancel_retry_task()
        async with self._lock:
            companion = self._companion
            self._companion = None
        if companion is not None:
            await companion.close()

    async def _run_on_companion(self, action) -> None:
        if self._closed:
            return
        companion = await self._get_or_connect(apply_desired_state=False)
        if companion is None:
            self._ensure_retry_loop()
            return
        try:
            await action(companion)
        except Exception as error:
            if self._config.reconnect_on_command_failure:
                self._log_throttled(f"Command failed, reconnecting: {error}")
                await self._disconnect()
                self._ensure_retry_loop()

    async def _get_or_connect(self, *, apply_desired_state: bool = True) -> SdkReachyCompanion | None:
        async with self._lock:
            if self._closed:
                return None
            if self._companion is not None:
                return self._companion
            if self._retry_exhausted():
                return None
            try:
                self._companion = _create_sdk_companion(
                    self._config,
                    face_sample_collector=self._face_sample_collector,
                    on_face_sample_saved=self._on_face_sample_saved,
                )
            except Exception as error:
                self._log_throttled(f"Waiting for daemon: {error}")
                return None
            if not self._connected_once:
                print("[reachy] Connected to daemon", flush=True)
                self._connected_once = True
            else:
                print("[reachy] Reconnected to daemon", flush=True)
            self._retry_started_at = None
        if apply_desired_state:
            await self._apply_desired_state()
        return self._companion

    async def _apply_desired_state(self) -> None:
        companion = self._companion
        if companion is None or self._closed:
            return
        if self._desired_awake:
            await companion.wake()
        else:
            await companion.sleep()
        if self._desired_speaking and self._desired_awake:
            await companion.set_speaking(True)

    async def _disconnect(self) -> None:
        async with self._lock:
            companion = self._companion
            self._companion = None
        if companion is not None:
            try:
                await companion.close()
            except Exception:
                pass

    def _retry_exhausted(self) -> bool:
        limit = self._config.max_connect_retry_seconds
        if limit is None or self._retry_started_at is None:
            return False
        return time.monotonic() - self._retry_started_at >= limit

    def _ensure_retry_loop(self) -> None:
        if self._closed or self._retry_exhausted():
            return
        if self._retry_task is not None and not self._retry_task.done():
            return
        if self._retry_started_at is None:
            self._retry_started_at = time.monotonic()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._retry_task = loop.create_task(self._retry_loop())

    async def _retry_loop(self) -> None:
        try:
            while not self._closed and self._companion is None and not self._retry_exhausted():
                await asyncio.sleep(self._config.connect_retry_seconds)
                if self._closed:
                    return
                await self._get_or_connect()
        except asyncio.CancelledError:
            pass

    def _cancel_retry_task(self) -> None:
        if self._retry_task is not None and not self._retry_task.done():
            self._retry_task.cancel()
        self._retry_task = None

    def _log_throttled(self, message: str) -> None:
        now = time.monotonic()
        if now - self._last_log_time >= LOG_THROTTLE_SECONDS:
            print(f"[reachy] {message}", flush=True)
            self._last_log_time = now

    def diagnostics(self) -> dict:
        retrying = (
            self._retry_task is not None
            and not self._retry_task.done()
        ) or (self._companion is None and not self._closed and self._config.enabled)
        result = {
            "desired_awake": self._desired_awake,
            "desired_speaking": self._desired_speaking,
            "connected": self._companion is not None,
            "connected_once": self._connected_once,
            "retrying": retrying,
        }
        if self._companion is not None:
            result["sdk"] = self._companion.diagnostics()
        return result


def _daemon_status_to_dict(status) -> dict:
    backend = status.backend_status
    state = status.state
    result = {
        "daemon_state": state.value if hasattr(state, "value") else str(state),
        "daemon_version": status.version,
        "hardware_id": status.hardware_id,
        "daemon_error": status.error,
    }
    if backend is None:
        return result

    mode = getattr(backend, "motor_control_mode", None)
    stats = getattr(backend, "control_loop_stats", None)
    result.update({
        "backend_ready": getattr(backend, "ready", None),
        "backend_error": getattr(backend, "error", None),
        "motor_mode": mode.value if hasattr(mode, "value") else str(mode) if mode is not None else None,
        "last_alive": getattr(backend, "last_alive", None),
        "control_loop": str(stats) if stats else None,
    })
    return result


def _create_sdk_companion(
    config: ReachyConfig,
    *,
    face_sample_collector: FaceSampleCollector | None = None,
    on_face_sample_saved: Callable[[Path], None] | None = None,
) -> SdkReachyCompanion:
    ReachyMini, create_head_pose = _reachy_imports()
    media_backend = config.media_backend
    if not config.face_tracking_enabled and media_backend == DEFAULT_MEDIA_BACKEND:
        media_backend = NO_MEDIA_BACKEND
    mini = ReachyMini(connection_mode="localhost_only", media_backend=media_backend)
    face_detector = (
        FaceDetector(
            confidence_threshold=config.face_confidence_threshold,
            min_face_size_pixels=config.min_face_size_pixels,
        )
        if config.face_tracking_enabled
        else None
    )
    return SdkReachyCompanion(
        mini,
        create_head_pose=create_head_pose,
        config=config,
        face_detector=face_detector,
        face_sample_collector=face_sample_collector,
        on_face_sample_saved=on_face_sample_saved,
    )


def run_reachy_companion(
    config: ReachyConfig,
    *,
    face_sample_collector: FaceSampleCollector | None = None,
    on_face_sample_saved: Callable[[Path], None] | None = None,
) -> ReachyCompanion:
    if not config.enabled:
        return NoOpReachyCompanion()
    return RetryingReachyCompanion(
        config,
        face_sample_collector=face_sample_collector,
        on_face_sample_saved=on_face_sample_saved,
    )


def _parse_emotion(emotion: ReachyEmotion | str) -> ReachyEmotion | None:
    text = str(emotion).casefold().strip()
    aliases = {
        "excited": ReachyEmotion.CELEBRATE,
        "success": ReachyEmotion.CELEBRATE,
        "happy": ReachyEmotion.HAPPY,
        "curious": ReachyEmotion.CURIOUS,
        "thinking": ReachyEmotion.THINKING,
        "thoughtful": ReachyEmotion.THINKING,
        "confused": ReachyEmotion.CONFUSED,
        "celebrate": ReachyEmotion.CELEBRATE,
        "sad": ReachyEmotion.SAD,
    }
    return aliases.get(text)


def _emotion_moves(emotion: ReachyEmotion) -> list[EmotionMove]:
    deg = math.radians
    moves = {
        ReachyEmotion.HAPPY: [
            EmotionMove({"z": 8, "mm": True}, [deg(35), deg(-35)], 0.35),
            EmotionMove({"roll": 8, "degrees": True}, [deg(15), deg(-15)], 0.35),
            EmotionMove({}, [deg(-10), deg(10)], 0.35),
        ],
        ReachyEmotion.CURIOUS: [
            EmotionMove({"yaw": 12, "roll": 8, "degrees": True}, [deg(25), deg(5)], 0.45),
            EmotionMove({"yaw": -8, "roll": -5, "degrees": True}, [deg(5), deg(25)], 0.45),
        ],
        ReachyEmotion.THINKING: [
            EmotionMove({"pitch": -8, "roll": 5, "degrees": True}, [deg(5), deg(20)], 0.6),
            EmotionMove({"pitch": -5, "roll": -5, "degrees": True}, [deg(20), deg(5)], 0.6),
        ],
        ReachyEmotion.CONFUSED: [
            EmotionMove({"roll": 12, "degrees": True}, [deg(30), deg(30)], 0.35),
            EmotionMove({"roll": -12, "degrees": True}, [deg(-20), deg(-20)], 0.35),
            EmotionMove({}, [deg(10), deg(-10)], 0.35),
        ],
        ReachyEmotion.CELEBRATE: [
            EmotionMove({"z": 12, "mm": True}, [deg(50), deg(-50)], 0.3, "cartoon"),
            EmotionMove({"z": 4, "mm": True}, [deg(-30), deg(30)], 0.3, "cartoon"),
            EmotionMove({"z": 12, "mm": True}, [deg(50), deg(-50)], 0.3, "cartoon"),
            EmotionMove({}, [deg(-10), deg(10)], 0.4),
        ],
        ReachyEmotion.SAD: [
            EmotionMove({"pitch": -18, "z": -5, "degrees": True, "mm": True}, [deg(-45), deg(45)], 0.8),
            EmotionMove({"pitch": -10, "degrees": True}, [deg(-25), deg(25)], 0.8),
        ],
    }
    return moves[emotion]


def _smooth_target(
    previous: tuple[float, float] | None,
    current: tuple[float, float],
    alpha: float = 0.35,
) -> tuple[float, float]:
    if previous is None:
        return current
    return (
        previous[0] * (1.0 - alpha) + current[0] * alpha,
        previous[1] * (1.0 - alpha) + current[1] * alpha,
    )


def _should_rest_after_face_miss(
    *,
    now: float,
    last_seen_at: float | None,
    grace_seconds: float,
    already_resting: bool,
) -> bool:
    if already_resting:
        return False
    if last_seen_at is None:
        return True
    return now - last_seen_at >= grace_seconds


def _parse_yunet_candidate(
    face,
    *,
    frame_shape: tuple[int, ...],
) -> FaceCandidate | None:
    height, width = frame_shape[:2]
    x, y, box_width, box_height = (float(value) for value in face[:4])
    confidence = float(face[14])

    left = max(0, round(x))
    top = max(0, round(y))
    right = min(width, round(x + box_width))
    bottom = min(height, round(y + box_height))
    clipped_width = right - left
    clipped_height = bottom - top
    if clipped_width <= 0 or clipped_height <= 0:
        return None

    center_x = (left + clipped_width / 2) / width
    center_y = (top + clipped_height / 2) / height
    landmarks = tuple(
        (float(face[index]), float(face[index + 1]))
        for index in range(4, 14, 2)
    )
    return FaceCandidate(
        target=((center_x - 0.5) * 2.0, (center_y - 0.5) * 2.0),
        box=(left, top, clipped_width, clipped_height),
        confidence=confidence,
        landmarks=landmarks,
    )


def _candidate_to_detection(
    candidate: FaceCandidate,
    *,
    confidence_threshold: float,
    min_face_size_pixels: int,
) -> FaceDetection | None:
    if candidate.confidence < confidence_threshold:
        return None
    if candidate.box[2] < min_face_size_pixels or candidate.box[3] < min_face_size_pixels:
        return None
    return FaceDetection(
        target=candidate.target,
        box=candidate.box,
        confidence=candidate.confidence,
        landmarks=candidate.landmarks,
    )


def _parse_yunet_face(
    face,
    *,
    frame_shape: tuple[int, ...],
    confidence_threshold: float,
    min_face_size_pixels: int,
) -> FaceDetection | None:
    candidate = _parse_yunet_candidate(face, frame_shape=frame_shape)
    if candidate is None:
        return None
    return _candidate_to_detection(
        candidate,
        confidence_threshold=confidence_threshold,
        min_face_size_pixels=min_face_size_pixels,
    )


def _candidate_metadata(candidate: FaceCandidate) -> dict[str, Any]:
    return {
        "box": _box_metadata(candidate.box),
        "confidence": candidate.confidence,
        "landmarks": _landmarks_metadata(candidate.landmarks),
        "target": {"x": candidate.target[0], "y": candidate.target[1]},
    }


def _box_metadata(box: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = box
    return {"x": x, "y": y, "width": width, "height": height}


def _landmarks_metadata(landmarks: tuple[tuple[float, float], ...]) -> list[dict[str, float]]:
    return [{"x": x, "y": y} for x, y in landmarks]


def _verify_model_artifact(model_path: Path) -> None:
    if not model_path.exists():
        raise FileNotFoundError(
            f"YuNet model artifact is missing: {model_path}. Source: {YUNET_MODEL_URL}"
        )
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest != YUNET_MODEL_SHA256:
        raise ValueError(
            f"YuNet model checksum mismatch for {model_path}: expected "
            f"{YUNET_MODEL_SHA256}, got {digest}"
        )


def _reachy_imports():
    from reachy_mini import ReachyMini
    from reachy_mini.utils import create_head_pose

    return ReachyMini, create_head_pose


def _cv2():
    import cv2

    return cv2
