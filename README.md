# VozBot - Bilingual AI Receptionist for a Small Insurance Office (English/Spanish)

VozBot is a production-minded spec for a **bilingual (English/Spanish)** AI call-answering system for a small insurance office. It answers after a configurable number of rings, collects intent and contact info, creates a callback task for staff, and produces call summaries without depending on RingCentral APIs or real-time audio streaming.

---

## Project Goal

Build a reliable **bilingual AI receptionist** that:

- Answers incoming calls after RingCentral forwards unanswered calls to a PSTN number we control.
- Detects or asks for language preference (English/Spanish).
- Identifies new vs. existing customers.
- Captures contact info and intent safely.
- Creates a callback task for Mom/Dad, with summary + transcript.
- Escalates to a human when required or requested.

### Non-goals

- No dependency on RingCentral APIs, webhooks, or real-time streaming.
- No direct insurance coverage advice or binding decisions.
- No collection of highly sensitive info (SSN, full DOB, payment card).
- No assumption of a specific telephony/STT/TTS/LLM vendor.

### Definition of "Done"

- [x] Calls reach VozBot via PSTN forward after X rings.
- [x] Bilingual greeting and language selection/detection work.
- [x] Call state machine completes with a callback task in DB.
- [x] Sensitive info guardrails enforced.
- [x] Summaries/transcripts stored and retrievable.
- [x] Manual transfer or callback handoff always available.

---

## System Name and Bilingual Requirement

VozBot is a **professional, bilingual AI receptionist** for an insurance office.
It must **support English + Spanish** for both speech understanding and speech output.

### Example bilingual greetings

- English: "Hello, this is VozBot, the automated assistant for the insurance office. I can help in English or Spanish. Which do you prefer?"
- Espanol: "Hola, soy VozBot, el asistente automatico de la oficina de seguros. Puedo ayudarle en ingles o en espanol. Cual prefiere?"

---

## RingCentral Routing Contract (Confirmed Facts + Unknowns)

**Confirmed by RingCentral assistant**

- Uses **RingCentral RingEX**.
- Admin Portal supports forwarding **unanswered incoming calls** to an **external PSTN number**.
- Setup path (as described):
  - Admin Portal -> profile picture (top right) -> Call rules -> Forward all calls
  - Incoming calls dropdown = "Forward the call"
  - Choose Number and enter external phone number
  - Select user/number
  - Add schedule (date/time selectors)
  - Save
- Ring count before a call becomes "missed" is configurable:
  - **1-15 rings (5-75 seconds)**
  - Hint: "Desktop & Mobile Apps ring setting set to 0 rings can cause calls to flash; set to at least 4 rings / 20s."
- Custom call handling rules (e.g., **forward after X rings**) can apply to:
  - Individual user extensions
  - Main company number (Auto-Receptionist)
  - Or by assigning the main number to a user/queue/IVR

**Unknown / not supported (per RC assistant)**

- Forwarding to SIP/PBX endpoints
- Programmatic call routing via API
- Webhooks for ringing/unanswered
- Real-time audio streaming on RingEX
- External forwarding limits per month

**Contract we rely on**

- RingCentral is **only the upstream router**.
- We receive a **normal inbound PSTN call** at our controlled number **after X rings**.
- VozBot **must not depend** on any RingCentral API or streaming features.

---

## End-to-End Call Flow (Text Diagrams)

### 1) Standard Flow (Both Languages)

```
Caller
  -> RingCentral rings office phones (Mom/Dad)
    -> No answer after X rings
      -> RingCentral forwards to VozBot PSTN number
        -> VozBot answers (bilingual greeting)
          -> Language detect/selection
            -> Intent + customer type + contact info
              -> Create call record + callback task
                -> Notify staff
                  -> End call
```

### 2) Escalation/Transfer Flow

```
Caller
  -> RingCentral rings office phones
    -> Forwarded to VozBot
      -> Bilingual dialog
        -> Escalation trigger or caller asks for a human
          -> Attempt transfer (if configured)
            -> If transfer succeeds: bridge
            -> If transfer fails: callback task created
```

---

## Phased Build Plan (Milestones)

### Phase 0 - Telephony Skeleton (No AI) ✅
- [x] Inbound PSTN number reachable (Twilio adapter)
- [x] Answer call, play static audio prompt
- [x] Record caller audio to storage
- [x] Save minimal call metadata to DB

### Phase 1 - STT/TTS Loop ✅
- [x] Speech-to-text integration (Deepgram adapter)
- [x] Text-to-speech integration (Deepgram adapter)
- [x] Bilingual menu logic in English/Spanish
- [x] Store transcript with language metadata

### Phase 2 - LLM Orchestration + Tools ✅
- [x] LLM orchestration with tool/function calling (OpenAI adapter)
- [x] State machine-driven dialog (12 states)
- [x] Create/update call record
- [x] Create callback task with summary
- [x] Bilingual prompt templates
- [x] Tool schemas with Pydantic validation
- [x] Guardrails enforced (no SSN/DOB/payment)

### Phase 3 - Escalation + Transfer ✅
- [x] Transfer call to human (Twilio Dial TwiML)
- [x] Fallback to callback task if transfer fails
- [x] Escalation triggers enforced (keywords, sentiment, legal, emergency)
- [x] Configurable transfer timeout (default 30s)

### Phase 4 - Dashboard + Notifications ✅
- [x] Staff queue UI (Streamlit dashboard)
- [x] SMS notifications (Twilio) for urgent callbacks
- [x] Email notifications (SendGrid/SES)
- [x] Searchable transcripts with highlighting

---

## Architecture Overview

**Pluggable components behind interfaces (no vendor lock-in).**

- **Telephony Adapter**
  - Receives inbound PSTN calls
  - Handles call control (answer, hang up, transfer)
- **Speech Layer**
  - STT (speech-to-text)
  - TTS (text-to-speech)
- **LLM Orchestrator**
  - State machine logic
  - Tool/function calling
  - Bilingual prompt policies
- **Storage**
  - Primary DB (e.g., Postgres)
  - Queue (e.g., Redis, SQS-compatible)
- **Observability**
  - Structured logs
  - Call metrics and costs
  - Error tracking

---

## Call State Machine

**States:**

- `INIT`
- `GREET`
- `LANGUAGE_SELECT`
- `CLASSIFY_CUSTOMER_TYPE` (new vs existing)
- `INTENT_DISCOVERY`
- `INFO_COLLECTION`
- `CONFIRMATION`
- `CREATE_CALLBACK_TASK`
- `TRANSFER_OR_WRAPUP`
- `END`

**Notes**
- Language selection/detection is required early.
- Every state must support English and Spanish prompts and parsing.

---

## Data Model Proposal

### `calls` table

Required fields:
- `id`
- `from_number`
- `language` (en/es)
- `customer_type` (new/existing/unknown)
- `intent`
- `status` (enum)
- `summary`
- `transcript`
- `costs` (json or numeric fields)
- `created_at`
- `updated_at`

### `callback_tasks` table

Required fields:
- `id`
- `call_id`
- `priority`
- `assignee` (optional)
- `name`
- `callback_number`
- `best_time_window`
- `notes`
- `status`
- `created_at`
- `updated_at`

---

## Tool-Calling Contract (Strict Schemas)

Use **strong validation** (e.g., Pydantic) for all tool calls.

### Tools (minimal set)

- `create_call_record`
- `update_call_record`
- `create_callback_task`
- `transfer_call`
- `send_notification`

### Example schema style (pseudocode)

```
create_call_record({
  from_number: str,
  language: "en" | "es",
  customer_type: "new" | "existing" | "unknown",
  intent: str,
  status: str,
  transcript: str,
  summary: str
})
```

Strict validation rules:
- Language must be `en` or `es`.
- No sensitive fields permitted.
- Required fields must be present.

---

## Guardrails and Compliance (Non-Negotiables)

- **Disclosure:** The system must always disclose it is an automated assistant.
- **Sensitive info restrictions:** Never collect SSN, full DOB, or payment card data.
- **Advice limits:** Must not provide binding coverage advice.
- **Escalation triggers:**
  - Caller asks for a human
  - Legal/claims urgency
  - Confusion or repeated failure
  - Threats, emergencies, or complaints

---

## Repo Layout

```
vozbot/
  telephony/
    adapters/          # TwilioAdapter (call control, transfer)
    webhooks/          # Twilio webhook handlers
  speech/
    stt/               # STTProvider ABC + DeepgramSTT
    tts/               # TTSProvider ABC + DeepgramTTS
  agent/
    orchestrator/      # LLMProvider ABC, OpenAI adapter, core loop
    prompts/           # Bilingual prompt templates (EN/ES)
    state_machine/     # CallState enum, StateMachine class
    tools/             # Pydantic schemas + tool handlers
    escalation.py      # EscalationDetector (keywords, sentiment)
  storage/
    db/                # SQLAlchemy models, session management
    services/          # CallService, TranscriptService
    migrations/        # Alembic migrations
  dashboard/           # Streamlit staff dashboard + search
  notifications/       # SMS (Twilio) + Email (SendGrid/SES)
  queue/               # Background workers
  main.py              # FastAPI application entry point

tests/
  unit/                # 800+ unit tests
  integration/         # End-to-end tests
```

---

## Local Dev Instructions

### Environment Variables (`.env.example`)

```
APP_ENV=development
PORT=8000

DB_URL=postgresql://user:pass@localhost:5432/vozbot
REDIS_URL=redis://localhost:6379/0

STT_PROVIDER=...
TTS_PROVIDER=...
LLM_PROVIDER=...

TELEPHONY_PROVIDER=...
INBOUND_NUMBER=+1XXXXXXXXXX
TRANSFER_NUMBER=+1XXXXXXXXXX

LOG_LEVEL=info
```

### Docker Compose

- Postgres
- Redis
- App service

```
docker-compose up -d
```

### Run Tests

```
pytest
```

### Deploy (Small VPS)

- Use HTTPS and valid TLS certificates.
- Configure inbound telephony webhooks to point to public HTTPS URL.
- Ensure firewall allows inbound traffic on 443.
- Run with a process manager (systemd or container).

---

## Testing Strategy

- **Unit tests**
  - Schemas (Pydantic validation)
  - State machine transitions
- **Integration tests**
  - Pre-recorded audio -> STT -> intent extraction
  - TTS output checks
- **Smoke tests**
  - Place real inbound call
  - Verify DB record + callback task
  - Confirm bilingual prompts

---

## Bilingual Coverage Checklist

- [x] Bilingual greeting in English/Spanish
- [x] Language detection or preference prompt
- [x] All state machine prompts in both languages
- [x] Transcripts stored with language metadata
- [x] Callback tasks and summaries consistent across languages
- [x] Escalation keywords in both languages
- [x] Transfer fallback messages in both languages
