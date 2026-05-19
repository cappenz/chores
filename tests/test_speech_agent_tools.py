from __future__ import annotations

import asyncio

from chores import ChoresService
from speech_agent.live import INITIAL_GREETING_PROMPT, _build_config, _send_initial_greeting
from speech_agent.tools import build_tools, handle_tool_call


def test_speech_agent_owns_gemini_tool_definitions():
    tools = build_tools()
    declarations = tools[0]["function_declarations"]

    assert {declaration["name"] for declaration in declarations} == {
        "show_emotion",
        "mark_chore_done",
    }


def test_speech_chore_tool_lists_valid_chores():
    tools = build_tools()
    chore_tool = next(
        declaration
        for declaration in tools[0]["function_declarations"]
        if declaration["name"] == "mark_chore_done"
    )

    assert chore_tool["parameters"]["properties"]["chore"]["enum"] == [
        "dishwasher",
        "kitchen_trash",
        "wednesday_trash",
    ]


def test_speech_agent_uses_schedar_voice():
    config = _build_config("gemini-3.1-flash-live-preview")

    assert config["speech_config"]["voice_config"]["prebuilt_voice_config"]["voice_name"] == "Schedar"


def test_initial_greeting_prompts_model_to_speak():
    class FakeSession:
        def __init__(self):
            self.calls = []

        async def send_client_content(self, *, turns, turn_complete):
            self.calls.append((turns, turn_complete))

    session = FakeSession()

    asyncio.run(_send_initial_greeting(session))

    assert session.calls == [
        (
            {
                "role": "user",
                "parts": [{"text": INITIAL_GREETING_PROMPT}],
            },
            True,
        )
    ]


def test_speech_chore_tool_delegates_to_domain(isolated_data_dir):
    chores = ChoresService()

    result = handle_tool_call("mark_chore_done", {"chore": "dishwasher"}, chores)

    assert "Guido" in result
    assert chores.state.dishwasher_status == 1


def test_speech_chore_tool_rejects_unknown_chore(isolated_data_dir):
    chores = ChoresService()

    result = handle_tool_call("mark_chore_done", {"chore": "vacuum"}, chores)

    assert "Please use the words" in result
    assert chores.state.dishwasher_status == 0


def test_speech_emotion_tool_delegates_to_app_api():
    class FakeChores:
        def __init__(self):
            self.emotions = []

        def mark_chore_done(self, chore: str, source: str = "speech"):
            raise AssertionError("mark_chore_done should not be called")

        def get_status(self):
            return None

        def show_emotion(self, emotion: str):
            self.emotions.append(emotion)

    chores = FakeChores()

    result = handle_tool_call("show_emotion", {"emotion": "happy"}, chores)

    assert result == "ok"
    assert chores.emotions == ["happy"]
