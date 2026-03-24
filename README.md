Telegram-бот для сбора отзывов. Человек рассказывает свободным текстом или голосом — бот анализирует ответ, задает только нужные уточняющие вопросы и генерирует готовый отзыв через LLM.

Разработано для https://khabaroff.com/testimonials/

## Настроить под себя

Бот готов к работе из коробки — нужно только заменить тексты и промпты под своё имя и контекст. Код трогать не нужно.

| Что заменить | Файл | Что там |
|---|---|---|
| Тексты бота | `content/texts.yaml` | Приветствие, кнопки, финальные сообщения |
| Уточняющие вопросы | `content/clarify_questions.yaml` | Банк вопросов по категориям (moment / style / context) |
| Шаблон отзыва | `content/review_template.yaml` | Структура и описание блоков итогового отзыва |
| Промпт генерации | `prompts/generate_review.md` | Кто ты, чем занимаешься, как писать отзыв |
| Промпт анализа | `prompts/analyze_answer.md` | Как оценивать ответ и какие вопросы задавать |
| Промпт редактирования | `prompts/rephrase_review.md` | Как переформулировать отзыв по правкам пользователя |

## Используемые API

| Сервис | Зачем | Обязательный | Бесплатный тариф |
|---|---|---|---|
| [Telegram Bot API](https://core.telegram.org/bots/api) | Бот, сообщения, кнопки | да | да |
| LLM-провайдер | Генерация и анализ отзывов | да | зависит от провайдера |
| LLM-провайдер (fallback) | Резервный LLM, если основной недоступен | нет | зависит от провайдера |
| [AssemblyAI](https://www.assemblyai.com/) | Транскрипция голосовых сообщений | да, если нужен голос | есть бесплатный лимит |

**LLM:** по умолчанию основной — Azure OpenAI (GPT-4o), fallback — [OpenRouter](https://openrouter.ai/). Через OpenRouter можно подключить любую модель — OpenAI, Anthropic Claude, Google Gemini и др. Настраивается через переменные окружения, код менять не нужно.

## Как работает

1. `/start` — приветствие, выбор контекста (учеба / работа / жизнь) и периода
2. Открытый вопрос — текст или голосовое сообщение
3. LLM-анализ ответа (`analyze_answer`) — определяет, чего не хватает (момент / стиль / контекст)
4. 0–2 уточняющих вопроса из банка `clarify_questions.yaml` (приоритет: moment > style > context)
5. Подпись — имя и должность
6. Генерация отзыва через Azure OpenAI (с fallback на OpenRouter)
7. Редактирование и публикация

## Стек

- Python 3.11+, aiogram 3.x
- SQLite — хранение отзывов (файл, без внешней БД)

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

## Локальный запуск

```bash
python -m pip install -e ".[dev]"
python -m bot.main
```

## Тесты

```bash
python -m pytest tests/ -v
```

## Деплой через Docker (рекомендуется)

```bash
git clone https://github.com/khabaroff/khabaroff-public-feedback-bot.git
cd khabaroff-public-feedback-bot
cp .env.example .env
nano .env  # заполнить переменные

docker compose up -d --build
```

Управление:

```bash
docker compose logs -f         # логи в реальном времени
docker compose restart bot     # перезапуск
docker compose down            # остановка
docker compose up -d --build   # обновление после git pull
```

`restart: unless-stopped` в docker-compose.yml обеспечивает автоперезапуск при падении и при перезагрузке сервера.

---

## Деплой на сервер без Docker (Ubuntu/Debian)

### 1. Подготовка сервера

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv git
```

### 2. Клонирование и установка

```bash
cd /opt
sudo git clone https://github.com/khabaroff/khabaroff-public-feedback-bot.git feedback-bot
sudo chown -R $USER:$USER /opt/feedback-bot
cd /opt/feedback-bot

python3.11 -m venv .venv
.venv/bin/pip install -e .
```

### 3. Конфигурация

```bash
cp .env.example .env   # или создать вручную
nano .env               # заполнить все переменные
```

Проверка что конфигурация загружается:

```bash
RUN_BOT=0 .venv/bin/python -m bot.main
```

### 4. Systemd-сервис (автозапуск + перезапуск при падении)

```bash
sudo nano /etc/systemd/system/feedback-bot.service
```

Содержимое:

```ini
[Unit]
Description=Feedback Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
Group=ubuntu
WorkingDirectory=/opt/feedback-bot
ExecStart=/opt/feedback-bot/.venv/bin/python -m bot.main
EnvironmentFile=/opt/feedback-bot/.env

# Автоперезапуск при падении
Restart=on-failure
RestartSec=5

# Не перезапускать чаще 5 раз за 60 секунд
StartLimitIntervalSec=60
StartLimitBurst=5

# Логи
StandardOutput=journal
StandardError=journal
SyslogIdentifier=feedback-bot

[Install]
WantedBy=multi-user.target
```

> Замени `User=ubuntu` и `Group=ubuntu` на своего пользователя.

### 5. Запуск сервиса

```bash
sudo systemctl daemon-reload
sudo systemctl enable feedback-bot   # автозапуск при перезагрузке сервера
sudo systemctl start feedback-bot
```

### 6. Управление

```bash
# Статус
sudo systemctl status feedback-bot

# Логи (последние 100 строк)
sudo journalctl -u feedback-bot -n 100

# Логи в реальном времени
sudo journalctl -u feedback-bot -f

# Перезапуск после обновления кода
cd /opt/feedback-bot && git pull && sudo systemctl restart feedback-bot

# Остановка
sudo systemctl stop feedback-bot
```

### 7. Обновление бота

```bash
cd /opt/feedback-bot
git pull origin main
.venv/bin/pip install -e .
sudo systemctl restart feedback-bot
```
