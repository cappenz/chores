from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock

from display.diagnostics import format_diagnostics_lines, load_face_sample_metadata
from reachy.companion import (
    NoOpReachyCompanion,
    RetryingReachyCompanion,
    ReachyConfig,
    SdkReachyCompanion,
    _daemon_status_to_dict,
)
from speech_agent.audio import get_audio_device_diagnostics
from speech_agent.live import get_live_model_diagnostics


def test_format_diagnostics_lines_includes_sections_and_labels():
    diagnostics = {
        "app": {"uptime_seconds": 45.2},
        "ui": {
            "audio_enabled": True,
            "speech_active": False,
            "status_title": "Timer",
            "status_value": "03:12",
        },
        "models": {
            "active": None,
            "primary": "gemini-3.1-flash-live-preview",
            "fallback": "gemini-2.5-flash-native-audio-preview-12-2025",
            "announcement_tts": "eleven_multilingual_v2",
        },
        "reachy": {
            "connected": True,
            "desired_awake": True,
            "retrying": False,
            "sdk": {
                "daemon_state": "running",
                "daemon_version": "1.7.3",
                "backend_ready": True,
                "last_alive": time.time() - 1.2,
            },
        },
        "audio": {
            "input": {"name": "Mic", "index": 1, "channels": 1, "sample_rate": 16000.0},
            "output": {"name": "Speakers", "index": 3, "channels": 2, "sample_rate": 48000.0},
        },
    }

    text = "\n".join(format_diagnostics_lines(diagnostics, face_sample_count=2))

    assert "Reachy State: connected | daemon running v1.7.3 | awake=yes | retrying=no" in text
    assert "Actuation: ready=yes, last_alive=" in text
    assert "PyAudio default in: Mic (index 1, 1ch, 16000.0 Hz)" in text
    assert "PyAudio default out: Speakers (index 3, 2ch, 48000.0 Hz)" in text
    assert "Live model: idle" in text
    assert "Announcement TTS: eleven_multilingual_v2" in text
    assert "Speech Active: no" in text
    assert "Status: Timer / 03:12" in text
    assert "Uptime: 45.2s" in text
    assert "Face samples: 2" in text
    assert "Daemon State" not in text
    assert "PID:" not in text


def test_format_diagnostics_lines_omits_status_when_idle():
    text = "\n".join(format_diagnostics_lines({
        "ui": {"status_title": "none", "status_value": "none"},
    }))

    assert "Status:" not in text


def test_format_diagnostics_lines_shows_active_live_model():
    text = "\n".join(format_diagnostics_lines({
        "models": {"active": "gemini-3.1-flash-live-preview"},
    }))

    assert "Live model: gemini-3.1-flash-live-preview" in text


def test_format_diagnostics_lines_clips_long_values():
    long_name = "X" * 100
    text = "\n".join(format_diagnostics_lines({
        "audio": {"input": {"name": long_name, "index": 1, "channels": 1, "sample_rate": 16000.0}},
    }))

    line = next(line for line in text.splitlines() if line.startswith("  PyAudio default in:"))
    assert line.endswith("…")
    assert len(line.split(": ", 1)[1]) == 80


def test_format_diagnostics_lines_uses_unknown_for_missing_values():
    text = "\n".join(format_diagnostics_lines({}))

    assert "Reachy State: unknown" in text
    assert "PyAudio default in: unknown" in text
    assert "PyAudio default out: unknown" in text
    assert "Face samples: 0" in text


def test_format_diagnostics_lines_marks_stale_last_alive():
    text = "\n".join(format_diagnostics_lines({
        "reachy": {"sdk": {"backend_ready": False, "last_alive": time.time() - 12.0}},
    }))

    assert "last_alive=stale (12s ago)" in text


def test_get_live_model_diagnostics_includes_primary_and_fallback():
    result = get_live_model_diagnostics()

    assert result["active"] is None
    assert result["primary"] == "gemini-3.1-flash-live-preview"
    assert result["fallback"] == "gemini-2.5-flash-native-audio-preview-12-2025"


def test_load_face_sample_metadata_reads_adjacent_json(tmp_path: Path):
    image_path = tmp_path / "face-000001.jpg"
    image_path.write_text("fake", encoding="utf-8")
    metadata_path = tmp_path / "face-000001.json"
    metadata_path.write_text(
        json.dumps({"captured_at": "2026-06-12T10:00:00"}),
        encoding="utf-8",
    )

    assert load_face_sample_metadata(image_path)["captured_at"] == "2026-06-12T10:00:00"


def test_get_audio_device_diagnostics_success(monkeypatch):
    class FakePyAudio:
        def get_default_input_device_info(self):
            return {
                "name": "Mic",
                "index": 1,
                "maxInputChannels": 1,
                "defaultSampleRate": 16000.0,
            }

        def get_default_output_device_info(self):
            return {
                "name": "Speakers",
                "index": 3,
                "maxOutputChannels": 2,
                "defaultSampleRate": 48000.0,
            }

        def terminate(self) -> None:
            pass

    monkeypatch.setattr("speech_agent.audio._pyaudio", lambda: type("M", (), {"PyAudio": FakePyAudio}))

    result = get_audio_device_diagnostics()

    assert result["input"]["name"] == "Mic"
    assert result["output"]["name"] == "Speakers"


def test_get_audio_device_diagnostics_handles_os_error(monkeypatch):
    class FakePyAudio:
        def get_default_input_device_info(self):
            raise OSError("no input")

        def get_default_output_device_info(self):
            raise OSError("no output")

        def terminate(self) -> None:
            pass

    monkeypatch.setattr("speech_agent.audio._pyaudio", lambda: type("M", (), {"PyAudio": FakePyAudio}))

    result = get_audio_device_diagnostics()

    assert result["input"]["error"] == "no input"
    assert result["output"]["error"] == "no output"


def test_noop_reachy_diagnostics():
    assert NoOpReachyCompanion().diagnostics() == {"state": "disabled", "reason": "disabled"}


def test_sdk_reachy_diagnostics_reads_daemon_status():
    status = MagicMock()
    status.state = MagicMock(value="running")
    status.version = "1.7.3"
    status.hardware_id = "hw-1"
    status.error = None
    backend = MagicMock()
    backend.ready = True
    backend.error = None
    backend.motor_control_mode = MagicMock(value="enabled")
    backend.last_alive = 123.4
    backend.control_loop_stats = {"nb_error": 0}
    status.backend_status = backend

    mini = MagicMock()
    mini.client.get_status.return_value = status
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=lambda **kwargs: kwargs,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    result = companion.diagnostics()

    assert result["daemon_state"] == "running"
    assert result["motor_mode"] == "enabled"


def test_sdk_reachy_diagnostics_returns_error_dict_on_failure():
    mini = MagicMock()
    mini.client.get_status.side_effect = RuntimeError("daemon down")
    companion = SdkReachyCompanion(
        mini,
        create_head_pose=lambda **kwargs: kwargs,
        config=ReachyConfig(enabled=True, face_tracking_enabled=False),
    )

    result = companion.diagnostics()

    assert result["state"] == "error"
    assert "daemon down" in result["error"]


def test_retrying_reachy_diagnostics_includes_sdk_when_connected():
    sdk = MagicMock()
    sdk.diagnostics.return_value = {"daemon_state": "running"}
    companion = RetryingReachyCompanion(ReachyConfig(enabled=True, face_tracking_enabled=False))
    companion._companion = sdk
    companion._desired_awake = True
    companion._connected_once = True

    result = companion.diagnostics()

    assert result["connected"] is True
    assert result["desired_awake"] is True
    assert result["sdk"]["daemon_state"] == "running"


def test_daemon_status_to_dict_without_backend():
    status = MagicMock()
    status.state = MagicMock(value="error")
    status.version = "1.7.3"
    status.hardware_id = None
    status.error = "backend failed"
    status.backend_status = None

    result = _daemon_status_to_dict(status)

    assert result["daemon_state"] == "error"
    assert result["daemon_error"] == "backend failed"
    assert "backend_ready" not in result
