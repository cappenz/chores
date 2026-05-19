from __future__ import annotations

from typing import Protocol

VALID_CHORES = ("dishwasher", "kitchen_trash", "wednesday_trash")


class SpeechChoresApi(Protocol):
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
                    "name": "mark_chore_done",
                    "description": (
                        "Mark one household chore as completed. Valid chores are "
                        "dishwasher, kitchen_trash, and wednesday_trash."
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
                            }
                        },
                        "required": ["chore"],
                    },
                },
            ]
        }
    ]


def handle_tool_call(name: str, args: dict, chores: SpeechChoresApi) -> str:
    if name == "show_emotion":
        emotion = str(args.get("emotion", ""))
        chores.show_emotion(emotion)
        return "ok"

    if name == "mark_chore_done":
        chore = str(args.get("chore", ""))
        result = chores.mark_chore_done(chore, source="speech")
        return result.message

    return f"unknown tool: {name}"

