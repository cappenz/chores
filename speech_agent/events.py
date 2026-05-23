from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


AssistantEventKind = Literal["timer_finished", "timer_repeat"]


@dataclass(frozen=True)
class AssistantEvent:
    kind: AssistantEventKind
    prompt: str
