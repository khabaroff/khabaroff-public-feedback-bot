# CLAUDE.md

## Project Overview

Telegram feedback bot for Sergey Khabarov. Collects free-form text/voice answers, analyzes them via LLM, asks dynamic clarifying questions, and generates polished reviews.

## Architecture

- **bot/handlers.py** — aiogram 3.x handlers, all user-facing text from `content.texts` (no hardcoded strings)
- **bot/fsm.py** — FSM states (`FeedbackStatesGroup`) and `select_clarifying_questions()` logic
- **bot/service.py** — `FeedbackService` orchestrates sessions, voice collection, LLM calls
- **bot/llm.py** — `AzureOpenAIClient`, `OpenRouterClient`, `FallbackLLMClient` with `generate_review`, `rephrase_review`, `analyze_answer` methods
- **bot/voice.py** — `AssemblyAIClient` (language: `ru`) + `VoicePipeline`
- **bot/flow.py** — Pure data engine `FeedbackFlowEngine` (no Telegram deps)
- **bot/config.py** — `Settings` (env vars), `AppContent` (texts, prompts, question bank)
- **bot/db.py** — SQLite `ReviewRepository`

## Key Patterns

- All bot texts live in `content/texts.yaml` — handlers access via `content.texts["key"]`
- LLM prompts live in `prompts/*.md` — loaded at startup
- Clarifying questions come from `content/clarify_questions.yaml`, selected dynamically by `analyze_answer` result
- Voice transcription is non-blocking: register -> ack -> collect before generation
- `FallbackLLMClient` wraps primary (Azure) + fallback (OpenRouter)
- `analyze_answer` uses `temperature: 0.1`; on any error returns safe fallback (all fields false)

## Commands

```bash
# Run tests
.venv/bin/python -m pytest tests/ -v

# Check config loads without starting bot
RUN_BOT=0 .venv/bin/python -m bot.main

# Start bot
.venv/bin/python -m bot.main
```

## Testing Conventions

- `unittest.TestCase` for sync tests, `unittest.IsolatedAsyncioTestCase` for async
- Fake/stub dependencies (no real API calls)
- Test files: `tests/test_<module>.py`
- All LLM clients use injectable `post_json` for testing

## File Naming

- Python: `snake_case` files/functions, `PascalCase` classes
- Content: YAML in `content/`, Markdown in `prompts/`
- Tests: `test_<feature>.py`

## Security

- `.env`, `creds.txt`, `reviews.db` are in `.gitignore` — never commit
- `task/` directory is gitignored (working drafts)
