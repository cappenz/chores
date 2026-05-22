from __future__ import annotations

from chores import ChoresService, ChoresState


def test_state_is_saved_and_loaded(isolated_data_dir):
    app = ChoresService()
    app.update_state(1, 2, 3)

    reloaded = ChoresService()

    assert reloaded.state == ChoresState(1, 2, 3)
    assert (isolated_data_dir / "status.json").exists()


def test_status_reports_assignments_without_external_services(isolated_data_dir):
    app = ChoresService()

    status = app.get_status()

    assert [assignment.chore_id for assignment in status.assignments] == [
        "dishwasher",
        "kitchen_trash",
        "wednesday_trash",
    ]
    assert [assignment.person_display_name for assignment in status.assignments] == [
        "Isabelle",
        "Isabelle",
        "Isabelle",
    ]


def test_read_chores_reports_canonical_assignments(isolated_data_dir):
    app = ChoresService()

    assert app.read_chores() == (
        ("dishwasher", "isabelle"),
        ("kitchen_trash", "isabelle"),
        ("wednesday_trash", "isabelle"),
    )


def test_mark_chore_done_rotates_assignment(isolated_data_dir):
    app = ChoresService()

    result = app.mark_chore_done("dishwasher", source="test")

    assert result.ok
    assert result.state_changed
    assert result.chore_id == "dishwasher"
    assert result.previous_person_display_name == "Isabelle"
    assert result.next_person_display_name == "Guido"
    assert app.state == ChoresState(1, 0, 0)


def test_write_chore_next_rotates_assignment(isolated_data_dir):
    app = ChoresService()

    result = app.write_chore("dishwasher", "next", source="test")

    assert result.ok
    assert result.state_changed
    assert result.previous_person_display_name == "Isabelle"
    assert result.next_person_display_name == "Guido"
    assert app.state == ChoresState(1, 0, 0)


def test_write_chore_assigns_specific_person(isolated_data_dir):
    app = ChoresService()

    result = app.write_chore("dishwasher", "charlotte", source="test")

    assert result.ok
    assert result.state_changed
    assert result.previous_person_display_name == "Isabelle"
    assert result.next_person_display_name == "Charlotte"
    assert app.state == ChoresState(3, 0, 0)


def test_write_chore_to_current_person_is_noop(isolated_data_dir):
    app = ChoresService()

    result = app.write_chore("dishwasher", "isabelle", source="test")

    assert result.ok
    assert not result.state_changed
    assert result.message == "Isabelle is already assigned to the Dishwasher"
    assert app.state == ChoresState(0, 0, 0)


def test_write_chore_rejects_unknown_person(isolated_data_dir):
    app = ChoresService()

    result = app.write_chore("dishwasher", "zach", source="test")

    assert not result.ok
    assert app.state == ChoresState(0, 0, 0)


def test_wednesday_trash_alias_matches_wednesday_chore(isolated_data_dir):
    app = ChoresService()

    result = app.mark_chore_done("wednesday trash is done", source="test")

    assert result.ok
    assert result.chore_id == "wednesday_trash"
    assert app.state == ChoresState(0, 0, 1)


def test_unknown_chore_returns_rejection(isolated_data_dir):
    app = ChoresService()

    result = app.mark_chore_done("vacuum", source="test")

    assert not result.ok
    assert app.state == ChoresState(0, 0, 0)


def test_audio_toggle_is_domain_state(isolated_data_dir):
    app = ChoresService()

    result = app.set_audio_enabled(False, source="test")

    assert result.ok
    assert not app.get_audio_enabled()
    assert not result.status.audio_enabled
