from __future__ import annotations

import pytest

from chores import ChoresService


@pytest.fixture
def isolated_data_dir(tmp_path, monkeypatch):
    data_dir = tmp_path / "data"
    monkeypatch.setattr(ChoresService, "data_dir", str(data_dir))
    monkeypatch.setattr(ChoresService, "data_file", "status.json")
    return data_dir
