from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from bot.config import AppContent
from bot.flow import FeedbackFlowEngine
from bot.fsm import select_clarifying_questions
from bot.llm import validate_review_text
from bot.voice import PendingTranscript

logger = logging.getLogger(__name__)


class SessionNotFoundError(KeyError):
    """Raised when an operation references unknown user session."""


@dataclass
class FeedbackSession:
    engine: FeedbackFlowEngine
    started_at: float = field(default_factory=time.time)
    completed: bool = False
    abandon_notified: bool = False
    pending_transcripts: list[PendingTranscript] = field(default_factory=list)


class FeedbackService:
    def __init__(
        self,
        content: AppContent,
        voice_pipeline: Any,
        llm_client: Any,
        repository: Any,
        notify_owner: Callable[[dict[str, Any]], Awaitable[bool]],
        notify_owner_text: Callable[[str], Awaitable[bool]] | None = None,
    ) -> None:
        self.content = content
        self.voice_pipeline = voice_pipeline
        self.llm_client = llm_client
        self.repository = repository
        self.notify_owner = notify_owner
        self.notify_owner_text = notify_owner_text
        self.sessions: dict[int, FeedbackSession] = {}

    def start_session(self, user_id: int, username: str | None = None) -> None:
        self.sessions[user_id] = FeedbackSession(
            engine=FeedbackFlowEngine(user_id=user_id, username=username)
        )

    async def notify_session_started(self, user_id: int) -> None:
        session = self.sessions.get(user_id)
        if not session or not self.notify_owner_text:
            return
        from bot.notification import format_session_started
        text = format_session_started(user_id, session.engine.username)
        await self.notify_owner_text(text)

    async def check_abandoned_sessions(self, timeout_minutes: int = 60) -> None:
        if not self.notify_owner_text:
            return
        from bot.notification import format_session_abandoned
        now = time.time()
        for user_id, session in list(self.sessions.items()):
            if session.completed or session.abandon_notified:
                continue
            elapsed_min = int((now - session.started_at) / 60)
            if elapsed_min >= timeout_minutes:
                text = format_session_abandoned(
                    user_id, session.engine.username, elapsed_min
                )
                await self.notify_owner_text(text)
                session.abandon_notified = True

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

        # Use LLM-generated questions; fallback to question bank
        llm_questions = analysis.get("questions", [])
        if isinstance(llm_questions, list) and len(llm_questions) >= 2:
            return llm_questions[:2]
        # Fallback: LLM returned <2 questions — fill from bank
        fallback = select_clarifying_questions(analysis, self.content.clarify_questions)
        # Merge: keep whatever LLM gave, fill rest from bank
        merged: list[str] = list(llm_questions) if isinstance(llm_questions, list) else []
        for q in fallback:
            if len(merged) >= 2:
                break
            if q not in merged:
                merged.append(q)
        return merged[:2]

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

    def use_raw_answers(self, user_id: int) -> str:
        session = self._session(user_id)
        return session.engine.use_raw_answers()

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
        session.completed = True
        payload = session.engine.to_review_record()

        review_id = self.repository.save_review(payload)
        stored = self.repository.get_review(review_id) or payload

        delivered = await self.notify_owner(stored)
        if delivered:
            self.repository.mark_notified(review_id, True)
            stored = self.repository.get_review(review_id) or stored

        return review_id, stored

