from __future__ import annotations

import json

import numpy as np
from PIL import Image

from face_samples import FaceSampleCollector


class FakeClock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def test_face_sample_collector_saves_crop_and_metadata(tmp_path):
    clock = FakeClock(100.0)
    collector = FaceSampleCollector(tmp_path, clock=clock)
    frame = np.zeros((100, 200, 3), dtype=np.uint8)
    frame[:, :] = [30, 60, 90]

    sample = collector.maybe_save(
        frame,
        (50, 20, 40, 30),
        confidence=0.91,
        landmarks=((55.5, 25.5), (80.5, 25.5)),
        candidates=[
            {
                "box": {"x": 50, "y": 20, "width": 40, "height": 30},
                "confidence": 0.91,
            }
        ],
        tracking_target=(-0.3, -0.3),
        motion={"kind": "track_face", "yaw": -7.5, "pitch": 4.5},
    )

    assert sample is not None
    assert sample.image_path.exists()
    assert sample.metadata_path.exists()
    with Image.open(sample.image_path) as image:
        assert image.size == (200, 100)
        red, _green, blue = image.getpixel((60, 30))
        assert red > blue
    metadata = json.loads(sample.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source"] == "reachy"
    assert metadata["detected"] is True
    assert metadata["frame_size"] == {"width": 200, "height": 100}
    assert metadata["face_box"] == {"x": 50, "y": 20, "width": 40, "height": 30}
    assert metadata["confidence"] == 0.91
    assert metadata["landmarks"] == [{"x": 55.5, "y": 25.5}, {"x": 80.5, "y": 25.5}]
    assert metadata["candidates"] == [
        {
            "box": {"x": 50, "y": 20, "width": 40, "height": 30},
            "confidence": 0.91,
        }
    ]
    assert metadata["tracking_target"] == {"x": -0.3, "y": -0.3}
    assert metadata["motion"] == {"kind": "track_face", "yaw": -7.5, "pitch": 4.5}
    assert metadata["motion_error"] is None
    assert metadata["crop_box"] == {"left": 36, "top": 10, "right": 104, "bottom": 60}
    assert metadata["crop_path"]
    with Image.open(metadata["crop_path"]) as crop:
        assert crop.size == (68, 50)


def test_face_sample_collector_saves_negative_attempt_metadata(tmp_path):
    clock = FakeClock(100.0)
    collector = FaceSampleCollector(tmp_path, clock=clock)
    frame = np.zeros((100, 200, 3), dtype=np.uint8)

    sample = collector.maybe_save(frame)

    assert sample is not None
    assert sample.image_path.exists()
    metadata = json.loads(sample.metadata_path.read_text(encoding="utf-8"))
    assert metadata["detected"] is False
    assert metadata["face_box"] is None
    assert metadata["confidence"] is None
    assert metadata["landmarks"] == []
    assert metadata["candidates"] == []
    assert metadata["tracking_target"] is None
    assert metadata["motion"] is None
    assert metadata["motion_error"] is None
    assert metadata["crop_box"] is None
    assert metadata["crop_path"] is None


def test_face_sample_collector_rate_limits_saves(tmp_path):
    clock = FakeClock(100.0)
    collector = FaceSampleCollector(tmp_path, min_interval_seconds=5.0, clock=clock)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    assert collector.maybe_save(frame, (20, 20, 20, 20)) is not None
    clock.now += 4.9
    assert collector.maybe_save(frame, (20, 20, 20, 20)) is None
    clock.now += 0.1
    assert collector.maybe_save(frame, (20, 20, 20, 20)) is not None
