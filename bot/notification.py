from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def format_owner_notification(review: Mapping[str, Any]) -> str:
    signature = str(review.get("signature", "")).strip() or "Без подписи"
    contexts = review.get("context", [])
    if isinstance(contexts, list):
        context_text = ", ".join(str(item) for item in contexts if str(item).strip())
    else:
        context_text = str(contexts)
    period = str(review.get("period", "")).strip() or "не указан"
    is_public = bool(review.get("is_public", False))
    publication = "✅ разрешена" if is_public else "🔒 приватно"

    answers = review.get("answers_raw", [])
    answer_lines: list[str] = []
    if isinstance(answers, list):
        for idx, item in enumerate(answers, start=1):
            if not isinstance(item, dict):
                continue
            key = str(item.get("key", f"answer_{idx}"))
            text = str(item.get("text", "")).strip()
            answer_lines.append(f"{idx}. {key}: {text}")
    answers_block = "\n".join(answer_lines) if answer_lines else "Нет ответов"

    final_review = str(review.get("review_final", "")).strip()
    if not final_review:
        final_review = str(review.get("review_generated", "")).strip() or "Нет текста"

    tg_user_id = str(review.get("telegram_user_id", "")).strip()
    tg_username = str(review.get("telegram_username", "")).strip()
    tg_line = ""
    if tg_username:
        tg_line = f"💬 Telegram: @{tg_username} (ID: {tg_user_id})\n"
    elif tg_user_id:
        tg_line = f"💬 Telegram ID: {tg_user_id}\n"

    return (
        "📝 Новый отзыв\n\n"
        f"👤 От: {signature}\n"
        f"{tg_line}"
        f"📋 Контекст: {context_text or 'не указан'}\n"
        f"📅 Период: {period}\n"
        f"🌐 Публикация: {publication}\n\n"
        "━━━━━━━━━━━━━━━\n"
        "ОТВЕТЫ ЧЕЛОВЕКА (дословно)\n\n"
        f"{answers_block}\n"
        "━━━━━━━━━━━━━━━\n"
        "ИТОГОВЫЙ ОТЗЫВ\n\n"
        f"{final_review}\n\n"
        f"— {signature}\n"
        "━━━━━━━━━━━━━━━"
    )


def format_session_started(user_id: int, username: str | None) -> str:
    if username:
        who = f"@{username} (ID: {user_id})"
    else:
        who = f"ID: {user_id}"
    return f"👋 Кто-то начал оставлять отзыв\n\n💬 Telegram: {who}"


def format_session_abandoned(user_id: int, username: str | None, minutes: int) -> str:
    if username:
        who = f"@{username} (ID: {user_id})"
    else:
        who = f"ID: {user_id}"
    return (
        f"⏰ Незавершенный отзыв\n\n"
        f"💬 Telegram: {who}\n"
        f"⏱ Прошло {minutes} мин. с начала — отзыв не был завершен."
    )


async def send_owner_notification(bot: Any, owner_id: int, review: Mapping[str, Any]) -> bool:
    try:
        await bot.send_message(chat_id=owner_id, text=format_owner_notification(review))
        return True
    except Exception as exc:
        logger.error("Failed to send owner notification: %s", exc)
        return False


async def send_owner_text(bot: Any, owner_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=owner_id, text=text)
        return True
    except Exception as exc:
        logger.error("Failed to send owner message: %s", exc)
        return False
