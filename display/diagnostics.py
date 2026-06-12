from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path

import tkinter as tk
from PIL import Image, ImageTk

BACKGROUND = "#f5f5f5"
OUTER_PADDING = 40
TEXT_FONT = ("Courier", 14)
FACE_THUMBNAIL_SIZE = 160
MAX_FACE_SAMPLES = 3
LEFT_COLUMN_MINSIZE = 800
TEXT_WIDTH_CHARS = 80
CLIP_MAX_LEN = 80
LAST_ALIVE_STALE_SECONDS = 3.0


def load_face_sample_metadata(image_path: Path) -> dict:
    metadata_path = image_path.with_suffix(".json")
    if not metadata_path.exists():
        return {}
    try:
        return json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def format_diagnostics_lines(diagnostics: dict, *, face_sample_count: int = 0) -> list[str]:
    lines: list[str] = []
    reachy = diagnostics.get("reachy") or {}
    sdk = reachy.get("sdk") or {}
    if reachy.get("state") == "disabled":
        sdk = {}

    lines.extend(_section("Reachy", [
        ("Reachy State", _clip(_format_reachy_summary(reachy))),
        ("Actuation", _clip(_format_actuation(sdk))),
    ]))

    audio = diagnostics.get("audio") or {}
    lines.extend(_section("Audio", [
        ("PyAudio default in", _clip(_format_audio_side(audio.get("input") or {}))),
        ("PyAudio default out", _clip(_format_audio_side(audio.get("output") or {}))),
    ]))

    models = diagnostics.get("models") or {}
    lines.extend(_section("Models", [
        ("Live model", _clip(_format_live_model(models))),
        ("Announcement TTS", _clip(_format_announcement_tts(models))),
    ]))

    ui = diagnostics.get("ui") or {}
    speech_items: list[tuple[str, str]] = [
        ("Speech Active", _text(ui.get("speech_active"))),
        ("Audio Enabled", _text(ui.get("audio_enabled"))),
    ]
    status_title = ui.get("status_title")
    if status_title and status_title != "none":
        status_value = ui.get("status_value") or "none"
        speech_items.append(("Status", f"{status_title} / {status_value}"))
    lines.extend(_section("Speech/UI", speech_items))

    app = diagnostics.get("app") or {}
    uptime = app.get("uptime_seconds")
    uptime_text = f"{uptime}s" if uptime is not None else "unknown"
    lines.extend(_section("App", [
        ("Uptime", uptime_text),
        ("Face samples", str(face_sample_count)),
    ]))

    return lines


def _section(title: str, items: list[tuple[str, str]]) -> list[str]:
    lines = [title]
    for label, value in items:
        lines.append(f"  {label}: {value}")
    lines.append("")
    return lines


def _clip(text: str, max_len: int = CLIP_MAX_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _text(value, *, empty: str = "unknown") -> str:
    if value is None:
        return empty
    if isinstance(value, bool):
        return "yes" if value else "no"
    text = str(value).strip()
    return text if text else empty


def _format_reachy_summary(reachy: dict) -> str:
    if reachy.get("state") == "disabled":
        return "disabled"
    if reachy.get("state") == "error":
        return f"error ({reachy.get('error', 'unknown')})"

    parts: list[str] = []
    if reachy.get("connected"):
        parts.append("connected")
    elif reachy.get("retrying"):
        parts.append("unavailable (retrying)")
    elif reachy.get("connected_once"):
        parts.append("disconnected")
    else:
        parts.append("unknown")

    sdk = reachy.get("sdk") or {}
    daemon_state = sdk.get("daemon_state")
    if daemon_state:
        version = sdk.get("daemon_version")
        if version:
            parts.append(f"daemon {daemon_state} v{version}")
        else:
            parts.append(f"daemon {daemon_state}")

    desired_awake = reachy.get("desired_awake")
    if desired_awake is not None:
        parts.append(f"awake={'yes' if desired_awake else 'no'}")

    parts.append(f"retrying={'yes' if reachy.get('retrying') else 'no'}")
    return " | ".join(parts)


def _format_actuation(sdk: dict) -> str:
    if not sdk:
        return "unknown"
    ready = sdk.get("backend_ready")
    ready_text = _text(ready) if "backend_ready" in sdk else "unknown"
    last_alive = _format_last_alive(sdk.get("last_alive"))
    return f"ready={ready_text}, last_alive={last_alive}"


def _format_last_alive(value) -> str:
    if value is None:
        return "never"
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return str(value)
    age_seconds = time.time() - timestamp if timestamp > 1_000_000_000 else timestamp
    if age_seconds < 0:
        return "unknown"
    if age_seconds > LAST_ALIVE_STALE_SECONDS:
        return f"stale ({_format_age(age_seconds)} ago)"
    return f"{_format_age(age_seconds)} ago"


def _format_age(seconds: float) -> str:
    if seconds < 10:
        return f"{seconds:.1f}s"
    return f"{seconds:.0f}s"


def _format_live_model(models: dict) -> str:
    active = models.get("active")
    if active:
        return str(active)
    return "idle"


def _format_announcement_tts(models: dict) -> str:
    return _text(models.get("announcement_tts"))


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
        content.columnconfigure(0, weight=0, minsize=LEFT_COLUMN_MINSIZE)
        content.columnconfigure(1, weight=1, minsize=400)
        content.rowconfigure(0, weight=1)

        self._text = tk.Text(
            content,
            font=TEXT_FONT,
            bg=BACKGROUND,
            fg="#333333",
            wrap="none",
            width=TEXT_WIDTH_CHARS,
            height=35,
            relief=tk.FLAT,
            borderwidth=0,
            highlightthickness=0,
        )
        self._text.grid(row=0, column=0, sticky="nsew", padx=(0, 20))

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
        lines = format_diagnostics_lines(diagnostics, face_sample_count=len(face_paths))
        self._set_text("\n".join(lines))
        self._render_faces(face_paths[:MAX_FACE_SAMPLES])

    def _set_text(self, text: str) -> None:
        self._text.config(state=tk.NORMAL)
        self._text.delete("1.0", tk.END)
        self._text.insert("1.0", text)
        self._text.config(state=tk.DISABLED)

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
