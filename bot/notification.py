from __future__ import annotations

from typing import Any, Mapping


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

    return (
        "📝 Новый отзыв\n\n"
        f"👤 От: {signature}\n"
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


async def send_owner_notification(bot: Any, owner_id: int, review: Mapping[str, Any]) -> bool:
    try:
        await bot.send_message(chat_id=owner_id, text=format_owner_notification(review))
        return True
    except Exception:
        return False
