from __future__ import annotations

import datetime
import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import tkinter as tk
from PIL import Image, ImageTk

from chores import ChoresStatus
from core.people import PeopleRegistry

ScreenCommandSink = Callable[[str], Awaitable[None] | None]
AudioToggleSink = Callable[[bool], Awaitable[None] | None]


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
        window.configure(bg="#f5f5f5")

        main_frame = tk.Frame(window, bg="#f5f5f5", padx=40, pady=70)
        main_frame.pack(expand=True, fill="both")

        self.time_label = tk.Label(
            main_frame,
            text="Today is ...",
            font=("Helvetica", 48, "bold"),
            bg="#f5f5f5",
            fg="#333333",
        )
        self.time_label.pack(anchor="center", pady=(0, 100))

        chores_row = tk.Frame(main_frame, bg="#f5f5f5")
        chores_row.pack(fill="x", expand=True)
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

        self.controls_frame = tk.Frame(window, bg="#f5f5f5")
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
        self.audio_button.pack(side=tk.LEFT)
        self.refresh(status)

    def refresh(self, status: ChoresStatus) -> None:
        self.audio_enabled = status.audio_enabled
        now = datetime.datetime.now()
        self.time_label.config(text=now.strftime("%m/%d/%Y %I:%M:%S %p"))
        self.audio_button.config(text=self._audio_button_text())

        for index, assignment in enumerate(status.assignments):
            self.chore_names[index].config(text=assignment.person_display_name)
            self.chore_images[index].config(image=self.chore_photos[assignment.person_id])

    async def play_audio(self, audio: Any) -> None:
        del audio

    def set_speech_active(self, active: bool) -> None:
        if self.speech_active == active:
            return
        self.speech_active = active
        if active:
            self.microphone_label.pack(side=tk.LEFT, before=self.audio_button, padx=(0, 4))
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
        icons = {
            "dishwasher": "🍽️",
            "kitchen_trash": "🗑️",
            "wednesday_trash": "🌳",
        }
        return f"{icons.get(chore_id, '')} {display_name}".strip()

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

