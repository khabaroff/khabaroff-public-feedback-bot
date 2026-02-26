from __future__ import annotations

import random
from enum import StrEnum

_PRIORITY_FIELDS = ("moment", "style", "context")


class FeedbackState(StrEnum):
    START = "START"
    CONTEXT_SELECT = "CONTEXT_SELECT"
    PERIOD_SELECT = "PERIOD_SELECT"
    OPEN_QUESTION = "OPEN_QUESTION"
    CLARIFYING_Q1 = "CLARIFYING_Q1"
    CLARIFYING_Q2 = "CLARIFYING_Q2"
    SIGNATURE = "SIGNATURE"
    GENERATING = "GENERATING"
    REVIEW_CONFIRM = "REVIEW_CONFIRM"
    REVIEW_EDIT = "REVIEW_EDIT"
    PUBLIC_PERMISSION = "PUBLIC_PERMISSION"
    DONE = "DONE"


def select_clarifying_questions(
    analysis: dict[str, bool],
    question_bank: dict[str, list[str]],
) -> list[str]:
    if analysis.get("enough", False):
        return []

    questions: list[str] = []
    for field in _PRIORITY_FIELDS:
        if not analysis.get(field, False):
            candidates = question_bank.get(field, [])
            if candidates:
                questions.append(random.choice(candidates))
        if len(questions) == 2:
            break

    return questions


try:
    from aiogram.fsm.state import State, StatesGroup

    class FeedbackStatesGroup(StatesGroup):
        start = State()
        context_select = State()
        period_select = State()
        open_question = State()
        clarifying_q1 = State()
        clarifying_q2 = State()
        signature = State()
        generating = State()
        review_confirm = State()
        review_edit = State()
        public_permission = State()
        done = State()

except Exception:  # pragma: no cover - aiogram optional for non-runtime tests
    FeedbackStatesGroup = None  # type: ignore
