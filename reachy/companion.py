from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

DEFAULT_TRACKING_HZ = 8.0
DEFAULT_MEDIA_BACKEND = "default"
NO_MEDIA_BACKEND = "no_media"
DEFAULT_CONNECT_RETRY_SECONDS = 3.0
LOG_THROTTLE_SECONDS = 30.0


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


class SdkReachyCompanion:
    def __init__(
        self,
        mini,
        *,
        create_head_pose: Callable[..., Any],
        config: ReachyConfig,
        face_detector: "FaceDetector | None" = None,
    ) -> None:
        self._mini = mini
        self._create_head_pose = create_head_pose
        self._config = config
        self._face_detector = face_detector
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
            *(task for task in (self._speaking_task, self._emotion_task, face_task) if task),
            return_exceptions=True,
        )
        await asyncio.to_thread(self._close_mini)

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
        try:
            while True:
                started = time.monotonic()
                target = await asyncio.to_thread(self._detect_face_target)
                if target is not None:
                    smoothed = _smooth_target(smoothed, target)
                    await self._look_at_normalized_target(smoothed)
                elapsed = time.monotonic() - started
                await asyncio.sleep(max(0.0, interval - elapsed))
        except asyncio.CancelledError:
            pass

    def _detect_face_target(self) -> tuple[float, float] | None:
        frame = self._mini.media.get_frame()
        assert self._face_detector is not None
        return self._face_detector.detect(frame)

    async def _look_at_normalized_target(self, target: tuple[float, float]) -> None:
        x, y = target
        yaw = max(-25.0, min(25.0, x * 25.0))
        pitch = max(-15.0, min(15.0, -y * 15.0))
        async with self._motion_lock:
            await asyncio.to_thread(
                self._mini.set_target,
                head=self._create_head_pose(yaw=yaw, pitch=pitch, degrees=True),
            )

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
    def __init__(self) -> None:
        cv2 = _cv2()
        self._cv2 = cv2
        self._cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )

    def detect(self, frame) -> tuple[float, float] | None:
        cv2 = self._cv2
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        faces = self._cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)
        if len(faces) == 0:
            return None
        height, width = gray.shape[:2]
        x, y, w, h = max(faces, key=lambda face: face[2] * face[3])
        center_x = (x + w / 2) / width
        center_y = (y + h / 2) / height
        return (center_x - 0.5) * 2.0, (center_y - 0.5) * 2.0


@dataclass(frozen=True)
class EmotionMove:
    head: dict
    antennas: list[float]
    duration: float
    method: str = "minjerk"


class RetryingReachyCompanion:
    def __init__(self, config: ReachyConfig) -> None:
        self._config = config
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
                self._companion = _create_sdk_companion(self._config)
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


def _create_sdk_companion(config: ReachyConfig) -> SdkReachyCompanion:
    ReachyMini, create_head_pose = _reachy_imports()
    media_backend = config.media_backend
    if not config.face_tracking_enabled and media_backend == DEFAULT_MEDIA_BACKEND:
        media_backend = NO_MEDIA_BACKEND
    mini = ReachyMini(connection_mode="localhost_only", media_backend=media_backend)
    face_detector = FaceDetector() if config.face_tracking_enabled else None
    return SdkReachyCompanion(
        mini,
        create_head_pose=create_head_pose,
        config=config,
        face_detector=face_detector,
    )


def run_reachy_companion(config: ReachyConfig) -> ReachyCompanion:
    if not config.enabled:
        return NoOpReachyCompanion()
    return RetryingReachyCompanion(config)


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


def _reachy_imports():
    from reachy_mini import ReachyMini
    from reachy_mini.utils import create_head_pose

    return ReachyMini, create_head_pose


def _cv2():
    import cv2

    return cv2
