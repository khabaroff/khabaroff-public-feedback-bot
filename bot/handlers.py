from __future__ import annotations

import asyncio
from typing import Any

from bot.config import AppContent
from bot.fsm import FeedbackStatesGroup
from bot.service import FeedbackService, SessionNotFoundError
from bot.voice import download_telegram_voice_bytes

_SESSION_LOST_MSG = "Сессия потерялась (бот перезапускался). Нажми /start чтобы начать заново."

_CONTEXT_KEYS = ["study", "work", "life", "other"]
_PERIOD_KEYS = ["recent", "medium", "old", "unknown"]


def register_handlers(
    dispatcher: Any,
    service: FeedbackService,
    content: AppContent,
    video_note_path: str = "",
) -> None:
    try:
        from aiogram import F, Router
        from aiogram.filters import CommandStart
        from aiogram.fsm.context import FSMContext
        from aiogram.enums import ChatAction
        from aiogram.types import CallbackQuery, FSInputFile, Message
        from aiogram.utils.keyboard import InlineKeyboardBuilder
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("aiogram is required to register Telegram handlers") from exc

    if FeedbackStatesGroup is None:
        raise RuntimeError("FeedbackStatesGroup unavailable; aiogram state classes missing")

    router = Router(name="feedback-flow")
    T = content.texts

    def _start_keyboard() -> Any:
        builder = InlineKeyboardBuilder()
        builder.button(text=T["cta_start"], callback_data="flow:start")
        return builder.as_markup()

    def _context_keyboard(selected: set[str]) -> Any:
        builder = InlineKeyboardBuilder()
        for key in _CONTEXT_KEYS:
            label = T.get(f"context_{key}", key)
            marker = "✅ " if key in selected else ""
            builder.button(text=f"{marker}{label}", callback_data=f"context:toggle:{key}")
        builder.button(text=T.get("context_confirm", "✅ Готово"), callback_data="context:done")
        builder.adjust(1)
        return builder.as_markup()

    def _period_keyboard() -> Any:
        builder = InlineKeyboardBuilder()
        for key in _PERIOD_KEYS:
            label = T.get(f"period_{key}", key)
            builder.button(text=label, callback_data=f"period:{key}")
        builder.adjust(1)
        return builder.as_markup()

    def _review_keyboard() -> Any:
        builder = InlineKeyboardBuilder()
        builder.button(text=T["review_ok_button"], callback_data="review:accept")
        builder.button(text=T["review_edit_button"], callback_data="review:edit")
        builder.button(text=T["review_raw_button"], callback_data="review:raw")
        builder.adjust(1)
        return builder.as_markup()

    def _publish_keyboard() -> Any:
        builder = InlineKeyboardBuilder()
        builder.button(text=T["publish_yes_button"], callback_data="publish:yes")
        builder.button(text=T["publish_no_button"], callback_data="publish:no")
        builder.adjust(1)
        return builder.as_markup()

    async def _capture_answer(
        message: Message,
        state: FSMContext,
        answer_key: str,
    ) -> bool:
        user_id = message.from_user.id
        if message.voice is not None:
            try:
                voice_bytes = await download_telegram_voice_bytes(message.bot, message.voice)
                ack = await service.add_voice_answer(user_id, answer_key, voice_bytes)
                await message.answer(ack)
                return True
            except Exception:
                await message.answer(
                    "Не получилось обработать голосовое. Пришли ответ текстом, пожалуйста."
                )
                return False

        text = (message.text or "").strip()
        if not text:
            await message.answer("Нужен текст или голосовое сообщение.")
            return False
        service.add_text_answer(user_id, answer_key, text)
        return True

    @router.message(CommandStart())
    async def on_start(message: Message, state: FSMContext) -> None:
        user = message.from_user
        service.start_session(user_id=user.id, username=user.username)

        await message.answer(T["greeting_intro"])
        await asyncio.sleep(1)
        if video_note_path:
            try:
                await message.answer_video_note(FSInputFile(video_note_path))
            except Exception:
                pass

        followup = "\n\n".join([T["greeting_followup"], T["voice_hint"]])
        await message.answer(followup, reply_markup=_start_keyboard())
        await state.set_state(FeedbackStatesGroup.start)

    @router.callback_query(F.data == "flow:start")
    async def on_flow_start(callback: CallbackQuery, state: FSMContext) -> None:
        await state.update_data(contexts_selected=[])
        await state.set_state(FeedbackStatesGroup.context_select)
        await callback.message.answer(
            T["context_prompt"],
            reply_markup=_context_keyboard(set()),
        )
        await callback.answer()
        await service.notify_session_started(callback.from_user.id)

    @router.callback_query(F.data.startswith("context:toggle:"))
    async def on_context_toggle(callback: CallbackQuery, state: FSMContext) -> None:
        context = callback.data.split(":", 2)[2]
        data = await state.get_data()
        selected = set(data.get("contexts_selected", []))
        if context in selected:
            selected.remove(context)
        else:
            selected.add(context)
        await state.update_data(contexts_selected=sorted(selected))
        await callback.message.edit_reply_markup(reply_markup=_context_keyboard(selected))
        await callback.answer()

    @router.callback_query(F.data == "context:done")
    async def on_context_done(callback: CallbackQuery, state: FSMContext) -> None:
        data = await state.get_data()
        selected = data.get("contexts_selected", [])
        if not selected:
            await callback.answer("Сначала выбери хотя бы один контекст", show_alert=True)
            return

        service.set_contexts(callback.from_user.id, selected)
        await state.set_state(FeedbackStatesGroup.period_select)
        await callback.message.answer(T["period_prompt"], reply_markup=_period_keyboard())
        await callback.answer()

    @router.callback_query(F.data.startswith("period:"))
    async def on_period_selected(callback: CallbackQuery, state: FSMContext) -> None:
        period_key = callback.data.split(":", 1)[1]
        service.set_period(callback.from_user.id, period_key)
        await state.set_state(FeedbackStatesGroup.open_question)
        await callback.message.answer(T["open_question"])
        await callback.answer()

    @router.message(FeedbackStatesGroup.open_question)
    async def on_open_answer(message: Message, state: FSMContext) -> None:
        captured = await _capture_answer(message, state, "open")
        if not captured:
            return

        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)
        try:
            questions = await service.analyze_and_select_questions(message.from_user.id)
        except SessionNotFoundError:
            await message.answer(_SESSION_LOST_MSG)
            await state.clear()
            return

        await state.update_data(clarifying_questions=questions)
        await state.set_state(FeedbackStatesGroup.clarifying_q1)
        await message.answer(T["clarify_intro"])
        await message.answer(questions[0])

    @router.message(FeedbackStatesGroup.clarifying_q1)
    async def on_clarifying_1(message: Message, state: FSMContext) -> None:
        captured = await _capture_answer(message, state, "clarify_1")
        if not captured:
            return

        data = await state.get_data()
        questions = data.get("clarifying_questions", [])
        if len(questions) > 1:
            await state.set_state(FeedbackStatesGroup.clarifying_q2)
            await message.answer("Спасибо! И еще один вопрос:")
            await message.answer(questions[1])
            return

        await state.set_state(FeedbackStatesGroup.signature)
        await message.answer(T["signature_prompt"])
        await message.answer(T["signature_hint"])

    @router.message(FeedbackStatesGroup.clarifying_q2)
    async def on_clarifying_2(message: Message, state: FSMContext) -> None:
        captured = await _capture_answer(message, state, "clarify_2")
        if not captured:
            return

        await state.set_state(FeedbackStatesGroup.signature)
        await message.answer(T["signature_prompt"])
        await message.answer(T["signature_hint"])

    @router.message(FeedbackStatesGroup.signature)
    async def on_signature(message: Message, state: FSMContext) -> None:
        signature = (message.text or "").strip()
        if not signature:
            await message.answer("Нужна подпись текстом.")
            return

        await state.set_state(FeedbackStatesGroup.generating)
        import random
        await message.answer(random.choice(content.thinking_phrases))
        await message.bot.send_chat_action(message.chat.id, ChatAction.TYPING)

        try:
            _thinking, review = await service.generate_review(message.from_user.id, signature)
        except SessionNotFoundError:
            await message.answer(_SESSION_LOST_MSG)
            await state.clear()
            return
        except Exception as exc:
            await state.set_state(FeedbackStatesGroup.signature)
            await message.answer(f"Не удалось сгенерировать отзыв: {exc}")
            return

        await message.answer(
            f"{T['review_ready']}\n\n{review}\n\n— {signature}",
            reply_markup=_review_keyboard(),
        )
        await state.set_state(FeedbackStatesGroup.review_confirm)

    @router.callback_query(F.data == "review:edit")
    async def on_review_edit(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(FeedbackStatesGroup.review_edit)
        await callback.message.answer(T["review_edit_prompt"])
        await callback.answer()

    @router.message(FeedbackStatesGroup.review_edit)
    async def on_review_edit_text(message: Message, state: FSMContext) -> None:
        text = (message.text or "").strip()
        if not text:
            await message.answer("Нужен текст правки.")
            return
        updated = service.apply_manual_edit(message.from_user.id, text)
        await message.answer(
            f"{T['review_edit_confirm']}\n\n{updated}",
            reply_markup=_review_keyboard(),
        )
        await state.set_state(FeedbackStatesGroup.review_confirm)

    @router.callback_query(F.data == "review:accept")
    async def on_review_accept(callback: CallbackQuery, state: FSMContext) -> None:
        await state.set_state(FeedbackStatesGroup.public_permission)
        await callback.message.answer(
            T["publish_prompt"],
            reply_markup=_publish_keyboard(),
        )
        await callback.answer()

    @router.callback_query(F.data == "review:raw")
    async def on_review_raw(callback: CallbackQuery, state: FSMContext) -> None:
        try:
            service.use_raw_answers(callback.from_user.id)
            await service.complete_review(callback.from_user.id, is_public=False)
        except SessionNotFoundError:
            await callback.message.answer(_SESSION_LOST_MSG)
            await state.clear()
            await callback.answer()
            return
        except Exception as exc:
            await callback.message.answer(f"Ошибка завершения отзыва: {exc}")
            await callback.answer()
            return

        await callback.message.answer(T["final_raw"])
        await state.clear()
        await callback.answer()

    @router.callback_query(F.data.startswith("publish:"))
    async def on_publish_permission(callback: CallbackQuery, state: FSMContext) -> None:
        is_public = callback.data.endswith("yes")
        try:
            await service.complete_review(callback.from_user.id, is_public=is_public)
        except SessionNotFoundError:
            await callback.message.answer(_SESSION_LOST_MSG)
            await state.clear()
            await callback.answer()
            return
        except Exception as exc:
            await callback.message.answer(f"Ошибка завершения отзыва: {exc}")
            await callback.answer()
            return

        final_text = T["final_public"] if is_public else T["final_private"]
        await callback.message.answer(final_text)
        await state.clear()
        await callback.answer()

    dispatcher.include_router(router)
