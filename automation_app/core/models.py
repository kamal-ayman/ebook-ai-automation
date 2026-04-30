from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List


@dataclass(frozen=True)
class QuestionOption:
    """Single answer choice extracted from the quiz page."""

    index: int
    text: str
    input_id: str
    value: str


@dataclass(frozen=True)
class QuizQuestion:
    """Normalized question model passed to the Gemini solver."""

    question_id: str
    question_number: str
    text: str
    options: List[QuestionOption]


class RunStatus(str, Enum):
    """High-level automation state used by the UI."""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    STOPPED = "STOPPED"
