from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bot.db import ReviewRepository
from bot.notification import format_owner_notification


def _review_payload() -> dict:
    return {
        "telegram_user_id": "42",
        "telegram_username": "demo",
        "context": ["study"],
        "period": "2025-2026",
        "answers_raw": [
            {"key": "open", "source": "text", "text": "Ответ"},
            {"key": "clarify_1", "source": "voice_transcript", "text": "Транскрипт"},
        ],
        "review_generated": "Черновик",
        "review_final": "Финал",
        "signature": "Анна, UX",
        "is_public": True,
        "notified": False,
    }


class TestDBAndNotification(unittest.TestCase):
    def test_repository_init_and_save(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "reviews.db"
            repo = ReviewRepository(db_path)
            repo.init_schema()

            row_id = repo.save_review(_review_payload())
            stored = repo.get_review(row_id)

            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored["signature"], "Анна, UX")
            self.assertEqual(stored["answers_raw"][1]["source"], "voice_transcript")

    def test_notified_flag_update(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "reviews.db"
            repo = ReviewRepository(db_path)
            repo.init_schema()

            row_id = repo.save_review(_review_payload())
            repo.mark_notified(row_id, True)
            stored = repo.get_review(row_id)

            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertTrue(stored["notified"])

    def test_owner_notification_format(self) -> None:
        message = format_owner_notification(_review_payload())
        self.assertIn("Новый отзыв", message)
        self.assertIn("ОТВЕТЫ ЧЕЛОВЕКА", message)
        self.assertIn("ИТОГОВЫЙ ОТЗЫВ", message)
        self.assertIn("Финал", message)


if __name__ == "__main__":
    unittest.main()
