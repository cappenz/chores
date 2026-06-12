from __future__ import annotations

import datetime
import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tkinter as tk
from PIL import Image, ImageTk

from chores import ChoresStatus
from core.people import PeopleRegistry
from display.diagnostics import DiagnosticsScreen

ScreenCommandSink = Callable[[str], Awaitable[None] | None]
AudioToggleSink = Callable[[bool], Awaitable[None] | None]

AVATAR_SIZE = 300
HEADER_CALENDAR_FONT_SIZE = 96
HEADER_DATETIME_FONT_SIZE = 40
HEADER_REGION_HEIGHT = 220
CHORES_REGION_HEIGHT = 430
CONTROLS_REGION_HEIGHT = 150
HORIZONTAL_PADDING = 40
MAX_FACE_SAMPLE_PREVIEWS = 3


@dataclass(frozen=True)
class ScreenStatus:
    title: str
    value: str
    highlighted: bool = True


class Screen:
    def __init__(
        self,
        window: tk.Tk,
        people: PeopleRegistry,
        status: ChoresStatus,
        *,
        on_chore_done: ScreenCommandSink,
        on_audio_toggle: AudioToggleSink,
    ) -> None:
        self.window = window
        self.people = people
        self.on_chore_done = on_chore_done
        self.on_audio_toggle = on_audio_toggle
        self.audio_enabled = status.audio_enabled
        self.speech_active = False
        self.current_status: ScreenStatus | None = None
        self.face_sample_paths: list[Path] = []
        self.diagnostics_data: dict = {}
        self._diagnostics_visible = False
        window.configure(bg="#f5f5f5")

        self.main_frame = tk.Frame(window, bg="#f5f5f5")
        self.main_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)

        self.diagnostics_screen = DiagnosticsScreen(window, on_close=self.hide_diagnostics)

        header_region = tk.Frame(self.main_frame, bg="#f5f5f5", padx=HORIZONTAL_PADDING, pady=40)
        header_region.place(x=0, y=0, relwidth=1.0, height=HEADER_REGION_HEIGHT)

        top_frame = tk.Frame(header_region, bg="#f5f5f5")
        top_frame.pack(fill="x")
        top_frame.columnconfigure(0, weight=1)
        top_frame.columnconfigure(1, weight=1)
        self.top_frame = top_frame

        left_header = tk.Frame(top_frame, bg="#f5f5f5")
        left_header.grid(row=0, column=0, sticky="nw")
        self.left_header = left_header

        tk.Label(
            left_header,
            text="📅",
            font=("Helvetica", HEADER_CALENDAR_FONT_SIZE),
            bg="#f5f5f5",
            fg="#333333",
        ).pack(side=tk.LEFT, padx=(0, 24))

        datetime_block = tk.Frame(left_header, bg="#f5f5f5")
        datetime_block.pack(side=tk.LEFT, anchor="w")

        self.date_label = tk.Label(
            datetime_block,
            text="...",
            font=("Helvetica", HEADER_DATETIME_FONT_SIZE, "bold"),
            bg="#f5f5f5",
            fg="#333333",
            anchor="w",
        )
        self.date_label.pack(anchor="w")

        self.time_text_label = tk.Label(
            datetime_block,
            text="...",
            font=("Helvetica", HEADER_DATETIME_FONT_SIZE, "bold"),
            bg="#f5f5f5",
            fg="#333333",
            anchor="w",
        )
        self.time_text_label.pack(anchor="w")

        self.right_header = tk.Frame(top_frame, bg="#f5f5f5")
        self.right_header.grid(row=0, column=1, sticky="nsew")
        self.status_frame = tk.Frame(
            self.right_header,
            bg="#333333",
            highlightthickness=0,
            bd=0,
        )
        self.status_inner_frame = tk.Frame(self.status_frame, bg="#f5f5f5", padx=18, pady=8)
        self.status_inner_frame.pack(fill="both", expand=True, padx=3, pady=3)
        self.status_title_label = tk.Label(
            self.status_inner_frame,
            text="",
            font=("Helvetica", HEADER_DATETIME_FONT_SIZE, "bold"),
            bg="#f5f5f5",
            fg="#333333",
            anchor="w",
        )
        self.status_title_label.pack(anchor="w")
        self.status_value_label = tk.Label(
            self.status_inner_frame,
            text="",
            font=("Helvetica", HEADER_DATETIME_FONT_SIZE, "bold"),
            bg="#f5f5f5",
            fg="#333333",
            anchor="w",
        )
        self.status_value_label.pack(anchor="w")

        top_frame.bind("<Configure>", self._on_top_frame_configure)

        chores_region = tk.Frame(self.main_frame, bg="#f5f5f5", padx=HORIZONTAL_PADDING)
        chores_region.place(
            x=0,
            y=HEADER_REGION_HEIGHT,
            relwidth=1.0,
            height=CHORES_REGION_HEIGHT,
        )

        chores_row = tk.Frame(chores_region, bg="#f5f5f5")
        chores_row.pack(fill="x")
        for column in range(3):
            chores_row.columnconfigure(column, weight=1)

        self.chore_images: list[tk.Label] = []
        self.chore_names: list[tk.Label] = []
        self.chore_photos: dict[str, ImageTk.PhotoImage] = {}
        self.load_person_images()

        for index, assignment in enumerate(status.assignments):
            chore_frame = tk.Frame(chores_row, bg="#f5f5f5")
            chore_frame.grid(row=0, column=index, sticky="nsew")

            title_label = tk.Label(
                chore_frame,
                text=self._title_for_chore(assignment.chore_id, assignment.chore_display_name),
                font=("Helvetica", 32, "bold"),
                bg="#f5f5f5",
                fg="#555555",
            )
            title_label.pack(pady=(0, 15))

            image_label = tk.Label(
                chore_frame,
                image=self.chore_photos[assignment.person_id],
                bg="#f5f5f5",
                cursor="hand2",
            )
            image_label.pack(pady=(0, 10))
            image_label.bind("<Button-1>", self._make_click_handler(assignment.chore_id))
            self.chore_images.append(image_label)

            name_label = tk.Label(
                chore_frame,
                text=assignment.person_display_name,
                font=("Helvetica", 30, "normal"),
                bg="#f5f5f5",
                fg="#000000",
            )
            name_label.pack()
            self.chore_names.append(name_label)

        controls_region = tk.Frame(self.main_frame, bg="#f5f5f5")
        controls_region.place(
            x=0,
            y=HEADER_REGION_HEIGHT + CHORES_REGION_HEIGHT,
            relwidth=1.0,
            height=CONTROLS_REGION_HEIGHT,
        )

        self.controls_frame = tk.Frame(controls_region, bg="#f5f5f5")
        self.controls_frame.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        self.microphone_label = tk.Label(
            self.controls_frame,
            text="🎤",
            font=("Helvetica", 30),
            bg="#f5f5f5",
            fg="#111111",
            width=3,
            height=2,
        )
        self.dev_button = tk.Button(
            self.controls_frame,
            text="i",
            font=("Helvetica", 30),
            bg="#f5f5f5",
            fg="#333333",
            relief=tk.FLAT,
            borderwidth=0,
            width=3,
            height=2,
            command=self.show_diagnostics,
        )
        self.audio_button = tk.Button(
            self.controls_frame,
            text=self._audio_button_text(),
            font=("Helvetica", 30),
            bg="#f5f5f5",
            fg="#333333",
            relief=tk.FLAT,
            borderwidth=0,
            width=3,
            height=2,
            command=self.toggle_audio,
        )
        self.dev_button.pack(side=tk.LEFT, padx=(0, 4))
        self.audio_button.pack(side=tk.LEFT)
        self.refresh(status)

    def refresh(self, status: ChoresStatus) -> None:
        self.audio_enabled = status.audio_enabled
        now = datetime.datetime.now()
        self.date_label.config(text=self._format_date_line(now))
        self.time_text_label.config(text=self._format_time_line(now))
        self.audio_button.config(text=self._audio_button_text())

        for index, assignment in enumerate(status.assignments):
            self.chore_names[index].config(text=assignment.person_display_name)
            self.chore_images[index].config(image=self.chore_photos[assignment.person_id])

    async def play_audio(self, audio: Any) -> None:
        del audio

    def set_status(self, status: ScreenStatus | None) -> None:
        self.current_status = status
        self._render_top_right()

    def set_diagnostics(self, diagnostics: dict) -> None:
        self.diagnostics_data = diagnostics
        if self._diagnostics_visible:
            self.diagnostics_screen.refresh(self.diagnostics_data, self.face_sample_paths)

    def show_diagnostics(self) -> None:
        self.main_frame.place_forget()
        self.diagnostics_screen.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self.diagnostics_screen.refresh(self.diagnostics_data, self.face_sample_paths)
        self._diagnostics_visible = True

    def hide_diagnostics(self) -> None:
        self.diagnostics_screen.place_forget()
        self.main_frame.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        self._diagnostics_visible = False

    def add_face_sample(self, image_path: Path) -> None:
        self.face_sample_paths.insert(0, image_path)
        self.face_sample_paths = self.face_sample_paths[:MAX_FACE_SAMPLE_PREVIEWS]
        if self._diagnostics_visible:
            self.diagnostics_screen.refresh(self.diagnostics_data, self.face_sample_paths)

    def _render_top_right(self) -> None:
        self.status_frame.pack_forget()
        status = self.current_status
        if status is None:
            return

        border_color = "#333333" if status.highlighted else "#f5f5f5"
        self.status_frame.config(bg=border_color)
        self.status_title_label.config(text=status.title)
        self.status_value_label.config(text=status.value)
        self.status_frame.pack(anchor="ne", padx=(0, 40))

    def set_speech_active(self, active: bool) -> None:
        if self.speech_active == active:
            return
        self.speech_active = active
        if active:
            self.microphone_label.pack(side=tk.LEFT, before=self.dev_button, padx=(0, 4))
        else:
            self.microphone_label.pack_forget()
        self.controls_frame.update()

    def pump(self) -> None:
        self.window.update_idletasks()
        self.window.update()

    def close(self) -> None:
        self.window.destroy()

    def load_person_images(self) -> None:
        for person in self.people.people:
            image_path = self.people.get_image_asset(person.id)
            if image_path is None or not image_path.exists():
                self.chore_photos[person.id] = self._fallback_photo()
                continue
            try:
                image = Image.open(image_path)
                image = self._crop_square(image)
                image = image.resize((300, 300), Image.LANCZOS)
                self.chore_photos[person.id] = ImageTk.PhotoImage(image)
            except Exception as error:
                print(f"Error loading image for {person.display_name}: {error}")
                self.chore_photos[person.id] = self._fallback_photo()

    def toggle_audio(self) -> None:
        self.audio_enabled = not self.audio_enabled
        self._maybe_await(self.on_audio_toggle(self.audio_enabled))
        self.audio_button.config(text=self._audio_button_text())
        self.audio_button.update()

    def _on_top_frame_configure(self, event: tk.Event) -> None:
        if event.widget is not self.top_frame:
            return
        inset = self._avatar_column_inset(event.width)
        self.left_header.grid_configure(padx=(inset, 0))

    @staticmethod
    def _avatar_column_inset(row_width: int, column_count: int = 3) -> int:
        return max(0, (row_width // column_count - AVATAR_SIZE) // 2)

    def _make_click_handler(self, chore_id: str):
        def handler(event) -> None:
            del event
            self._maybe_await(self.on_chore_done(chore_id))

        return handler

    def _audio_button_text(self) -> str:
        return "🔊" if self.audio_enabled else "🔇"

    @staticmethod
    def _fallback_photo() -> ImageTk.PhotoImage:
        fallback = Image.new("RGB", (300, 300), color="gray")
        return ImageTk.PhotoImage(fallback)

    @staticmethod
    def _title_for_chore(chore_id: str, display_name: str) -> str:
        display_titles = {
            "dishwasher": ("🍽️", "Dishwasher"),
            "kitchen_trash": ("🗑️", "Kitchen"),
            "wednesday_trash": ("🚛", "Trashcans"),
        }
        icon, label = display_titles.get(chore_id, ("", display_name))
        return f"{icon} {label}".strip()

    @staticmethod
    def _format_date_line(when: datetime.datetime) -> str:
        return when.strftime("%B %-d, %Y")

    @staticmethod
    def _format_time_line(when: datetime.datetime) -> str:
        return when.strftime("%H:%M:%S")

    @staticmethod
    def _crop_square(image: Image.Image) -> Image.Image:
        width, height = image.size
        if width > height:
            left = (width - height) // 2
            return image.crop((left, 0, left + height, height))
        top = (height - width) // 2
        return image.crop((0, top, width, top + width))

    @staticmethod
    def _maybe_await(result: Awaitable[None] | None) -> None:
        if result is not None:
            try:
                asyncio.create_task(result)
            except RuntimeError:
                if hasattr(result, "close"):
                    result.close()


async def run_screen(
    commands: ScreenCommandSink,
    state: Callable[[], ChoresStatus],
    people: PeopleRegistry,
) -> None:
    window = tk.Tk()
    screen = Screen(
        window,
        people,
        state(),
        on_chore_done=commands,
        on_audio_toggle=lambda enabled: None,
    )
    try:
        while True:
            screen.refresh(state())
            screen.pump()
    finally:
        screen.close()


def create_screen(
    people: PeopleRegistry,
    status: ChoresStatus,
    *,
    on_chore_done: ScreenCommandSink,
    on_audio_toggle: AudioToggleSink,
    window_mode: str | None = None,
) -> Screen:
    window = tk.Tk()
    if window_mode:
        dimensions = window_mode.replace(" ", "").split("x")
        width = int(dimensions[0])
        height = int(dimensions[1])
        window.geometry(f"{width}x{height}")
        window.attributes("-fullscreen", False)
    else:
        window.attributes("-fullscreen", True)
    return Screen(
        window,
        people,
        status,
        on_chore_done=on_chore_done,
        on_audio_toggle=on_audio_toggle,
    )
