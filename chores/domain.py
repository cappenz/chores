from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from core.people import PeopleRegistry, load_people

CommandSource = Literal["display", "discord", "speech", "test", "system"]


@dataclass(frozen=True)
class ChoresState:
    dishwasher_status: int
    kitchen_status: int
    wednesday_status: int


@dataclass(frozen=True)
class ChoreDefinition:
    id: str
    display_name: str
    state_field: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class ChoreAssignment:
    chore_id: str
    chore_display_name: str
    person_id: str
    person_display_name: str


@dataclass(frozen=True)
class ChoresStatus:
    assignments: tuple[ChoreAssignment, ...]
    audio_enabled: bool


@dataclass(frozen=True)
class ChoreCommandResult:
    ok: bool
    message: str
    status: ChoresStatus
    state_changed: bool = False
    chore_id: str | None = None
    chore_display_name: str | None = None
    previous_person_id: str | None = None
    previous_person_display_name: str | None = None
    next_person_id: str | None = None
    next_person_display_name: str | None = None


CHORE_DEFINITIONS: tuple[ChoreDefinition, ...] = (
    ChoreDefinition(
        id="dishwasher",
        display_name="Dishwasher",
        state_field="dishwasher_status",
        aliases=("dishwasher", "dish", "dishes"),
    ),
    ChoreDefinition(
        id="kitchen_trash",
        display_name="Kitchen trash",
        state_field="kitchen_status",
        aliases=("kitchen trash", "kitchen"),
    ),
    ChoreDefinition(
        id="wednesday_trash",
        display_name="Wednesday trash",
        state_field="wednesday_status",
        aliases=("wednesday trash", "wednesday", "outside"),
    ),
)


class ChoresService:
    data_dir = "data"
    data_file = "status.json"

    def __init__(self, people: PeopleRegistry | None = None, data_dir: Path | str | None = None) -> None:
        self.people = people or load_people()
        self.participants = self.people.get_chore_participants()
        self.data_dir = str(data_dir) if data_dir is not None else self.__class__.data_dir
        self.audio_enabled = True
        self.load_state()

    def get_status(self) -> ChoresStatus:
        assignments = tuple(
            self._assignment_for_chore(chore)
            for chore in CHORE_DEFINITIONS
        )
        return ChoresStatus(assignments=assignments, audio_enabled=self.audio_enabled)

    def read_chores(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (assignment.chore_id, assignment.person_id)
            for assignment in self.get_status().assignments
        )

    def mark_chore_done(self, chore: str, source: CommandSource = "system") -> ChoreCommandResult:
        return self.write_chore(chore, "next", source=source)

    def write_chore(self, chore: str, person: str, source: CommandSource = "system") -> ChoreCommandResult:
        del source
        chore_definition = self.normalize_chore(chore)
        if chore_definition is None:
            return ChoreCommandResult(
                ok=False,
                message=(
                    "Please use the words 'dishwasher', 'wednesday' or "
                    "'kitchen' to talk about what you need."
                ),
                status=self.get_status(),
            )

        current_index = self._get_chore_index(chore_definition)
        target_index = self._target_person_index(person, current_index)
        if target_index is None:
            return ChoreCommandResult(
                ok=False,
                message=(
                    "Please use 'next' or one of these names: "
                    f"{', '.join(participant.display_name for participant in self.participants)}."
                ),
                status=self.get_status(),
                chore_id=chore_definition.id,
                chore_display_name=chore_definition.display_name,
            )

        previous_person = self.participants[current_index]
        next_person = self.participants[target_index]
        state_changed = current_index != target_index
        if state_changed:
            self._set_chore_index(chore_definition, target_index)
            self.save_state()

        if state_changed:
            message = f"It's {next_person.display_name}'s turn to do the {chore_definition.display_name}"
        else:
            message = f"{next_person.display_name} is already assigned to the {chore_definition.display_name}"

        return ChoreCommandResult(
            ok=True,
            chore_id=chore_definition.id,
            chore_display_name=chore_definition.display_name,
            previous_person_id=previous_person.id,
            previous_person_display_name=previous_person.display_name,
            next_person_id=next_person.id,
            next_person_display_name=next_person.display_name,
            message=message,
            status=self.get_status(),
            state_changed=state_changed,
        )

    def set_audio_enabled(self, enabled: bool, source: CommandSource = "system") -> ChoreCommandResult:
        del source
        self.audio_enabled = enabled
        message = "Audio announcements enabled" if enabled else "Audio announcements disabled"
        return ChoreCommandResult(ok=True, message=message, status=self.get_status())

    def get_audio_enabled(self) -> bool:
        return self.audio_enabled

    def load_state(self) -> None:
        file_name = self._data_path()
        if file_name.exists():
            with file_name.open("r") as file:
                status = json.load(file)
            self.state = ChoresState(**status)
        else:
            self.state = ChoresState(0, 0, 0)
            self.save_state()

    def save_state(self) -> None:
        self._data_path().parent.mkdir(parents=True, exist_ok=True)
        with self._data_path().open("w") as file:
            json.dump(asdict(self.state), file)

    def update_state(self, dishwasher_status: int, kitchen_status: int, wednesday_status: int) -> None:
        self.state = ChoresState(dishwasher_status, kitchen_status, wednesday_status)
        self.save_state()

    def normalize_chore(self, chore: str) -> ChoreDefinition | None:
        content = chore.casefold()
        for chore_definition in CHORE_DEFINITIONS:
            if chore_definition.id == content:
                return chore_definition
            if any(alias in content for alias in chore_definition.aliases):
                return chore_definition
        return None

    def _assignment_for_chore(self, chore: ChoreDefinition) -> ChoreAssignment:
        person = self.participants[self._get_chore_index(chore)]
        return ChoreAssignment(
            chore_id=chore.id,
            chore_display_name=chore.display_name,
            person_id=person.id,
            person_display_name=person.display_name,
        )

    def _get_chore_index(self, chore: ChoreDefinition) -> int:
        return int(getattr(self.state, chore.state_field)) % len(self.participants)

    def _set_chore_index(self, chore: ChoreDefinition, value: int) -> None:
        state = asdict(self.state)
        state[chore.state_field] = value
        self.state = ChoresState(**state)

    def _target_person_index(self, person: str, current_index: int) -> int | None:
        content = person.strip().casefold()
        if content == "next":
            return (current_index + 1) % len(self.participants)
        for index, participant in enumerate(self.participants):
            if content in {participant.id.casefold(), participant.display_name.casefold()}:
                return index
        return None

    def _data_path(self) -> Path:
        return Path(self.data_dir) / self.__class__.data_file

