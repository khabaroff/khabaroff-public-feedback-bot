from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from bot.config import AppContent
from bot.flow import FeedbackFlowEngine
from bot.fsm import select_clarifying_questions
from bot.llm import validate_review_text
from bot.voice import PendingTranscript


class SessionNotFoundError(KeyError):
    """Raised when an operation references unknown user session."""


@dataclass
class FeedbackSession:
    engine: FeedbackFlowEngine
    pending_transcripts: list[PendingTranscript] = field(default_factory=list)


class FeedbackService:
    def __init__(
        self,
        content: AppContent,
        voice_pipeline: Any,
        llm_client: Any,
        repository: Any,
        notify_owner: Callable[[dict[str, Any]], Awaitable[bool]],
    ) -> None:
        self.content = content
        self.voice_pipeline = voice_pipeline
        self.llm_client = llm_client
        self.repository = repository
        self.notify_owner = notify_owner
        self.sessions: dict[int, FeedbackSession] = {}

    def start_session(self, user_id: int, username: str | None = None) -> None:
        self.sessions[user_id] = FeedbackSession(
            engine=FeedbackFlowEngine(user_id=user_id, username=username)
        )

    def _session(self, user_id: int) -> FeedbackSession:
        session = self.sessions.get(user_id)
        if session is None:
            raise SessionNotFoundError(f"No active session for user {user_id}")
        return session

    def set_contexts(self, user_id: int, contexts: list[str]) -> None:
        self._session(user_id).engine.set_contexts(contexts)

    def set_period(self, user_id: int, period: str) -> None:
        self._session(user_id).engine.set_period(period)

    def add_text_answer(self, user_id: int, answer_key: str, text: str) -> None:
        self._session(user_id).engine.add_answer(answer_key, "text", text)

    async def add_voice_answer(
        self, user_id: int, answer_key: str, audio_bytes: bytes
    ) -> str:
        session = self._session(user_id)
        pending = await self.voice_pipeline.register_voice_answer(answer_key, audio_bytes)
        session.pending_transcripts.append(pending)
        return self.content.texts.get(
            "voice_ack", "🎙 Получил, расшифровываю в фоне — продолжаем."
        )

    async def analyze_and_select_questions(self, user_id: int) -> list[str]:
        session = self._session(user_id)

        # Collect pending voice transcripts so we analyze real text
        if session.pending_transcripts:
            collected = await self.voice_pipeline.collect_transcripts(
                session.pending_transcripts
            )
            for key, transcript in collected.transcripts.items():
                session.engine.add_answer(key, "voice_transcript", transcript)
            session.pending_transcripts = []

        # Build answer text from all answers so far
        answer_parts = [entry.text for entry in session.engine.answers]
        answer_text = "\n".join(answer_parts)

        analysis = await self.llm_client.analyze_answer(
            self.content.analyze_prompt, answer_text
        )
        return select_clarifying_questions(analysis, self.content.clarify_questions)

    async def generate_review(self, user_id: int, signature: str) -> tuple[str, str]:
        session = self._session(user_id)
        session.engine.set_signature(signature)

        if session.pending_transcripts:
            collected = await self.voice_pipeline.collect_transcripts(
                session.pending_transcripts
            )
            for key, transcript in collected.transcripts.items():
                session.engine.add_answer(key, "voice_transcript", transcript)
            session.pending_transcripts = []

        payload = session.engine.build_generation_payload()

        max_attempts = 3
        for attempt in range(max_attempts):
            review_text = await self.llm_client.generate_review(
                self.content.generate_prompt, payload
            )
            violations = validate_review_text(review_text)
            if not violations:
                break
            if attempt == max_attempts - 1:
                raise ValueError(
                    "Generated review violates output constraints: "
                    + ", ".join(sorted(set(violations)))
                )

        session.engine.set_generated_review(review_text)
        thinking = random.choice(self.content.thinking_phrases)
        return thinking, review_text

    def apply_manual_edit(self, user_id: int, review_text: str) -> str:
        session = self._session(user_id)
        session.engine.submit_manual_edit(review_text)
        return session.engine.review_final

    async def complete_review(
        self, user_id: int, is_public: bool
    ) -> tuple[int, dict[str, Any]]:
        session = self._session(user_id)
        session.engine.approve_review()
        session.engine.set_public_permission(is_public)
        payload = session.engine.to_review_record()

        review_id = self.repository.save_review(payload)
        stored = self.repository.get_review(review_id) or payload

        delivered = await self.notify_owner(stored)
        if delivered:
            self.repository.mark_notified(review_id, True)
            stored = self.repository.get_review(review_id) or stored

        return review_id, stored

