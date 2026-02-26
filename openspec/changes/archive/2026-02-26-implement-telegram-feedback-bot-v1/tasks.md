## 1. Project Bootstrap

- [x] 1.1 Create baseline Python package structure (`bot/`, `content/`, `prompts/`) and entrypoint wiring in `bot/main.py`
- [x] 1.2 Add runtime dependencies for `aiogram 3`, SQLite access, HTTP client for AssemblyAI/Azure, and YAML parsing
- [x] 1.3 Add environment configuration loader for Telegram token, owner Telegram ID, AssemblyAI key, and Azure OpenAI credentials

## 2. Content and Prompt Configuration

- [x] 2.1 Create `content/texts.yaml` with all required conversation messages and button labels from the approved flow
- [x] 2.2 Create `content/thinking.yaml` with randomized thinking phrase pool
- [x] 2.3 Create `prompts/generate_review.md` and `prompts/rephrase_review.md` with generation constraints from `task.md`
- [x] 2.4 Implement startup validation that fails fast on missing/invalid content and prompt keys

## 3. FSM and Dialogue Handlers

- [x] 3.1 Define FSM states for full flow (`START` through `DONE`) in `bot/fsm.py`
- [x] 3.2 Implement greeting sequence with welcome text, Video Note send, and "Поехали" transition
- [x] 3.3 Implement context multi-select with inline buttons and explicit "Готово" confirmation
- [x] 3.4 Implement period selection and transition to open-question step
- [x] 3.5 Implement open answer capture (text + voice) and context-based clarifying question routing (max two)
- [x] 3.6 Implement signature capture, review confirm/edit loop, publication consent step, and dual final messages

## 4. Voice Transcription Pipeline

- [x] 4.1 Implement Telegram voice file download and async upload to AssemblyAI in `bot/voice.py`
- [x] 4.2 Persist transcription job metadata per answer slot in FSM/session state
- [x] 4.3 Implement non-blocking acknowledgement flow ("расшифровываю в фоне — продолжаем")
- [x] 4.4 Implement transcript polling and merge before LLM generation with timeout/failure fallback

## 5. Review Generation and Editing

- [x] 5.1 Implement generation payload assembler that combines context, period, answers, transcripts, and signature metadata
- [x] 5.2 Implement Azure OpenAI client in `bot/llm.py` using external prompt files
- [x] 5.3 Send randomized thinking phrase before generation result output
- [x] 5.4 Implement output safety checks for prohibited phrases and gendered author forms before showing draft
- [x] 5.5 Implement unlimited manual edit loop while preserving `review_generated` and latest `review_final`

## 6. Persistence Layer

- [x] 6.1 Implement SQLite schema initialization for `reviews` table in `bot/db.py`
- [x] 6.2 Implement repository methods to create/update review records across lifecycle stages
- [x] 6.3 Store `answers_raw` as structured JSON with source type (`text`/`voice_transcript`) per answer key
- [x] 6.4 Implement `notified` flag lifecycle and retry-safe update semantics

## 7. Owner Notification

- [x] 7.1 Implement Telegram notification formatter that includes signature, context, period, consent, raw answers, and final review
- [x] 7.2 Send owner notification after consent capture and mark `notified=true` only on successful delivery
- [x] 7.3 Add error handling path that logs notification failures while preserving completed review data

## 8. Verification

- [x] 8.1 Add unit tests for config loading/validation and YAML/prompt key resolution
- [x] 8.2 Add unit tests for FSM branching (single/multi-context, clarifying question cap, edit loop behavior)
- [x] 8.3 Add tests for voice transcription orchestration (job registration, polling success, fallback on failure)
- [x] 8.4 Add tests for persistence mapping and owner notification state transitions
- [x] 8.5 Run end-to-end smoke test of the full Telegram flow (text-only and mixed text+voice paths)
