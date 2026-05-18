from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PEOPLE_FILE = Path("data/people.toml")


@dataclass(frozen=True)
class DiscordIdentity:
    user_id: str

    @property
    def mention(self) -> str:
        return f"<@{self.user_id}>"


@dataclass(frozen=True)
class Person:
    id: str
    display_name: str
    chore_participant: bool
    chore_order: int
    discord: DiscordIdentity | None
    image: Path | None


@dataclass(frozen=True)
class PeopleRegistry:
    people: tuple[Person, ...]

    def get_person(self, person_id: str) -> Person:
        for person in self.people:
            if person.id == person_id:
                return person
        raise KeyError(f"Unknown person id: {person_id}")

    def get_chore_participants(self) -> list[Person]:
        participants = [person for person in self.people if person.chore_participant]
        return sorted(participants, key=lambda person: person.chore_order)

    def get_discord_identity(self, person_id: str) -> DiscordIdentity | None:
        return self.get_person(person_id).discord

    def get_image_asset(self, person_id: str) -> Path | None:
        return self.get_person(person_id).image


def load_people(path: Path = DEFAULT_PEOPLE_FILE) -> PeopleRegistry:
    with path.open("rb") as file:
        data = tomllib.load(file)

    people_data = data.get("people", [])
    people: list[Person] = []
    seen_ids: set[str] = set()
    seen_orders: set[int] = set()

    for item in people_data:
        person_id = str(item["id"])
        if person_id in seen_ids:
            raise ValueError(f"Duplicate person id: {person_id}")
        seen_ids.add(person_id)

        chore_order = int(item.get("chore_order", len(seen_orders)))
        chore_participant = bool(item.get("chore_participant", True))
        if chore_participant:
            if chore_order in seen_orders:
                raise ValueError(f"Duplicate chore order: {chore_order}")
            seen_orders.add(chore_order)

        discord_data = item.get("discord")
        discord = None
        if discord_data and discord_data.get("user_id"):
            discord = DiscordIdentity(user_id=str(discord_data["user_id"]))

        image_path = item.get("image")
        people.append(
            Person(
                id=person_id,
                display_name=str(item["display_name"]),
                chore_participant=chore_participant,
                chore_order=chore_order,
                discord=discord,
                image=Path(str(image_path)) if image_path else None,
            )
        )

    if not people:
        raise ValueError("People file must define at least one person")
    if not any(person.chore_participant for person in people):
        raise ValueError("People file must define at least one chore participant")

    return PeopleRegistry(tuple(people))

