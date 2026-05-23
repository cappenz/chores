from __future__ import annotations

import datetime

from display.screen import Screen, ScreenStatus


def test_title_for_chore_uses_display_only_labels():
    assert Screen._title_for_chore("dishwasher", "Dishwasher") == "🍽️ Dishwasher"
    assert Screen._title_for_chore("kitchen_trash", "Kitchen trash") == "🗑️ Kitchen"
    assert Screen._title_for_chore("wednesday_trash", "Wednesday trash") == "🚛 Trashcans"


def test_avatar_column_inset_centers_avatar_in_first_column():
    assert Screen._avatar_column_inset(1200) == 50


def test_format_date_and_time_lines():
    when = datetime.datetime(2026, 5, 22, 13, 14, 15)

    assert Screen._format_date_line(when) == "May 22, 2026"
    assert Screen._format_time_line(when) == "13:14:15"


def test_screen_status_is_layout_independent_status_model():
    status = ScreenStatus(title="Pizza is Ready", value="12:34")

    assert status.title == "Pizza is Ready"
    assert status.value == "12:34"
    assert status.highlighted
