from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

MIN_SAVE_INTERVAL_SECONDS = 1.0
DEFAULT_OUTPUT_DIR = Path("data/face_samples/unlabeled")
CROP_PADDING_RATIO = 0.35


@dataclass(frozen=True)
class FaceSample:
    image_path: Path
    metadata_path: Path | None = None


class FaceSampleCollector:
    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        *,
        min_interval_seconds: float = MIN_SAVE_INTERVAL_SECONDS,
        save_full_frame: bool = False,
        save_metadata: bool = False,
        clock: Any = time.monotonic,
    ) -> None:
        self.output_dir = output_dir
        self.min_interval_seconds = min_interval_seconds
        self.save_full_frame = save_full_frame
        self.save_metadata = save_metadata
        self.clock = clock
        self._last_saved_at: float | None = None
        self._counter = 0
        self._session_dir = self._new_session_dir()

    def maybe_save(
        self,
        frame,
        face_box: tuple[int, int, int, int] | None = None,
        *,
        confidence: float | None = None,
        landmarks: tuple[tuple[float, float], ...] = (),
        candidates: list[dict[str, Any]] | None = None,
        tracking_target: tuple[float, float] | None = None,
        motion: dict[str, Any] | None = None,
        motion_error: str | None = None,
    ) -> FaceSample | None:
        if face_box is None and not (self.save_full_frame or self.save_metadata):
            return None
        now = self.clock()
        if self._last_saved_at is not None and now - self._last_saved_at < self.min_interval_seconds:
            return None

        image = Image.fromarray(_bgr_to_rgb(frame))
        crop_box = _expanded_crop_box(face_box, image.size) if face_box is not None else None
        crop = image.crop(crop_box) if crop_box is not None else None
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._counter += 1
        stem = f"frame-{self._counter:06d}"
        image_path = self._session_dir / f"{stem}.jpg" if self.save_full_frame else None
        metadata_path = self._session_dir / f"{stem}.json" if self.save_metadata else None
        crop_path = self._session_dir / f"{stem}-crop.jpg" if face_box is not None else None

        if image_path is not None:
            image.save(image_path, quality=92)
        if crop_path is not None and crop is not None:
            crop.save(crop_path, quality=92)
        if metadata_path is not None:
            metadata_path.write_text(
                json.dumps(
                    {
                        "captured_at": datetime.now().isoformat(timespec="seconds"),
                        "source": "reachy",
                        "image_path": str(image_path or crop_path),
                        "detected": face_box is not None,
                        "frame_size": {"width": image.width, "height": image.height},
                        "face_box": _box_dict(face_box) if face_box is not None else None,
                        "confidence": confidence,
                        "landmarks": _landmarks_list(landmarks),
                        "candidates": candidates or [],
                        "tracking_target": _target_dict(tracking_target),
                        "motion": motion,
                        "motion_error": motion_error,
                        "crop_box": _crop_dict(crop_box) if face_box is not None else None,
                        "crop_path": str(crop_path) if crop_path is not None else None,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
        self._last_saved_at = now
        saved_image_path = crop_path or image_path
        if saved_image_path is None:
            return None
        return FaceSample(image_path=saved_image_path, metadata_path=metadata_path)

    def _new_session_dir(self) -> Path:
        started_at = datetime.now()
        return (
            self.output_dir
            / started_at.strftime("%Y-%m-%d")
            / f"session-{started_at.strftime('%H%M%S')}"
        )


def _expanded_crop_box(
    face_box: tuple[int, int, int, int],
    image_size: tuple[int, int],
) -> tuple[int, int, int, int]:
    x, y, width, height = face_box
    image_width, image_height = image_size
    pad_x = int(width * CROP_PADDING_RATIO)
    pad_y = int(height * CROP_PADDING_RATIO)
    left = max(0, x - pad_x)
    top = max(0, y - pad_y)
    right = min(image_width, x + width + pad_x)
    bottom = min(image_height, y + height + pad_y)
    return left, top, right, bottom


def _bgr_to_rgb(frame):
    return frame[..., ::-1]


def _box_dict(face_box: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = face_box
    return {"x": x, "y": y, "width": width, "height": height}


def _crop_dict(crop_box: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = crop_box
    return {"left": left, "top": top, "right": right, "bottom": bottom}


def _landmarks_list(landmarks: tuple[tuple[float, float], ...]) -> list[dict[str, float]]:
    return [{"x": x, "y": y} for x, y in landmarks]


def _target_dict(target: tuple[float, float] | None) -> dict[str, float] | None:
    if target is None:
        return None
    return {"x": target[0], "y": target[1]}
