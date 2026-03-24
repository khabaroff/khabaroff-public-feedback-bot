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


def format_session_abandoned(
    user_id: int,
    username: str | None,
    minutes: int,
    partial_data: Mapping[str, Any] | None = None,
) -> str:
    if username:
        who = f"@{username} (ID: {user_id})"
    else:
        who = f"ID: {user_id}"
    text = (
        f"⏰ Незавершенный отзыв\n\n"
        f"💬 Telegram: {who}\n"
        f"⏱ Прошло {minutes} мин. с начала — отзыв не был завершен."
    )
    if partial_data:
        contexts = partial_data.get("context", [])
        if isinstance(contexts, list) and contexts:
            text += f"\n📋 Контекст: {', '.join(str(c) for c in contexts)}"
        period = str(partial_data.get("period", "")).strip()
        if period:
            text += f"\n📅 Период: {period}"
        answers = partial_data.get("answers_raw", [])
        if isinstance(answers, list) and answers:
            lines = []
            for idx, item in enumerate(answers, start=1):
                if not isinstance(item, dict):
                    continue
                key = str(item.get("key", f"answer_{idx}"))
                answer_text = str(item.get("text", "")).strip()
                if answer_text:
                    lines.append(f"  {idx}. {key}: {answer_text}")
            if lines:
                text += "\n\n📝 Собранные ответы:\n" + "\n".join(lines)
    return text


_TG_MSG_LIMIT = 4096


async def send_owner_notification(bot: Any, owner_id: int, review: Mapping[str, Any]) -> bool:
    try:
        text = format_owner_notification(review)
        if len(text) <= _TG_MSG_LIMIT:
            await bot.send_message(chat_id=owner_id, text=text)
        else:
            # Split into chunks respecting the limit
            for chunk in _split_message(text, _TG_MSG_LIMIT):
                await bot.send_message(chat_id=owner_id, text=chunk)
        return True
    except Exception as exc:
        logger.error("Failed to send owner notification: %s", exc, exc_info=True)
        return False


def _split_message(text: str, limit: int) -> list[str]:
    """Split a long message into chunks, breaking at newlines when possible."""
    chunks: list[str] = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        # Find a newline near the limit to break at
        cut = text.rfind("\n", 0, limit)
        if cut <= 0:
            cut = limit
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


async def send_owner_text(bot: Any, owner_id: int, text: str) -> bool:
    try:
        await bot.send_message(chat_id=owner_id, text=text)
        return True
    except Exception as exc:
        logger.error("Failed to send owner message: %s", exc)
        return False
