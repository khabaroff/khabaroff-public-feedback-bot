# feedback-dialog-flow Specification

## Purpose
TBD - created by archiving change implement-telegram-feedback-bot-v1. Update Purpose after archive.
## Requirements
### Requirement: Guided Feedback Conversation
The system SHALL guide each user through a deterministic feedback flow with the ordered states `START`, `CONTEXT_SELECT`, `PERIOD_SELECT`, `OPEN_QUESTION`, `CLARIFYING_Q1`, `CLARIFYING_Q2` (optional), `SIGNATURE`, `GENERATING`, `REVIEW_CONFIRM`, `REVIEW_EDIT` (loop), `PUBLIC_PERMISSION`, and `DONE`.

#### Scenario: Start command initializes flow
- **WHEN** a user starts the bot from `t.me/sk_fdbck_bot` and presses the start button
- **THEN** the bot enters `CONTEXT_SELECT` and presents the first context-selection prompt

### Requirement: Greeting With Personal Intro
The system SHALL send a greeting text and a Video Note greeting before asking the user to begin the questionnaire.

#### Scenario: Greeting package is delivered
- **WHEN** a new feedback session is created
- **THEN** the bot sends greeting text, sends the configured Video Note, and shows the "Поехали" inline button

### Requirement: Multi-Select Context Capture
The system SHALL allow users to select one or more context options and continue only after explicit confirmation via "Готово".

#### Scenario: User selects multiple contexts
- **WHEN** the user selects two or more context options and presses "Готово"
- **THEN** the bot stores all selected contexts and transitions to `PERIOD_SELECT`

### Requirement: Period Selection
The system SHALL collect one period option from predefined choices before proceeding to open feedback.

#### Scenario: Period is chosen
- **WHEN** the user taps one period option
- **THEN** the selected period is stored and the bot asks the open question in `OPEN_QUESTION`

### Requirement: Context-Driven Clarifying Questions
The system SHALL ask one or two clarifying questions based on selected context categories and SHALL NOT ask more than two total clarifying questions.

#### Scenario: Mixed contexts produce capped clarifications
- **WHEN** the user selected multiple context categories
- **THEN** the bot asks at most two clarifying questions mapped from those categories and proceeds to `SIGNATURE`

### Requirement: Signature Collection
The system SHALL collect a free-form signature string for final review attribution.

#### Scenario: Signature is captured
- **WHEN** the user submits signature text
- **THEN** the signature is stored and the flow moves to `GENERATING`

### Requirement: Review Approval Loop
The system SHALL present generated review text with approval and edit actions and SHALL keep looping until explicit approval is received.

#### Scenario: User requests edit
- **WHEN** the user taps "Хочу подправить текст"
- **THEN** the bot asks for edited text, stores new version, and returns to the same approval buttons

### Requirement: Publication Permission and Tailored Finales
The system SHALL ask for publication consent after review approval and SHALL show different completion messages for public and private consent outcomes.

#### Scenario: Private-only consent
- **WHEN** the user selects private-only option
- **THEN** the system stores `is_public=false` and sends the private completion message

### Requirement: Gender-Neutral Language Policy
The system MUST use gender-neutral wording in all bot texts and generated feedback shown to users.

#### Scenario: Bot text validation
- **WHEN** the bot renders any user-facing template in the flow
- **THEN** the rendered message contains no gender-marked author forms

