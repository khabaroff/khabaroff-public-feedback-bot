import unittest

from bot.flow import FeedbackFlowEngine
from bot.fsm import select_clarifying_questions

_QUESTION_BANK = {
    "moment": ["moment_q1", "moment_q2"],
    "style": ["style_q1", "style_q2"],
    "context": ["context_q1", "context_q2"],
}


class TestSelectClarifyingQuestions(unittest.TestCase):
    def test_all_false_returns_two_prioritized(self) -> None:
        analysis = {"context": False, "moment": False, "style": False}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertEqual(len(result), 2)
        self.assertIn(result[0], _QUESTION_BANK["moment"])
        self.assertIn(result[1], _QUESTION_BANK["style"])

    def test_moment_and_style_false_returns_two(self) -> None:
        analysis = {"context": True, "moment": False, "style": False}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertEqual(len(result), 2)
        self.assertIn(result[0], _QUESTION_BANK["moment"])
        self.assertIn(result[1], _QUESTION_BANK["style"])

    def test_only_moment_false_fills_from_present(self) -> None:
        analysis = {"context": True, "moment": False, "style": True}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertEqual(len(result), 2)
        self.assertIn(result[0], _QUESTION_BANK["moment"])

    def test_only_context_false_fills_from_present(self) -> None:
        analysis = {"context": False, "moment": True, "style": True}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertEqual(len(result), 2)
        self.assertIn(result[0], _QUESTION_BANK["context"])

    def test_all_true_still_returns_two(self) -> None:
        analysis = {"context": True, "moment": True, "style": True}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertEqual(len(result), 2)

    def test_always_max_two(self) -> None:
        analysis = {"context": False, "moment": False, "style": False}
        result = select_clarifying_questions(analysis, _QUESTION_BANK)
        self.assertLessEqual(len(result), 2)


class TestFlowEngine(unittest.TestCase):
    def test_edit_loop_keeps_latest_final(self) -> None:
        engine = FeedbackFlowEngine(user_id=1)
        engine.set_contexts(["work"])
        engine.set_period("recent")
        engine.add_answer("open", "text", "We did a project")
        engine.add_answer("clarify_1", "text", "Sergey saved the release")
        engine.set_signature("Anna, UX")
        engine.set_generated_review("Draft")

        engine.submit_manual_edit("Final 1")
        engine.submit_manual_edit("Final 2")

        self.assertEqual(engine.review_generated, "Draft")
        self.assertEqual(engine.review_final, "Final 2")

    def test_smoke_text_only_flow(self) -> None:
        engine = FeedbackFlowEngine(user_id=7)
        engine.set_contexts(["study"])
        engine.set_period("2025-2026")
        engine.add_answer("open", "text", "Great presentation")
        engine.add_answer("clarify_1", "text", "Applied at work")
        engine.set_signature("Ilya, developer")

        payload = engine.build_generation_payload()
        self.assertEqual(payload["context"], ["study"])
        self.assertEqual(len(payload["answers"]), 2)

        engine.set_generated_review("Generated text")
        engine.approve_review()
        engine.set_public_permission(True)
        review = engine.to_review_record()

        self.assertTrue(review["is_public"])
        self.assertEqual(review["review_final"], "Generated text")

    def test_smoke_mixed_text_voice_flow(self) -> None:
        engine = FeedbackFlowEngine(user_id=8)
        engine.set_contexts(["work", "life"])
        engine.set_period("old")
        engine.add_answer("open", "voice_transcript", "This is a transcript")
        engine.add_answer("clarify_1", "text", "It was great")
        engine.set_signature("Maxim")

        payload = engine.build_generation_payload()
        self.assertEqual(payload["answers"][0]["source"], "voice_transcript")
        self.assertEqual(payload["answers"][0]["text"], "This is a transcript")


if __name__ == "__main__":
    unittest.main()
