# review-generation-and-editing Specification

## Purpose
TBD - created by archiving change implement-telegram-feedback-bot-v1. Update Purpose after archive.
## Requirements
### Requirement: Review Generation Payload Assembly
The system SHALL build a generation payload containing selected context, period, all text answers, all available voice transcripts, and signature metadata.

#### Scenario: Payload contains all answer sources
- **WHEN** generation begins after signature capture
- **THEN** the request payload includes both direct text answers and finalized transcript text for each voice answer

### Requirement: Prompt-Driven LLM Generation
The system SHALL use `prompts/generate_review.md` as the system prompt for first-pass review generation.

#### Scenario: Initial generation call
- **WHEN** no draft review exists for a session
- **THEN** the system sends Azure OpenAI request with `generate_review.md` prompt and user answer payload

### Requirement: Thinking Indicator Messaging
The system SHALL send one random "thinking" phrase sourced from `content/thinking.yaml` before review output is returned.

#### Scenario: Thinking phrase displayed
- **WHEN** the flow enters `GENERATING`
- **THEN** one configured thinking phrase is sent and remains visible before final generated text message

### Requirement: Editable Draft Confirmation Loop
The system SHALL present generated draft with approve/edit options and SHALL support unlimited edit iterations until approval.

#### Scenario: Multiple edit iterations
- **WHEN** the user repeatedly submits revised draft text
- **THEN** each revision replaces prior `review_final` candidate and the system re-renders the same approve/edit actions

### Requirement: Review Output Constraints
The system MUST enforce prompt constraints for human-readable review output: conversational tone, concrete details, and gender-neutral wording.

#### Scenario: Output validation before display
- **WHEN** generated text is received from Azure OpenAI
- **THEN** the system checks for prohibited artifacts (bot/form mentions and gendered author forms) before sending text to user

