from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ReviewRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS reviews (
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
                    notified INTEGER NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'completed'
                )
                """
            )
            self._migrate_add_status_column(conn)

    def _migrate_add_status_column(self, conn: sqlite3.Connection) -> None:
        cursor = conn.execute("PRAGMA table_info(reviews)")
        columns = {row[1] for row in cursor.fetchall()}
        if "status" not in columns:
            conn.execute(
                "ALTER TABLE reviews ADD COLUMN status TEXT NOT NULL DEFAULT 'completed'"
            )

    def save_review(self, payload: dict[str, Any]) -> int:
        created_at = payload.get("created_at")
        if not created_at:
            created_at = datetime.now(timezone.utc).isoformat()

        status = payload.get("status", "completed")

        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO reviews (
                    telegram_user_id,
                    telegram_username,
                    context,
                    period,
                    answers_raw,
                    review_generated,
                    review_final,
                    signature,
                    is_public,
                    created_at,
                    notified,
                    status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(payload.get("telegram_user_id", "")),
                    str(payload.get("telegram_username", "")),
                    json.dumps(payload.get("context", []), ensure_ascii=False),
                    str(payload.get("period", "")),
                    json.dumps(payload.get("answers_raw", []), ensure_ascii=False),
                    str(payload.get("review_generated", "")),
                    str(payload.get("review_final", "")),
                    str(payload.get("signature", "")),
                    int(bool(payload.get("is_public", False))),
                    str(created_at),
                    int(bool(payload.get("notified", False))),
                    str(status),
                ),
            )
            return int(cursor.lastrowid)

    def get_review(self, review_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_dict(row)

    def mark_notified(self, review_id: int, notified: bool) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE reviews SET notified = ? WHERE id = ?",
                (int(bool(notified)), review_id),
            )

    def update_review_fields(self, review_id: int, **fields: Any) -> None:
        allowed = {
            "context",
            "period",
            "answers_raw",
            "review_generated",
            "review_final",
            "signature",
            "is_public",
            "notified",
            "telegram_username",
            "status",
        }
        updates: list[str] = []
        values: list[Any] = []

        for key, value in fields.items():
            if key not in allowed:
                continue
            if key in {"context", "answers_raw"}:
                value = json.dumps(value, ensure_ascii=False)
            if key in {"is_public", "notified"}:
                value = int(bool(value))
            updates.append(f"{key} = ?")
            values.append(value)

        if not updates:
            return

        values.append(review_id)
        query = f"UPDATE reviews SET {', '.join(updates)} WHERE id = ?"
        with self._connect() as conn:
            conn.execute(query, values)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _row_to_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        raw = dict(row)
        raw["context"] = json.loads(raw["context"]) if raw.get("context") else []
        raw["answers_raw"] = (
            json.loads(raw["answers_raw"]) if raw.get("answers_raw") else []
        )
        raw["is_public"] = bool(raw.get("is_public"))
        raw["notified"] = bool(raw.get("notified"))
        raw.setdefault("status", "completed")
        return raw
