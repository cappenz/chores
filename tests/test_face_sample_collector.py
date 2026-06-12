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

    sample = collector.maybe_save(frame, (50, 20, 40, 30))

    assert sample is not None
    assert sample.image_path.exists()
    assert sample.metadata_path.exists()
    with Image.open(sample.image_path) as image:
        assert image.size == (68, 50)
    metadata = json.loads(sample.metadata_path.read_text(encoding="utf-8"))
    assert metadata["source"] == "reachy"
    assert metadata["frame_size"] == {"width": 200, "height": 100}
    assert metadata["face_box"] == {"x": 50, "y": 20, "width": 40, "height": 30}
    assert metadata["crop_box"] == {"left": 36, "top": 10, "right": 104, "bottom": 60}


def test_face_sample_collector_rate_limits_saves(tmp_path):
    clock = FakeClock(100.0)
    collector = FaceSampleCollector(tmp_path, clock=clock)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    assert collector.maybe_save(frame, (20, 20, 20, 20)) is not None
    clock.now += 4.9
    assert collector.maybe_save(frame, (20, 20, 20, 20)) is None
    clock.now += 0.1
    assert collector.maybe_save(frame, (20, 20, 20, 20)) is not None
