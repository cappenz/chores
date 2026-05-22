from __future__ import annotations

import asyncio

from chores import ChoresService
from speech_agent.live import INITIAL_GREETING_PROMPT, _build_config, _send_initial_greeting
from speech_agent.tools import (
    _search_state,
    build_tools,
    handle_tool_call,
    reset_web_search_counter,
    web_search,
)


def test_speech_agent_owns_gemini_tool_definitions():
    tools = build_tools()
    declarations = tools[0]["function_declarations"]

    assert {declaration["name"] for declaration in declarations} == {
        "show_emotion",
        "mark_chore_done",
        "web_search",
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


def test_web_search_tool_accepts_queries():
    tools = build_tools()
    search_tool = next(
        declaration
        for declaration in tools[0]["function_declarations"]
        if declaration["name"] == "web_search"
    )

    queries = search_tool["parameters"]["properties"]["queries"]

    assert queries["type"] == "array"
    assert queries["items"]["type"] == "string"
    assert search_tool["parameters"]["required"] == ["queries"]


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

    result = asyncio.run(
        handle_tool_call("mark_chore_done", {"chore": "dishwasher"}, chores)
    )

    assert "Guido" in result
    assert chores.state.dishwasher_status == 1


def test_speech_chore_tool_rejects_unknown_chore(isolated_data_dir):
    chores = ChoresService()

    result = asyncio.run(
        handle_tool_call("mark_chore_done", {"chore": "vacuum"}, chores)
    )

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

    result = asyncio.run(handle_tool_call("show_emotion", {"emotion": "happy"}, chores))

    assert result == "ok"
    assert chores.emotions == ["happy"]


def test_web_search_handles_empty_queries():
    reset_web_search_counter()

    result = web_search([])

    assert result == "No queries provided."


def test_web_search_requires_api_key(monkeypatch):
    reset_web_search_counter()
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)

    result = web_search(["current weather"])

    assert result == (
        "Web search is not configured. Set BRAVE_API_KEY to enable Brave Search."
    )


def test_web_search_enforces_session_limit(monkeypatch):
    reset_web_search_counter()
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")
    _search_state["search_count"] = 49

    result = web_search(["one", "two"])

    assert "Search limit exceeded" in result


def test_web_search_formats_mocked_brave_results(monkeypatch):
    reset_web_search_counter()
    monkeypatch.setenv("BRAVE_API_KEY", "test-key")

    def search_single_query(query: str, api_key: str):
        assert api_key == "test-key"
        return {
            "query": query,
            "results": {
                "web": {
                    "results": [
                        {
                            "title": f"Title for {query}",
                            "description": f"Snippet for {query}",
                            "url": f"https://example.com/{query}",
                        }
                    ]
                }
            },
        }

    monkeypatch.setattr("speech_agent.tools._search_single_query", search_single_query)

    result = web_search(["first", "second"])

    assert "## first" in result
    assert "Title for first: Snippet for first (https://example.com/first)" in result
    assert "## second" in result
    assert _search_state["search_count"] == 2


def test_web_search_tool_dispatches(monkeypatch):
    class FakeChores:
        def mark_chore_done(self, chore: str, source: str = "speech"):
            raise AssertionError("mark_chore_done should not be called")

        def get_status(self):
            return None

        def show_emotion(self, emotion: str):
            raise AssertionError("show_emotion should not be called")

    monkeypatch.setattr(
        "speech_agent.tools.web_search",
        lambda queries: f"searched {queries}",
    )

    result = asyncio.run(
        handle_tool_call("web_search", {"queries": ["test"]}, FakeChores())
    )

    assert result == "searched ['test']"
