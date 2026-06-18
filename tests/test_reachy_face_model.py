from __future__ import annotations

import numpy as np
import pytest

from reachy.companion import FaceDetector


@pytest.mark.model
def test_yunet_model_loads_and_runs_on_blank_frame():
    detector = FaceDetector()
    frame = np.zeros((120, 160, 3), dtype=np.uint8)

    detector.detect(frame)
