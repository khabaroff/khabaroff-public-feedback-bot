# khabaroff-public-feedback-bot

Telegram-бот для сбора отзывов о Сергее Хабарове. Человек рассказывает свободным текстом или голосом — бот анализирует ответ, задаёт только нужные уточняющие вопросы и генерирует готовый отзыв через LLM.

## Как работает

1. `/start` — приветствие, выбор контекста (учёба / работа / жизнь) и периода
2. Открытый вопрос — текст или голосовое сообщение
3. LLM-анализ ответа (`analyze_answer`) — определяет, чего не хватает (момент / стиль / контекст)
4. 0–2 уточняющих вопроса из банка `clarify_questions.yaml` (приоритет: moment > style > context)
5. Подпись — имя и должность
6. Генерация отзыва через Azure OpenAI (с fallback на OpenRouter)
7. Редактирование и публикация

## Стек

- Python 3.11+, aiogram 3.x
- Azure OpenAI (GPT-4o) — генерация и анализ
- OpenRouter — fallback LLM
- AssemblyAI — транскрипция голосовых (русский язык)
- SQLite — хранение отзывов

## Структура проекта

```
bot/            # Основной код бота
  config.py     # Загрузка настроек и контента
  handlers.py   # Telegram-хэндлеры (aiogram)
  fsm.py        # FSM-состояния и выбор уточняющих вопросов
  service.py    # Оркестрация бизнес-логики
  llm.py        # Клиенты Azure OpenAI / OpenRouter
  voice.py      # AssemblyAI транскрипция
  flow.py       # Движок данных сессии (без Telegram-зависимостей)
  db.py         # SQLite-репозиторий
  notification.py # Уведомление владельца
  main.py       # Точка входа
content/        # YAML-конфигурация текстов
  texts.yaml    # Все тексты бота
  thinking.yaml # Фразы-заглушки на время генерации
  clarify_questions.yaml # Банк уточняющих вопросов
  review_template.yaml   # Шаблон полей отзыва
prompts/        # Системные промпты для LLM
  analyze_answer.md    # Анализ открытого ответа
  generate_review.md   # Генерация отзыва
  rephrase_review.md   # Редактирование отзыва
tests/          # Юнит-тесты (pytest)
openspec/       # Спецификации и change proposals
```

## Настройка

Переменные окружения (или `.env` файл):

| Переменная | Описание |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Токен Telegram-бота |
| `OWNER_TELEGRAM_ID` | ID владельца для уведомлений |
| `ASSEMBLYAI_API_KEY` | Ключ AssemblyAI |
| `AZURE_OPENAI_API_KEY` | Ключ Azure OpenAI |
| `AZURE_OPENAI_ENDPOINT` | Эндпоинт Azure OpenAI |
| `AZURE_OPENAI_MODEL` | Модель (например `gpt-4o`) |
| `OPENROUTER_API_KEY` | (опц.) Ключ OpenRouter для fallback |
| `OPENROUTER_MODEL` | (опц.) Модель OpenRouter |

## Запуск

```bash
python -m pip install -e ".[dev]"
python -m bot.main
```

## Тесты

```bash
python -m pytest tests/ -v
```
