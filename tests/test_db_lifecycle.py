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


if __name__ == "__main__":
    unittest.main()
