from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

MIN_SAVE_INTERVAL_SECONDS = 5.0
DEFAULT_OUTPUT_DIR = Path("data/face_samples/unlabeled")
CROP_PADDING_RATIO = 0.35


@dataclass(frozen=True)
class FaceSample:
    image_path: Path
    metadata_path: Path


class FaceSampleCollector:
    def __init__(
        self,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
        *,
        min_interval_seconds: float = MIN_SAVE_INTERVAL_SECONDS,
        clock: Any = time.monotonic,
    ) -> None:
        self.output_dir = output_dir
        self.min_interval_seconds = min_interval_seconds
        self.clock = clock
        self._last_saved_at: float | None = None
        self._counter = 0
        self._session_dir = self._new_session_dir()

    def maybe_save(self, frame, face_box: tuple[int, int, int, int]) -> FaceSample | None:
        now = self.clock()
        if self._last_saved_at is not None and now - self._last_saved_at < self.min_interval_seconds:
            return None

        image = Image.fromarray(frame)
        crop_box = _expanded_crop_box(face_box, image.size)
        crop = image.crop(crop_box)
        self._session_dir.mkdir(parents=True, exist_ok=True)

        self._counter += 1
        stem = f"face-{self._counter:06d}"
        image_path = self._session_dir / f"{stem}.jpg"
        metadata_path = self._session_dir / f"{stem}.json"

        crop.save(image_path, quality=92)
        metadata_path.write_text(
            json.dumps(
                {
                    "captured_at": datetime.now().isoformat(timespec="seconds"),
                    "source": "reachy",
                    "image_path": str(image_path),
                    "frame_size": {"width": image.width, "height": image.height},
                    "face_box": _box_dict(face_box),
                    "crop_box": _crop_dict(crop_box),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        self._last_saved_at = now
        return FaceSample(image_path=image_path, metadata_path=metadata_path)

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


def _box_dict(face_box: tuple[int, int, int, int]) -> dict[str, int]:
    x, y, width, height = face_box
    return {"x": x, "y": y, "width": width, "height": height}


def _crop_dict(crop_box: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = crop_box
    return {"left": left, "top": top, "right": right, "bottom": bottom}
