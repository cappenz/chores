from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import tkinter as tk
from PIL import Image, ImageTk

BACKGROUND = "#f5f5f5"
OUTER_PADDING = 40
TEXT_FONT = ("Courier", 14)
FACE_THUMBNAIL_SIZE = 160
MAX_FACE_SAMPLES = 3


def load_face_sample_metadata(image_path: Path) -> dict:
    metadata_path = image_path.with_suffix(".json")
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def format_diagnostics_lines(diagnostics: dict) -> list[str]:
    lines: list[str] = []
    reachy = diagnostics.get("reachy") or {}
    sdk = reachy.get("sdk") or {}
    if reachy.get("state") == "disabled":
        sdk = {}

    lines.extend(_section("Reachy", [
        ("Reachy State", _reachy_state(reachy)),
        ("Daemon State", _text(sdk.get("daemon_state"))),
        ("Daemon Version", _text(sdk.get("daemon_version"))),
        ("Hardware ID", _text(sdk.get("hardware_id"))),
        ("Backend Ready", _text(sdk.get("backend_ready"))),
        ("Backend Error", _text(sdk.get("backend_error"), empty="none")),
        ("Motor Mode", _text(sdk.get("motor_mode"))),
        ("Last Alive", _text(sdk.get("last_alive"))),
        ("Control Loop", _text(sdk.get("control_loop"))),
    ]))

    audio = diagnostics.get("audio") or {}
    lines.extend(_section("Audio", [
        ("Audio In", _format_audio_side(audio.get("input") or {})),
        ("Audio Out", _format_audio_side(audio.get("output") or {})),
    ]))

    ui = diagnostics.get("ui") or {}
    status_title = ui.get("status_title") or "none"
    status_value = ui.get("status_value") or "none"
    status_text = f"{status_title} / {status_value}"
    lines.extend(_section("Speech/UI", [
        ("Speech Active", _text(ui.get("speech_active"))),
        ("Audio Enabled", _text(ui.get("audio_enabled"))),
        ("Status", status_text),
    ]))

    app = diagnostics.get("app") or {}
    uptime = app.get("uptime_seconds")
    uptime_text = f"{uptime}s" if uptime is not None else "unknown"
    lines.extend(_section("App", [
        ("PID", _text(app.get("pid"))),
        ("Uptime", uptime_text),
        ("Now", _text(app.get("now"))),
    ]))

    env = diagnostics.get("env") or {}
    env_items = [(key, _text(value)) for key, value in sorted(env.items())]
    if env_items:
        lines.extend(_section("Environment", env_items))

    return lines


def _section(title: str, items: list[tuple[str, str]]) -> list[str]:
    lines = [title]
    for label, value in items:
        lines.append(f"  {label}: {value}")
    lines.append("")
    return lines


def _text(value, *, empty: str = "unknown") -> str:
    if value is None:
        return empty
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value).strip()
    return text if text else empty


def _reachy_state(reachy: dict) -> str:
    if reachy.get("state") == "disabled":
        return "disabled"
    if reachy.get("state") == "error":
        return f"error ({reachy.get('error', 'unknown')})"
    if reachy.get("connected"):
        return "connected"
    if reachy.get("retrying"):
        return "unavailable (retrying)"
    if reachy.get("connected_once"):
        return "disconnected"
    return "unknown"


def _format_audio_side(side: dict) -> str:
    if side.get("error"):
        return str(side["error"])
    if not side:
        return "unknown"
    name = side.get("name", "unknown")
    index = side.get("index", "?")
    channels = side.get("channels", "?")
    sample_rate = side.get("sample_rate", "?")
    return f"{name} (index {index}, {channels}ch, {sample_rate} Hz)"


class DiagnosticsScreen(tk.Frame):
    def __init__(self, parent: tk.Misc, *, on_close: Callable[[], None]) -> None:
        super().__init__(parent, bg=BACKGROUND)
        self._on_close = on_close
        self._face_photos: list[ImageTk.PhotoImage] = []
        self._face_rows: list[tk.Frame] = []

        outer = tk.Frame(self, bg=BACKGROUND, padx=OUTER_PADDING, pady=OUTER_PADDING)
        outer.pack(fill="both", expand=True)

        content = tk.Frame(outer, bg=BACKGROUND)
        content.pack(fill="both", expand=True)
        content.columnconfigure(0, weight=2)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._text_label = tk.Label(
            content,
            text="",
            font=TEXT_FONT,
            bg=BACKGROUND,
            fg="#333333",
            anchor="nw",
            justify="left",
        )
        self._text_label.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

        self._faces_frame = tk.Frame(content, bg=BACKGROUND)
        self._faces_frame.grid(row=0, column=1, sticky="nsew")

        self._empty_faces_label = tk.Label(
            self._faces_frame,
            text="No face samples yet",
            font=TEXT_FONT,
            bg=BACKGROUND,
            fg="#666666",
            anchor="n",
        )

        footer = tk.Frame(outer, bg=BACKGROUND)
        footer.pack(fill="x", pady=(20, 0))

        tk.Button(
            footer,
            text="Close",
            font=("Helvetica", 24),
            bg=BACKGROUND,
            fg="#333333",
            relief=tk.FLAT,
            borderwidth=0,
            command=self._on_close,
        ).pack(side=tk.LEFT, anchor="sw")

    def refresh(self, diagnostics: dict, face_paths: list[Path]) -> None:
        lines = format_diagnostics_lines(diagnostics)
        self._text_label.config(text="\n".join(lines))
        self._render_faces(face_paths[:MAX_FACE_SAMPLES])

    def _render_faces(self, face_paths: list[Path]) -> None:
        for row in self._face_rows:
            row.destroy()
        self._face_rows = []
        self._face_photos = []
        self._empty_faces_label.pack_forget()

        if not face_paths:
            self._empty_faces_label.pack(anchor="n")
            return

        for path in face_paths:
            row = tk.Frame(self._faces_frame, bg=BACKGROUND)
            row.pack(fill="x", pady=(0, 16))
            self._face_rows.append(row)

            metadata = load_face_sample_metadata(path)
            captured_at = metadata.get("captured_at", "unknown")

            try:
                with Image.open(path) as image:
                    image = image.copy()
                image.thumbnail((FACE_THUMBNAIL_SIZE, FACE_THUMBNAIL_SIZE), Image.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self._face_photos.append(photo)
                tk.Label(row, image=photo, bg=BACKGROUND).pack(anchor="w")
            except OSError:
                tk.Label(row, text="(image unavailable)", font=TEXT_FONT, bg=BACKGROUND).pack(anchor="w")

            tk.Label(
                row,
                text=path.name,
                font=TEXT_FONT,
                bg=BACKGROUND,
                fg="#333333",
                anchor="w",
            ).pack(anchor="w")
            tk.Label(
                row,
                text=captured_at,
                font=TEXT_FONT,
                bg=BACKGROUND,
                fg="#666666",
                anchor="w",
            ).pack(anchor="w")
