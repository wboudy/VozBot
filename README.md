# VozBot - Bilingual AI Receptionist (English/Spanish)

VozBot is a **bilingual AI call-answering system** for small businesses. It answers calls, collects intent and contact info, creates callback tasks for staff, and produces call summaries.

## Current Status: Feature Complete ✅

All 4 phases implemented with **800+ tests passing**.

| Phase | Status | Features |
|-------|--------|----------|
| Phase 0 | ✅ | Telephony skeleton (Twilio) |
| Phase 1 | ✅ | STT/TTS (Deepgram), bilingual menu |
| Phase 2 | ✅ | LLM orchestration (OpenAI), state machine, tools |
| Phase 3 | ✅ | Escalation detection, call transfer, fallback |
| Phase 4 | ✅ | Staff dashboard (Streamlit), SMS/email notifications |

## Quick Start

```bash
# Clone and install
git clone https://github.com/wboudy/VozBot.git
cd VozBot
cp .env.example .env  # Fill in API keys
pip install -e .

# Run
docker-compose up -d  # Postgres + Redis
python -m vozbot.main

# Test
pytest
```

## Call Flow

```
Caller → Office phones ring → No answer → Forward to VozBot
  → Bilingual greeting → Language selection
    → Intent + contact info → Create callback task
      → Notify staff → End call
```

If caller requests human or escalation triggers fire:
```
→ Attempt transfer → Success: bridge call
                  → Failure: create urgent callback task
```

---

## Architecture

**Pluggable providers** - no vendor lock-in:

| Layer | Provider | Interface |
|-------|----------|-----------|
| Telephony | Twilio | `TelephonyAdapter` ABC |
| Speech-to-Text | Deepgram | `STTProvider` ABC |
| Text-to-Speech | Deepgram | `TTSProvider` ABC |
| LLM | OpenAI | `LLMProvider` ABC |
| Email | SendGrid/SES | `EmailProvider` ABC |

## Project Structure

```
vozbot/
  telephony/       # Twilio adapter + webhooks
  speech/          # STT/TTS providers
  agent/
    orchestrator/  # LLM provider, core loop
    state_machine/ # Call states
    tools/         # Pydantic schemas + handlers
    prompts/       # Bilingual templates
    escalation.py  # Trigger detection
  storage/         # Database models + services
  dashboard/       # Streamlit UI + search
  notifications/   # SMS + email service
tests/             # 800+ unit + integration tests
```

## Call State Machine

```
INIT → GREET → LANGUAGE_SELECT → CLASSIFY_CUSTOMER_TYPE
  → INTENT_DISCOVERY → INFO_COLLECTION → CONFIRMATION
    → CREATE_CALLBACK_TASK → TRANSFER_OR_WRAPUP → END
```

## Data Model

**`calls`**: id, from_number, language, customer_type, intent, status, summary, transcript, costs, timestamps

**`callback_tasks`**: id, call_id, priority, assignee, name, callback_number, best_time_window, notes, status, timestamps

## Guardrails

- Always discloses it's an AI assistant
- Never collects SSN, DOB, or payment info
- Never provides binding coverage advice
- Escalates on: human request, legal keywords, frustration, emergencies

## Environment Variables

See `.env.example` for full list. Key variables:

```bash
# Required APIs
DEEPGRAM_API_KEY=...
OPENAI_API_KEY=...
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...

# Phone numbers
TWILIO_PHONE_NUMBER=+1...
TRANSFER_NUMBER=+1...

# Database
DATABASE_URL=postgresql://...

# Notifications
STAFF_PHONE=+1...
STAFF_EMAIL=...
SENDGRID_API_KEY=...
```

## Development

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=vozbot

# Start dashboard
streamlit run vozbot/dashboard/app.py
```

## Deployment

1. Set up HTTPS with valid TLS
2. Configure Twilio webhooks to public URL
3. Run with process manager (systemd/Docker)
4. Set `APP_ENV=production`
