from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from bot.db import ReviewRepository


class TestDBLifecycle(unittest.TestCase):
    def test_update_review_fields(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = ReviewRepository(Path(tmp) / "reviews.db")
            repo.init_schema()
            row_id = repo.save_review(
                {
                    "telegram_user_id": "1",
                    "telegram_username": "",
                    "context": ["study"],
                    "period": "2025",
                    "answers_raw": [],
                    "review_generated": "draft",
                    "review_final": "draft",
                    "signature": "sig",
                    "is_public": False,
                    "notified": False,
                }
            )

            repo.update_review_fields(row_id, review_final="updated", is_public=True)
            row = repo.get_review(row_id)
            assert row is not None
            self.assertEqual(row["review_final"], "updated")
            self.assertTrue(row["is_public"])


    def test_draft_lifecycle(self) -> None:
        with TemporaryDirectory() as tmp:
            repo = ReviewRepository(Path(tmp) / "reviews.db")
            repo.init_schema()

            # Create draft
            draft_id = repo.save_review(
                {
                    "telegram_user_id": "42",
                    "telegram_username": "testuser",
                    "context": [],
                    "period": "",
                    "answers_raw": [],
                    "review_generated": "",
                    "review_final": "",
                    "signature": "",
                    "is_public": False,
                    "notified": False,
                    "status": "draft",
                }
            )

            row = repo.get_review(draft_id)
            assert row is not None
            self.assertEqual(row["status"], "draft")
            self.assertEqual(row["context"], [])

            # Update draft with partial data
            repo.update_review_fields(
                draft_id,
                context=["work", "study"],
                period="recent",
                answers_raw=[{"key": "open", "source": "text", "text": "My answer"}],
            )
            row = repo.get_review(draft_id)
            assert row is not None
            self.assertEqual(row["context"], ["work", "study"])
            self.assertEqual(row["period"], "recent")
            self.assertEqual(len(row["answers_raw"]), 1)
            self.assertEqual(row["status"], "draft")

            # Complete the draft
            repo.update_review_fields(
                draft_id,
                review_final="Final review text",
                signature="Anna",
                is_public=True,
                status="completed",
            )
            row = repo.get_review(draft_id)
            assert row is not None
            self.assertEqual(row["status"], "completed")
            self.assertEqual(row["review_final"], "Final review text")
            self.assertTrue(row["is_public"])

    def test_migration_adds_status_to_existing_db(self) -> None:
        with TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "reviews.db"

            # Create table without status column (old schema)
            import sqlite3
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id TEXT NOT NULL,
                    telegram_username TEXT,
                    context TEXT NOT NULL,
                    period TEXT,
                    answers_raw TEXT NOT NULL,
                    review_generated TEXT,
                    review_final TEXT,
                    signature TEXT,
                    is_public INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    notified INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.execute(
                "INSERT INTO reviews (telegram_user_id, context, answers_raw, created_at) "
                "VALUES ('1', '[]', '[]', '2025-01-01')"
            )
            conn.commit()
            conn.close()

            # init_schema should migrate
            repo = ReviewRepository(db_path)
            repo.init_schema()

            row = repo.get_review(1)
            assert row is not None
            self.assertEqual(row["status"], "completed")


if __name__ == "__main__":
    unittest.main()
