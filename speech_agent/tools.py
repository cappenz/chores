from __future__ import annotations

import asyncio
import json
import os
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Protocol

VALID_CHORES = ("dishwasher", "kitchen_trash", "wednesday_trash")
VALID_CHORE_PEOPLE = ("next", "isabelle", "guido", "daniel", "charlotte", "thomas")
BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
MAX_SEARCHES_PER_SESSION = 50
MAX_PARALLEL_SEARCHES = 5
SEARCH_RESULT_LIMIT = 5
SEARCH_TIMEOUT_SECONDS = 10
_search_state = {"search_count": 0}


class SpeechChoresApi(Protocol):
    def read_chores(self) -> tuple[tuple[str, str], ...]:
        ...

    def write_chore(self, chore: str, person: str, source: str = "speech"):
        ...

    def mark_chore_done(self, chore: str, source: str = "speech"):
        ...

    def get_status(self):
        ...

    def show_emotion(self, emotion: str):
        ...


def build_tools() -> list[dict]:
    return [
        {
            "function_declarations": [
                {
                    "name": "show_emotion",
                    "description": "Display or express an emotion visually.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "emotion": {
                                "type": "string",
                                "description": "The emotion to show, e.g. happy, scared, excited.",
                            }
                        },
                        "required": ["emotion"],
                    },
                },
                {
                    "name": "read_chores",
                    "description": (
                        "Read the current household chore assignments. Use this when "
                        "the user asks who has a chore, whose turn it is, or what the "
                        "current chore status is."
                    ),
                },
                {
                    "name": "write_chore",
                    "description": (
                        "Set the person responsible for one household chore. Use "
                        "person='next' to advance that chore to the next person in the "
                        "normal rotation. Use a specific person when the user asks to "
                        "assign the chore to someone or skip someone in the rotation."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "chore": {
                                "type": "string",
                                "enum": list(VALID_CHORES),
                                "description": (
                                    "Canonical chore id: dishwasher, kitchen_trash, "
                                    "or wednesday_trash. Use dishwasher for dishes."
                                ),
                            },
                            "person": {
                                "type": "string",
                                "enum": list(VALID_CHORE_PEOPLE),
                                "description": (
                                    "The person to assign the chore to, or 'next' to "
                                    "advance to the next person in the chore rotation."
                                ),
                            }
                        },
                        "required": ["chore", "person"],
                    },
                },
                {
                    "name": "web_search",
                    "description": (
                        "Search the web for current or factual information that may be "
                        "outside the model's knowledge. Use concise search queries."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "queries": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": (
                                    "One or more web search queries. Use multiple queries "
                                    "only when they cover distinct facts to verify."
                                ),
                            }
                        },
                        "required": ["queries"],
                    },
                },
            ]
        }
    ]


def reset_web_search_counter() -> None:
    _search_state["search_count"] = 0


async def handle_tool_call(name: str, args: dict, chores: SpeechChoresApi) -> str:
    if name == "show_emotion":
        emotion = str(args.get("emotion", ""))
        chores.show_emotion(emotion)
        return "ok"

    if name == "read_chores":
        return _format_chore_assignments(chores.read_chores())

    if name == "write_chore":
        chore = str(args.get("chore", ""))
        person = str(args.get("person", ""))
        result = chores.write_chore(chore, person, source="speech")
        return result.message

    if name == "web_search":
        queries = _coerce_queries(args.get("queries"))
        return await asyncio.to_thread(web_search, queries)

    return f"unknown tool: {name}"


def _format_chore_assignments(assignments: tuple[tuple[str, str], ...]) -> str:
    if not assignments:
        return "No chore assignments are available."
    return "\n".join(f"{chore}: {person}" for chore, person in assignments)


def web_search(queries: list[str]) -> str:
    if not queries:
        return "No queries provided."

    current_count = _search_state["search_count"]
    if current_count + len(queries) > MAX_SEARCHES_PER_SESSION:
        return (
            f"Search limit exceeded: already performed {current_count} searches, "
            f"requesting {len(queries)} more, but maximum is "
            f"{MAX_SEARCHES_PER_SESSION} per session."
        )

    api_key = os.getenv("BRAVE_API_KEY", "").strip()
    if not api_key:
        return "Web search is not configured. Set BRAVE_API_KEY to enable Brave Search."

    results = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SEARCHES) as executor:
        future_to_query = {
            executor.submit(_search_single_query, query, api_key): query
            for query in queries
        }
        for future in as_completed(future_to_query):
            query = future_to_query[future]
            try:
                results.append(future.result())
            except Exception as error:
                results.append({"query": query, "results": {"error": str(error)}})

    _search_state["search_count"] += len(queries)
    query_order = {query: index for index, query in enumerate(queries)}
    results.sort(key=lambda item: query_order.get(item["query"], len(queries)))
    return _format_results(results)


def _coerce_queries(value: object) -> list[str]:
    if isinstance(value, str):
        candidates = [value]
    elif isinstance(value, list):
        candidates = value
    else:
        candidates = []
    return [str(query).strip() for query in candidates if str(query).strip()]


def _search_single_query(query: str, api_key: str) -> dict:
    params = urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(
        f"{BRAVE_API_URL}?{params}",
        headers={
            "Accept": "application/json",
            "X-Subscription-Token": api_key,
        },
    )
    with urllib.request.urlopen(request, timeout=SEARCH_TIMEOUT_SECONDS) as response:
        body = response.read().decode("utf-8")
    return {"query": query, "results": json.loads(body)}


def _format_results(search_results: list[dict]) -> str:
    output = []
    for item in search_results:
        query = item["query"]
        results = item["results"]
        output.append(f"## {query}\n")

        error = results.get("error")
        if error:
            output.append(f"Search failed: {error}\n")
            continue

        web_results = results.get("web", {}).get("results", [])
        if not web_results:
            output.append("No results found.\n")
            continue

        for result in web_results[:SEARCH_RESULT_LIMIT]:
            title = result.get("title", "").strip()
            description = result.get("description", "").strip()
            url = result.get("url", "").strip()
            if title and description and url:
                output.append(f"- {title}: {description} ({url})")
            elif description:
                output.append(f"- {description}")

        output.append("")

    return "\n".join(output)

