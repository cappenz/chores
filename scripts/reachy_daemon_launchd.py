#!/usr/bin/env python3
"""Install and manage the Reachy Mini daemon as a macOS LaunchAgent."""

from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

LABEL = "com.chores.reachy-daemon"
DEFAULT_MODE = "real"
VALID_MODES = frozenset({"real", "sim", "mockup-sim"})


@dataclass(frozen=True)
class DaemonConfig:
    repo_dir: Path
    uv_path: Path
    mode: str
    log_level: str
    log_dir: Path
    no_media: bool
    port: str | None
    extra_args: list[str]


def _env_bool(name: str, *, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.casefold() in {"1", "true", "yes", "on"}


def _load_config(repo_dir: Path | None = None) -> DaemonConfig:
    root = (repo_dir or Path.cwd()).resolve()
    mode = os.getenv("REACHY_DAEMON_MODE", DEFAULT_MODE).casefold().strip()
    if mode not in VALID_MODES:
        raise ValueError(f"REACHY_DAEMON_MODE must be one of {sorted(VALID_MODES)}, got {mode!r}")

    uv = shutil.which("uv")
    if not uv:
        raise RuntimeError("uv not found on PATH")

    extra_raw = os.getenv("REACHY_DAEMON_EXTRA_ARGS", "").strip()
    extra_args = shlex.split(extra_raw) if extra_raw else []
    log_dir = Path(os.path.expanduser(os.getenv("REACHY_DAEMON_LOG_DIR", "~/Library/Logs/chores")))

    return DaemonConfig(
        repo_dir=root,
        uv_path=Path(uv),
        mode=mode,
        log_level=os.getenv("REACHY_DAEMON_LOG_LEVEL", "INFO").upper(),
        log_dir=log_dir,
        no_media=_env_bool("REACHY_DAEMON_NO_MEDIA"),
        port=os.getenv("REACHY_DAEMON_PORT"),
        extra_args=extra_args,
    )


def _launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def _launchctl_domain() -> str:
    uid = os.getuid()
    return f"gui/{uid}"


def _launchctl_target() -> str:
    return f"{_launchctl_domain()}/{LABEL}"


def build_daemon_argv(config: DaemonConfig) -> list[str]:
    log_file = config.log_dir / "reachy-daemon.log"
    argv = [
        str(config.uv_path),
        "run",
        "python",
        "-m",
        "reachy_mini.daemon.app.main",
        "--localhost-only",
        "--log-level",
        config.log_level,
        "--log-file",
        str(log_file),
    ]
    if config.mode == "sim":
        argv.extend(["--sim", "--headless"])
    elif config.mode == "mockup-sim":
        argv.extend(["--mockup-sim", "--headless"])
    if config.no_media:
        argv.append("--no-media")
    if config.port:
        argv.extend(["--fastapi-port", config.port])
    argv.extend(config.extra_args)
    return argv


def build_plist(config: DaemonConfig) -> dict:
    config.log_dir.mkdir(parents=True, exist_ok=True)
    stdout = config.log_dir / "reachy-daemon.stdout.log"
    stderr = config.log_dir / "reachy-daemon.stderr.log"
    return {
        "Label": LABEL,
        "WorkingDirectory": str(config.repo_dir),
        "ProgramArguments": build_daemon_argv(config),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 10,
        "StandardOutPath": str(stdout),
        "StandardErrorPath": str(stderr),
    }


def _run_launchctl(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["launchctl", *args],
        check=check,
        capture_output=True,
        text=True,
    )


def cmd_print(config: DaemonConfig) -> int:
    plist = build_plist(config)
    print(plistlib.dumps(plist).decode())
    print(f"\nWould install to: {_launch_agent_path()}", file=sys.stderr)
    return 0


def cmd_install(config: DaemonConfig) -> int:
    plist_path = _launch_agent_path()
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist = build_plist(config)
    with plist_path.open("wb") as handle:
        plistlib.dump(plist, handle)
    print(f"Wrote {plist_path} (mode={config.mode})")

    domain = _launchctl_domain()
    target = _launchctl_target()
    bootout = _run_launchctl(["bootout", domain, str(plist_path)], check=False)
    if bootout.returncode != 0 and "No such process" not in (bootout.stderr or ""):
        pass
    _run_launchctl(["bootstrap", domain, str(plist_path)])
    _run_launchctl(["enable", target])
    _run_launchctl(["kickstart", "-k", target])
    print(f"Installed and started {target}")
    return 0


def cmd_uninstall() -> int:
    plist_path = _launch_agent_path()
    domain = _launchctl_domain()
    if plist_path.exists():
        _run_launchctl(["bootout", domain, str(plist_path)], check=False)
        plist_path.unlink()
        print(f"Removed {plist_path}")
    else:
        print(f"No plist at {plist_path}")
    return 0


def cmd_start() -> int:
    _run_launchctl(["kickstart", "-k", _launchctl_target()])
    print(f"Started {_launchctl_target()}")
    return 0


def cmd_stop() -> int:
    _run_launchctl(["kill", "SIGTERM", _launchctl_target()], check=False)
    print(f"Stopped {_launchctl_target()}")
    return 0


def cmd_status() -> int:
    result = _run_launchctl(["print", _launchctl_target()], check=False)
    if result.returncode != 0:
        print(f"Not loaded: {_launchctl_target()}")
        if result.stderr:
            print(result.stderr.strip())
        return 1
    print(result.stdout)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage Reachy Mini daemon LaunchAgent")
    parser.add_argument(
        "command",
        choices=["install", "uninstall", "start", "stop", "status", "print"],
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=None,
        help="Repository root (default: current working directory)",
    )
    args = parser.parse_args(argv)

    try:
        config = _load_config(args.repo_dir)
    except (RuntimeError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    commands = {
        "print": lambda: cmd_print(config),
        "install": lambda: cmd_install(config),
        "uninstall": cmd_uninstall,
        "start": cmd_start,
        "stop": cmd_stop,
        "status": cmd_status,
    }
    return commands[args.command]()


if __name__ == "__main__":
    raise SystemExit(main())
