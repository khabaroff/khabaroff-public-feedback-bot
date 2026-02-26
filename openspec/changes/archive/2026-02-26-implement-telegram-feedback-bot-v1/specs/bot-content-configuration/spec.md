## ADDED Requirements

### Requirement: Externalized Bot Texts
The system SHALL load all user-facing bot texts from `content/texts.yaml` and SHALL NOT hardcode conversational copy in handler logic.

#### Scenario: Greeting text sourced from config
- **WHEN** the bot sends the welcome message
- **THEN** the message content is resolved from `content/texts.yaml` key-value data

### Requirement: Externalized Thinking Phrases
The system SHALL load thinking indicator phrases from `content/thinking.yaml` as a list used for random selection at generation time.

#### Scenario: Thinking phrase pool loaded
- **WHEN** application startup completes
- **THEN** the runtime config contains at least one thinking phrase from `content/thinking.yaml`

### Requirement: Prompt Files As Runtime Dependencies
The system SHALL load `prompts/generate_review.md` and `prompts/rephrase_review.md` from disk at runtime for LLM calls.

#### Scenario: Prompt resolved for generation
- **WHEN** first draft review generation is requested
- **THEN** the system uses the current file content of `prompts/generate_review.md` in request construction

### Requirement: Startup Configuration Validation
The system SHALL validate presence and parseability of required YAML/Markdown config files during startup and SHALL fail fast when mandatory keys are missing.

#### Scenario: Missing mandatory text key
- **WHEN** startup loads `content/texts.yaml` and required key is absent
- **THEN** startup exits with explicit configuration error instead of running partially configured bot
