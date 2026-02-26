# review-persistence-and-notification Specification

## Purpose
TBD - created by archiving change implement-telegram-feedback-bot-v1. Update Purpose after archive.
## Requirements
### Requirement: SQLite Review Record Persistence
The system SHALL persist each completed feedback session into a `reviews` table with fields for Telegram identity, context, period, raw answers, generated review, final review, signature, publication consent, timestamps, and notification state.

#### Scenario: Completed session is saved
- **WHEN** user completes publication consent step
- **THEN** a record is inserted or updated in `reviews` with all collected session data

### Requirement: Raw Answer Traceability
The system SHALL store original user-provided text and transcript outputs in `answers_raw` as structured JSON to preserve source-level context.

#### Scenario: Mixed input sources are traceable
- **WHEN** a session contains both text and voice answers
- **THEN** `answers_raw` includes entries indicating source type and content for every asked question

### Requirement: Final Review Versioning
The system SHALL store both the first generated draft and the latest approved/edited final review version.

#### Scenario: User edits generated draft
- **WHEN** the user submits a manual correction after first draft
- **THEN** `review_generated` remains original draft and `review_final` is updated to the approved edited text

### Requirement: Owner Notification Delivery
The system SHALL notify the configured owner Telegram ID after session completion with a summary including signature, context, period, consent flag, raw answers, and final review.

#### Scenario: Notification sent for public review
- **WHEN** the user selects public consent and flow reaches completion
- **THEN** the system sends owner notification message and marks `notified=true`

### Requirement: Notification Failure Recovery
The system SHALL preserve completion data even when owner notification fails and SHALL keep `notified=false` for later retry.

#### Scenario: Telegram owner chat unavailable
- **WHEN** notification API call fails after record persistence
- **THEN** session remains completed, failure is logged, and `notified` remains false

