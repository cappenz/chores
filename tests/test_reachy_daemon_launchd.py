from __future__ import annotations

import os
from pathlib import Path

import pytest

from scripts.reachy_daemon_launchd import (
    DaemonConfig,
    build_daemon_argv,
    build_plist,
    _load_config,
)


@pytest.fixture
def repo_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def daemon_config(repo_dir: Path) -> DaemonConfig:
    return DaemonConfig(
        repo_dir=repo_dir,
        uv_path=Path("/opt/homebrew/bin/uv"),
        mode="real",
        log_level="INFO",
        log_dir=repo_dir / "logs",
        no_media=False,
        port=None,
        extra_args=[],
    )


def test_build_daemon_argv_real(daemon_config: DaemonConfig) -> None:
    argv = build_daemon_argv(daemon_config)

    assert argv[0] == "/opt/homebrew/bin/uv"
    assert "reachy_mini.daemon.app.main" in argv
    assert "--localhost-only" in argv
    assert "--sim" not in argv
    assert str(daemon_config.log_dir / "reachy-daemon.log") in argv


def test_build_daemon_argv_sim(daemon_config: DaemonConfig) -> None:
    sim_config = DaemonConfig(
        repo_dir=daemon_config.repo_dir,
        uv_path=daemon_config.uv_path,
        mode="sim",
        log_level="INFO",
        log_dir=daemon_config.log_dir,
        no_media=False,
        port=None,
        extra_args=[],
    )

    argv = build_daemon_argv(sim_config)

    assert "--sim" in argv
    assert "--headless" in argv


def test_build_daemon_argv_no_media_and_port(daemon_config: DaemonConfig) -> None:
    config = DaemonConfig(
        repo_dir=daemon_config.repo_dir,
        uv_path=daemon_config.uv_path,
        mode="real",
        log_level="DEBUG",
        log_dir=daemon_config.log_dir,
        no_media=True,
        port="8765",
        extra_args=["--no-wake-up-on-start"],
    )

    argv = build_daemon_argv(config)

    assert "--no-media" in argv
    assert "--fastapi-port" in argv
    assert argv[argv.index("--fastapi-port") + 1] == "8765"
    assert "--no-wake-up-on-start" in argv


def test_build_plist_has_keepalive(daemon_config: DaemonConfig) -> None:
    plist = build_plist(daemon_config)

    assert plist["Label"] == "com.chores.reachy-daemon"
    assert plist["KeepAlive"] is True
    assert plist["RunAtLoad"] is True
    assert plist["WorkingDirectory"] == str(daemon_config.repo_dir)


def test_load_config_reads_mode_from_env(repo_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REACHY_DAEMON_MODE", "mockup-sim")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    config = _load_config(repo_dir)

    assert config.mode == "mockup-sim"


def test_load_config_rejects_invalid_mode(repo_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REACHY_DAEMON_MODE", "invalid")
    monkeypatch.setenv("PATH", os.environ.get("PATH", ""))

    with pytest.raises(ValueError, match="REACHY_DAEMON_MODE"):
        _load_config(repo_dir)
