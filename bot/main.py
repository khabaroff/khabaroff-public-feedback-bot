from __future__ import annotations

import asyncio
import os
from pathlib import Path

from bot.config import ConfigError, ContentError, load_content, load_settings
from bot.db import ReviewRepository
from bot.handlers import register_handlers
from bot.llm import AzureOpenAIClient, FallbackLLMClient, OpenRouterClient
from bot.notification import send_owner_notification
from bot.service import FeedbackService
from bot.voice import AssemblyAIClient, VoicePipeline


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


async def _bootstrap() -> None:
    settings = load_settings()
    content = load_content(Path.cwd())

    repository = ReviewRepository(settings.db_path)
    repository.init_schema()

    llm_client = AzureOpenAIClient(
        endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        deployment=settings.azure_openai_deployment or settings.azure_openai_model,
        api_version=settings.azure_openai_api_version,
    )
    if settings.openrouter_api_key and settings.openrouter_model:
        llm_client = FallbackLLMClient(
            primary=llm_client,
            fallback=OpenRouterClient(
                base_url=settings.openrouter_base_url,
                api_key=settings.openrouter_api_key,
                model=settings.openrouter_model,
            ),
        )
    voice_pipeline = VoicePipeline(
        client=AssemblyAIClient(api_key=settings.assemblyai_api_key),
        poll_interval=1.5,
    )

    should_run_bot = _is_truthy(os.environ.get("RUN_BOT", "0"))
    if not should_run_bot:
        print(
            "Configuration loaded:",
            {
                "owner_telegram_id": settings.owner_telegram_id,
                "thinking_phrases": len(content.thinking_phrases),
                "run_bot": False,
            },
        )
        return

    try:
        from aiogram import Bot, Dispatcher
    except Exception as exc:  # pragma: no cover - runtime dependency
        raise RuntimeError("aiogram is required when RUN_BOT=1") from exc

    bot = Bot(token=settings.telegram_bot_token)

    async def _notify_owner(review: dict) -> bool:
        return await send_owner_notification(bot, settings.owner_telegram_id, review)

    service = FeedbackService(
        content=content,
        voice_pipeline=voice_pipeline,
        llm_client=llm_client,
        repository=repository,
        notify_owner=_notify_owner,
    )

    dispatcher = Dispatcher()
    register_handlers(
        dispatcher=dispatcher,
        service=service,
        content=content,
        video_note_path=settings.video_note_path,
    )

    await dispatcher.start_polling(bot)


def main() -> None:
    try:
        asyncio.run(_bootstrap())
    except (ConfigError, ContentError) as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
