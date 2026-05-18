from __future__ import annotations

from pathlib import Path

import pytest

from core.people import load_people


def test_load_people_from_toml():
    registry = load_people(Path("data/people.toml"))

    participants = registry.get_chore_participants()

    assert [person.id for person in participants] == [
        "isabelle",
        "guido",
        "daniel",
        "charlotte",
        "thomas",
    ]
    assert registry.get_discord_identity("guido").mention == "<@339570174451646469>"
    assert registry.get_image_asset("guido") == Path("assets/portraits/guido-ghibli.png")


def test_load_people_rejects_duplicate_chore_order(tmp_path):
    people_file = tmp_path / "people.toml"
    people_file.write_text(
        """
[[people]]
id = "one"
display_name = "One"
chore_order = 0

[[people]]
id = "two"
display_name = "Two"
chore_order = 0
""".strip()
    )

    with pytest.raises(ValueError, match="Duplicate chore order"):
        load_people(people_file)
