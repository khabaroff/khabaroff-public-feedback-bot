from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class AnswerEntry:
    key: str
    source: str
    text: str


class FeedbackFlowEngine:
    def __init__(self, user_id: int, username: str | None = None) -> None:
        self.user_id = user_id
        self.username = username
        self.contexts: list[str] = []
        self.period: str = ""
        self.answers: list[AnswerEntry] = []
        self.signature: str = ""
        self.review_generated: str = ""
        self.review_final: str = ""
        self.is_public: bool | None = None

    def set_contexts(self, contexts: list[str]) -> None:
        self.contexts = [item for item in contexts if item]

    def set_period(self, period: str) -> None:
        self.period = period.strip()

    def add_answer(self, key: str, source: str, text: str) -> None:
        normalized_source = source.strip()
        if normalized_source not in {"text", "voice_transcript"}:
            raise ValueError(f"Unsupported answer source: {source}")
        self.answers.append(AnswerEntry(key=key, source=normalized_source, text=text))

    def set_signature(self, signature: str) -> None:
        self.signature = signature.strip()

    def set_generated_review(self, review_text: str) -> None:
        cleaned = review_text.strip()
        self.review_generated = cleaned
        self.review_final = cleaned

    def submit_manual_edit(self, review_text: str) -> None:
        self.review_final = review_text.strip()

    def approve_review(self) -> None:
        if not self.review_final and self.review_generated:
            self.review_final = self.review_generated
        if not self.review_final:
            raise ValueError("Cannot approve empty review")

    def set_public_permission(self, is_public: bool) -> None:
        self.is_public = bool(is_public)

    def get_raw_answers_text(self) -> str:
        """Return all raw answer texts joined as-is."""
        return "\n\n".join(entry.text for entry in self.answers if entry.text.strip())

    def use_raw_answers(self) -> str:
        """Set raw answers as the final review (no LLM processing)."""
        raw = self.get_raw_answers_text()
        self.review_final = raw
        return raw

    def build_generation_payload(self) -> dict[str, Any]:
        return {
            "context": list(self.contexts),
            "period": self.period,
            "answers": [
                {"key": item.key, "source": item.source, "text": item.text}
                for item in self.answers
            ],
            "signature": self.signature,
        }

    def to_review_record(self) -> dict[str, Any]:
        return {
            "telegram_user_id": str(self.user_id),
            "telegram_username": self.username or "",
            "context": list(self.contexts),
            "period": self.period,
            "answers_raw": [
                {"key": item.key, "source": item.source, "text": item.text}
                for item in self.answers
            ],
            "review_generated": self.review_generated,
            "review_final": self.review_final or self.review_generated,
            "signature": self.signature,
            "is_public": bool(self.is_public),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "notified": False,
        }

