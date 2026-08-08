# 🛡️ Scam Recovery Commander — Digital Bodyguard

**Caspian AI Agent Hackathon 2026**

An AI agent that helps scam victims recover by coordinating bank complaints, police
reports, emergency alerts, and recovery tracking across email and Telegram.

> *"The victim panics; the agent mobilizes."*

## How It Works

The Digital Bodyguard runs on **two channels through a single `on_message` handler**:

- **Email** (`bodyguard@agents.trycaspianai.com`) — victim's primary contact; formal complaints
- **Telegram** (`@DigitalBodyguardBot`) — emergency alerts, recovery checklists, status queries

When a victim reports a scam, the agent:
1. Extracts bank name, transaction ID, amount, and scam type
2. Drafts a formal bank fraud complaint (email)
3. Drafts a cyber crime report for cybercrime.gov.in
4. Alerts emergency contacts with scam warnings (Telegram)
5. Provides credit freeze and password hardening guides
6. Tracks the recovery timeline and escalates if the bank doesn't respond

## Quick Start

### Prerequisites

- Python 3.11+
- A Caspian API key (free, no signup needed)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An OpenAI-compatible API key (or use Featherless $25 credit)

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/scam-recovery-commander.git
cd scam-recovery-commander
uv sync --all-extras     # creates .venv, installs deps + dev extras
```

### 2. Get API Keys

**Caspian key** (instant, no signup):
```bash
curl -s -X POST https://api.trycaspianai.com/v1/projects/sandbox \
  -H 'Content-Type: application/json' -d '{"name":"bodyguard"}'
```

**Telegram bot token:**
1. Open Telegram → message [@BotFather](https://t.me/BotFather)
2. Send `/newbot`, choose name "Digital Bodyguard" and username `@DigitalBodyguardBot`
3. Copy the token (looks like `7123456789:AAE...`)

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your keys:
# CASPIAN_API_KEY=comm_sandbox_...
# TELEGRAM_BOT_TOKEN=7123456789:AAE...
# OPENAI_API_KEY=sk-...
```

### 4. Run

```bash
uv run python -m bodyguard.main
# or:
uv run bodyguard
```

You should see:
```
🛡️  Digital Bodyguard ONLINE
   Email:    bodyguard@agents.trycaspianai.com
   Telegram: @DigitalBodyguardBot
```

### 5. Test

```bash
# Send a test email
curl -s -X POST https://api.trycaspianai.com/v1/test-emails \
  -H "Authorization: Bearer $CASPIAN_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"text":"Help! I just got scammed. Someone called pretending to be from HDFC. I shared my OTP and ₹50,000 was debited. TXN ID: TXN123456. What do I do?"}'
```

### 6. Verify

```bash
curl -s "https://api.trycaspianai.com/v1/events?type=message.sent" \
  -H "Authorization: Bearer $CASPIAN_API_KEY"
```

## Project Structure

```
scam-recovery-commander/
├── src/
│   └── bodyguard/
│       ├── __init__.py          # Package
│       ├── main.py              # Entry point — connects channels, starts listen()
│       ├── handler.py           # THE ONE on_message handler — routes all channels
│       ├── case_manager.py      # State machine + in-memory case store
│       ├── recovery_engine.py   # LLM-driven draft generation
│       ├── alert_system.py      # Proactive sends + follow-up scheduler
│       ├── prompts.py           # All prompt templates (single source of truth)
│       └── config.py            # Environment config
├── tests/
│   ├── __init__.py
│   └── test_case_manager.py     # State machine + CRUD tests
├── scripts/
│   └── verify.sh                # Pre-demo verification script
├── .env.example                 # Template for required env vars
├── .gitignore
├── pyproject.toml               # Project metadata + dependencies
├── README.md                    # This file
├── HACKATHON.md                 # Hackathon rules + SDK reference
├── PLAN.md                      # Architecture + demo script
├── ENGINEERING.md               # Engineering principles
└── AGENTS.md                    # Auto-loaded project context
```

## Engineering Principles

This project follows [ENGINEERING.md](ENGINEERING.md) which documents:
- **Agent Harness Pattern** — LLM proposes drafts, harness executes sends
- **SOLID** — single responsibility per module; open/closed state router; Liskov via `message.reply()`
- **KISS** — one LLM, in-memory store, two channels, no framework
- **DRY** — one prompt file, one message sender, one case structure
- **YAGNI** — no database, no dashboard, no multi-tenant — just what the 3-min demo needs
- **Fail Fast** — invalid state transitions rejected; low-confidence intents clarified

## Demo Script

See [PLAN.md](PLAN.md) for the full ≤3-minute demo narrative, broken into three segments:
1. **0:00–0:30** — The Trigger (victim reports scam via email)
2. **0:30–1:30** — Parallel Actions (bank complaint, cyber report, emergency alerts)
3. **1:30–2:30** — Recovery Journey (status updates, escalation)
4. **2:30–3:00** — Resolution (reimbursement confirmation, case summary)

## Running Tests

```bash
uv run pytest
```

~10 tests covering: state machine transitions, intent classification, case CRUD.

## License

MIT
