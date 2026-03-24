from __future__ import annotations

import asyncio
import random
import unittest
from dataclasses import dataclass
from typing import Any

from bot.config import AppContent
from bot.db import ReviewRepository
from bot.service import FeedbackService
from bot.voice import PendingTranscript, TranscriptCollection


class FakeVoicePipeline:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bytes]] = []

    async def register_voice_answer(self, answer_key: str, audio_bytes: bytes) -> PendingTranscript:
        self.calls.append((answer_key, audio_bytes))
        return PendingTranscript(answer_key=answer_key, job_id=f"job-{answer_key}")

    async def collect_transcripts(
        self, pending_jobs: list[PendingTranscript], max_attempts: int = 5
    ) -> TranscriptCollection:
        transcripts = {item.answer_key: f"tx-{item.answer_key}" for item in pending_jobs}
        return TranscriptCollection(transcripts=transcripts, failed=[], pending=[])


class FakeLLMClient:
    def __init__(self) -> None:
        self.generated_payload: dict[str, Any] | None = None
        self.analyze_result: dict[str, Any] = {
            "context": False, "moment": False, "style": False, "questions": [],
        }

    async def generate_review(self, prompt: str, payload: dict[str, Any]) -> str:
        self.generated_payload = payload
        return "Draft review"

    async def analyze_answer(self, system_prompt: str, answer_text: str) -> dict[str, Any]:
        return dict(self.analyze_result)


class FakeNotifier:
    def __init__(self) -> None:
        self.called_with: dict[str, Any] | None = None

    async def __call__(self, review: dict[str, Any]) -> bool:
        self.called_with = review
        return True


class FakeFailingNotifier:
    async def __call__(self, review: dict[str, Any]) -> bool:
        return False


@dataclass
class FakeRepo:
    rows: dict[int, dict[str, Any]]
    last_id: int = 0

    def save_review(self, payload: dict[str, Any]) -> int:
        self.last_id += 1
        self.rows[self.last_id] = dict(payload)
        return self.last_id

    def mark_notified(self, review_id: int, notified: bool) -> None:
        self.rows[review_id]["notified"] = notified

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        return self.rows.get(review_id)

    def update_review_fields(self, review_id: int, **fields: Any) -> None:
        if review_id in self.rows:
            self.rows[review_id].update(fields)


class TestServiceOrchestration(unittest.IsolatedAsyncioTestCase):
    def _content(self) -> AppContent:
        return AppContent(
            texts={"greeting_intro": "hello", "cta_start": "go", "voice_ack": "ack"},
            thinking_phrases=["one", "two"],
            generate_prompt="generate",
            rephrase_prompt="rephrase",
            analyze_prompt="analyze",
            clarify_questions={
                "moment": ["moment q1"],
                "style": ["style q1"],
                "context": ["context q1"],
            },
            review_template={},
        )

    async def test_voice_answers_are_merged_before_generation(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        notifier = FakeNotifier()
        repo = FakeRepo(rows={})

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=1, username="demo")
        svc.set_contexts(1, ["work"])
        svc.set_period(1, "recent")
        await svc.add_voice_answer(1, "open", b"voice-bytes")
        svc.add_text_answer(1, "clarify_1", "text")

        thinking, draft = await svc.generate_review(user_id=1, signature="Anna")

        self.assertIn(thinking, ["one", "two"])
        self.assertEqual(draft, "Draft review")
        assert llm.generated_payload is not None
        answer_sources = [item["source"] for item in llm.generated_payload["answers"]]
        self.assertIn("voice_transcript", answer_sources)

    async def test_generation_payload_contains_context_period_answers_and_signature(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        notifier = FakeNotifier()
        repo = FakeRepo(rows={})

        svc = FeedbackService(
            content=self._content(),
            voice_pipeline=voice,
            llm_client=llm,
            repository=repo,
            notify_owner=notifier,
        )
        svc.start_session(user_id=11, username="demo")
        svc.set_contexts(11, ["study", "work"])
        svc.set_period(11, "2025-2026")
        svc.add_text_answer(11, "open", "Main answer")
        svc.add_text_answer(11, "clarify_1", "Clarification one")
        svc.add_text_answer(11, "clarify_2", "Clarification two")

        await svc.generate_review(user_id=11, signature="Anna, UX-designer")

        assert llm.generated_payload is not None
        payload = llm.generated_payload

        self.assertEqual(payload["context"], ["study", "work"])
        self.assertEqual(payload["period"], "2025-2026")
        self.assertEqual(payload["signature"], "Anna, UX-designer")

        self.assertEqual(len(payload["answers"]), 3)
        self.assertEqual(payload["answers"][0]["key"], "open")
        self.assertEqual(payload["answers"][0]["text"], "Main answer")
        self.assertEqual(payload["answers"][1]["key"], "clarify_1")
        self.assertEqual(payload["answers"][1]["text"], "Clarification one")
        self.assertEqual(payload["answers"][2]["key"], "clarify_2")
        self.assertEqual(payload["answers"][2]["text"], "Clarification two")

    async def test_notification_updates_notified_flag_on_success(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=2, username="demo")
        svc.set_contexts(2, ["study"])
        svc.set_period(2, "2025")
        svc.add_text_answer(2, "open", "Answer")
        await svc.generate_review(user_id=2, signature="Ilya")
        review_id, stored = await svc.complete_review(user_id=2, is_public=True)

        self.assertEqual(review_id, 1)
        self.assertTrue(stored["notified"])

    async def test_notification_failure_keeps_notified_false(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeFailingNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=3, username="demo")
        svc.set_contexts(3, ["life"])
        svc.set_period(3, "old")
        svc.add_text_answer(3, "open", "Answer")
        await svc.generate_review(user_id=3, signature="Maxim")
        review_id, stored = await svc.complete_review(user_id=3, is_public=False)

        self.assertEqual(review_id, 1)
        self.assertFalse(stored["notified"])

    async def test_analyze_uses_llm_questions(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        llm.analyze_result = {
            "context": True, "moment": False, "style": False,
            "questions": ["LLM Q1 about moment", "LLM Q2 about style"],
        }
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=20, username="demo")
        svc.set_contexts(20, ["work"])
        svc.set_period(20, "recent")
        svc.add_text_answer(20, "open", "Generic answer")

        questions = await svc.analyze_and_select_questions(20)
        self.assertEqual(len(questions), 2)
        self.assertEqual(questions[0], "LLM Q1 about moment")
        self.assertEqual(questions[1], "LLM Q2 about style")

    async def test_analyze_falls_back_to_bank_when_no_llm_questions(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        llm.analyze_result = {
            "context": True, "moment": False, "style": True,
            "questions": [],
        }
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=21, username="demo")
        svc.set_contexts(21, ["study"])
        svc.set_period(21, "recent")
        svc.add_text_answer(21, "open", "Generic answer")

        questions = await svc.analyze_and_select_questions(21)
        self.assertEqual(len(questions), 2)

    async def test_analyze_always_returns_two_questions(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        llm.analyze_result = {
            "context": True, "moment": True, "style": True,
            "questions": [],
        }
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=22, username="demo")
        svc.set_contexts(22, ["work"])
        svc.set_period(22, "recent")
        svc.add_text_answer(22, "open", "Very detailed answer")

        questions = await svc.analyze_and_select_questions(22)
        self.assertEqual(len(questions), 2)

    async def test_analyze_collects_voice_before_analysis(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        llm.analyze_result = {
            "context": False, "moment": False, "style": False,
            "questions": ["Q1", "Q2"],
        }
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=23, username="demo")
        svc.set_contexts(23, ["work"])
        svc.set_period(23, "recent")
        await svc.add_voice_answer(23, "open", b"voice-bytes")

        questions = await svc.analyze_and_select_questions(23)
        self.assertEqual(len(questions), 2)
        session = svc.sessions[23]
        self.assertEqual(len(session.pending_transcripts), 0)


    async def test_raw_review_notifies_owner(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(content=self._content(), voice_pipeline=voice, llm_client=llm, repository=repo, notify_owner=notifier)
        svc.start_session(user_id=40, username="rawuser")
        svc.set_contexts(40, ["work"])
        svc.set_period(40, "recent")
        svc.add_text_answer(40, "open", "My raw answer")
        svc.add_text_answer(40, "clarify_1", "Clarification")
        await svc.generate_review(user_id=40, signature="Test User")

        # Use raw answers instead of LLM-generated text
        raw = svc.use_raw_answers(40)
        self.assertIn("My raw answer", raw)

        review_id, stored = await svc.complete_review(user_id=40, is_public=False)
        self.assertTrue(stored["notified"])
        self.assertIsNotNone(notifier.called_with)
        self.assertEqual(notifier.called_with["review_final"], raw)


    async def test_draft_saved_on_each_step(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=50, username="drafter")

        # Draft created on start
        session = svc.sessions[50]
        self.assertIsNotNone(session.draft_id)
        draft = repo.get_review(session.draft_id)
        self.assertIsNotNone(draft)
        self.assertEqual(draft["status"], "draft")

        # Contexts saved
        svc.set_contexts(50, ["work", "study"])
        draft = repo.get_review(session.draft_id)
        self.assertEqual(draft["context"], ["work", "study"])

        # Period saved
        svc.set_period(50, "recent")
        draft = repo.get_review(session.draft_id)
        self.assertEqual(draft["period"], "recent")

        # Text answer saved
        svc.add_text_answer(50, "open", "My main answer")
        draft = repo.get_review(session.draft_id)
        self.assertEqual(len(draft["answers_raw"]), 1)
        self.assertEqual(draft["answers_raw"][0]["text"], "My main answer")

        # Second answer appended
        svc.add_text_answer(50, "clarify_1", "Clarification")
        draft = repo.get_review(session.draft_id)
        self.assertEqual(len(draft["answers_raw"]), 2)

    async def test_complete_review_updates_draft_to_completed(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=51, username="completer")
        svc.set_contexts(51, ["life"])
        svc.set_period(51, "old")
        svc.add_text_answer(51, "open", "Answer")
        await svc.generate_review(user_id=51, signature="Test")

        session = svc.sessions[51]
        draft_id = session.draft_id

        review_id, stored = await svc.complete_review(user_id=51, is_public=True)

        # Uses existing draft row, no new row created
        self.assertEqual(review_id, draft_id)
        self.assertEqual(stored["status"], "completed")
        self.assertTrue(stored["is_public"])
        # Only 2 rows total: one draft from start_session(50) would be separate,
        # but here only 1 row in this repo instance
        self.assertEqual(len(repo.rows), 1)

    async def test_abandoned_session_includes_partial_data(self) -> None:
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()
        owner_texts: list[str] = []

        async def capture_text(text: str) -> bool:
            owner_texts.append(text)
            return True

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
            notify_owner_text=capture_text,
        )
        svc.start_session(user_id=52, username="abandoner")
        svc.set_contexts(52, ["work"])
        svc.add_text_answer(52, "open", "Partial answer here")

        # Force session to appear old
        svc.sessions[52].started_at -= 3700

        await svc.check_abandoned_sessions(timeout_minutes=60)
        self.assertEqual(len(owner_texts), 1)
        self.assertIn("Partial answer here", owner_texts[0])
        self.assertIn("work", owner_texts[0])


    # --- TDD: draft gap tests ---

    async def test_manual_edit_saves_draft(self) -> None:
        """apply_manual_edit should persist edited review to draft."""
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=60, username="editor")
        svc.set_contexts(60, ["work"])
        svc.set_period(60, "recent")
        svc.add_text_answer(60, "open", "Answer")
        await svc.generate_review(user_id=60, signature="Editor")

        session = svc.sessions[60]
        draft = repo.get_review(session.draft_id)
        self.assertEqual(draft["review_final"], "Draft review")

        # User edits the review
        svc.apply_manual_edit(60, "My custom edited review")

        # Draft in DB should reflect the edit
        draft = repo.get_review(session.draft_id)
        self.assertEqual(draft["review_final"], "My custom edited review")

    async def test_use_raw_answers_saves_draft(self) -> None:
        """use_raw_answers should persist raw text as review_final to draft."""
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=61, username="rawer")
        svc.set_contexts(61, ["life"])
        svc.set_period(61, "old")
        svc.add_text_answer(61, "open", "Raw answer one")
        svc.add_text_answer(61, "clarify_1", "Raw answer two")

        svc.use_raw_answers(61)

        session = svc.sessions[61]
        draft = repo.get_review(session.draft_id)
        self.assertIn("Raw answer one", draft["review_final"])
        self.assertIn("Raw answer two", draft["review_final"])

    async def test_analyze_saves_voice_transcripts_to_draft(self) -> None:
        """After voice transcripts are collected in analyze, draft should update."""
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        llm.analyze_result = {
            "context": False, "moment": False, "style": False,
            "questions": ["Q1", "Q2"],
        }
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=62, username="voicer")
        svc.set_contexts(62, ["work"])
        svc.set_period(62, "recent")
        await svc.add_voice_answer(62, "open", b"voice-bytes")

        # Before analyze, draft has no answers with text (voice pending)
        session = svc.sessions[62]
        draft_before = repo.get_review(session.draft_id)
        self.assertEqual(len(draft_before["answers_raw"]), 0)

        # Analyze collects voice transcripts
        await svc.analyze_and_select_questions(62)

        # Draft should now have the transcribed answer
        draft_after = repo.get_review(session.draft_id)
        self.assertEqual(len(draft_after["answers_raw"]), 1)
        self.assertEqual(draft_after["answers_raw"][0]["source"], "voice_transcript")

    async def test_complete_review_works_without_draft_id(self) -> None:
        """If draft creation failed, complete_review should still save via save_review."""
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=63, username="nondraft")
        svc.set_contexts(63, ["study"])
        svc.set_period(63, "recent")
        svc.add_text_answer(63, "open", "Answer")
        await svc.generate_review(user_id=63, signature="Fallback")

        # Simulate draft creation failure by clearing draft_id
        session = svc.sessions[63]
        session.draft_id = None

        # complete_review should still work via save_review fallback
        review_id, stored = await svc.complete_review(user_id=63, is_public=False)
        self.assertIsNotNone(review_id)
        self.assertFalse(stored["is_public"])
        self.assertEqual(stored["signature"], "Fallback")

    async def test_restart_session_creates_new_draft(self) -> None:
        """Starting a new session for same user creates new draft; old draft stays."""
        voice = FakeVoicePipeline()
        llm = FakeLLMClient()
        repo = FakeRepo(rows={})
        notifier = FakeNotifier()

        svc = FeedbackService(
            content=self._content(), voice_pipeline=voice,
            llm_client=llm, repository=repo, notify_owner=notifier,
        )
        svc.start_session(user_id=64, username="restarter")
        first_draft_id = svc.sessions[64].draft_id
        svc.set_contexts(64, ["work"])
        svc.add_text_answer(64, "open", "First attempt")

        # User restarts
        svc.start_session(user_id=64, username="restarter")
        second_draft_id = svc.sessions[64].draft_id

        # Two separate drafts
        self.assertNotEqual(first_draft_id, second_draft_id)
        self.assertEqual(len(repo.rows), 2)

        # Old draft retains its data
        old_draft = repo.get_review(first_draft_id)
        self.assertEqual(old_draft["context"], ["work"])
        self.assertEqual(len(old_draft["answers_raw"]), 1)

        # New draft is empty
        new_draft = repo.get_review(second_draft_id)
        self.assertEqual(new_draft["context"], [])


if __name__ == "__main__":
    unittest.main()
