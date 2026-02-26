# voice-transcription-pipeline Specification

## Purpose
TBD - created by archiving change implement-telegram-feedback-bot-v1. Update Purpose after archive.
## Requirements
### Requirement: Voice Input Acceptance
The system SHALL accept Telegram voice messages (`.ogg`/opus) on open-answer and clarifying-answer steps.

#### Scenario: Voice message on open question
- **WHEN** the user sends a voice message while in `OPEN_QUESTION`
- **THEN** the system stores a pending voice answer entry and continues the flow

### Requirement: Immediate Non-Blocking Acknowledgement
The system SHALL acknowledge voice receipt immediately and continue conversation without waiting for transcript completion.

#### Scenario: Acknowledgement is instant
- **WHEN** a voice message is received
- **THEN** the bot replies with receipt confirmation and asks the next expected question in the same interaction

### Requirement: AssemblyAI Async Job Lifecycle
The system SHALL upload voice payloads to AssemblyAI with `language_detection=true`, create transcription jobs, and persist job identifiers linked to answer slots.

#### Scenario: Job is registered
- **WHEN** a voice message is submitted for transcription
- **THEN** the system stores the created transcription job ID and answer key mapping in session state

### Requirement: Transcript Synchronization Before Generation
The system SHALL poll pending transcription jobs before calling review generation and SHALL merge finished transcripts into answer payload.

#### Scenario: Pending transcripts resolved at generation step
- **WHEN** the flow enters `GENERATING` with unresolved jobs
- **THEN** the system polls until completion or timeout and includes available transcripts in generation input

### Requirement: Transcription Failure Fallback
The system SHALL handle failed or timed-out transcription jobs without losing flow progress.

#### Scenario: One transcript fails
- **WHEN** at least one transcription job returns failure state
- **THEN** the bot marks that answer as failed transcription, keeps session active, and requests text fallback or continues with remaining data

