# 🛡️ Scam Recovery Commander — Digital Bodyguard

**Caspian AI Agent Hackathon 2026**

An AI agent that helps scam victims recover by coordinating bank complaints, cyber
crime reports, emergency alerts, and recovery tracking across email and Telegram.

> *"The victim panics; the agent mobilizes."*

## How It Works

The Digital Bodyguard runs on **two channels through a single `on_message` handler**:

- **Email** (`bodyguard@agents.trycaspianai.com`) — victim's primary contact; formal complaints
- **Telegram** (`@DigitalBodyguardBot`) — instant alerts, screenshots, status queries

When a victim reports a scam, the agent:

1. **Triages** — extracts bank, transaction ID, amount, scam type, victim name
2. **Collects evidence** — user sends UPI transaction screenshots → extracted via a
   vision model (Qwen3-VL) → each becomes a tracked transaction
3. **Blocks on missing info** — won't proceed until it has the victim's bank + account
   (re-reminds every 5 minutes until provided)
4. **Drafts complaints** — bank fraud complaint + cyber crime report, using ALL
   transactions, victim details, and fraudster identifiers
5. **Review → Confirm gate** — drafts are sent for review; nothing is marked as
   filed/forwarded until the user explicitly confirms (stores reference numbers)
6. **One-tap send** — each draft includes a pre-filled Gmail compose link so the user
   sends it from their OWN email (no SMTP, no credentials)
7. **Tracks recovery** — per-case timeline, status queries, follow-up escalation

## Key Features

| Feature | How it works |
|---|---|
| **Multi-transaction support** | Each screenshot adds a transaction (deduped by UTR); total amount auto-summed |
| **Vision extraction** | `Qwen3-VL-8B` reads PhonePe / GPay / Paytm screenshots → UTR, amount, recipient, bank |
| **SQLite persistence** | Cases survive agent restarts; multi-user isolated per `conversation_id` |
| **Blocking triage gate** | Recovery can't start until victim bank + account provided (type or screenshot) |
| **Review → Confirm** | Bank & cyber drafts need explicit user confirmation before marked as submitted |
| **One-tap Gmail links** | Pre-filled compose URLs — email goes from the user's own account |
| **Reference tracking** | `BNK-...` / `CYB-...` reference numbers stored per submitted complaint |
| **5-min reminders** | Auto-nudges until the blocking info is provided |

## Quick Start

### Prerequisites

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (package manager)
- A Caspian API key (free, no signup needed)
- A Telegram bot token (from [@BotFather](https://t.me/BotFather))
- An OpenAI-compatible API key for the LLM + vision model (Featherless $25 credit works)

### 1. Clone & Install

```bash
git clone https://github.com/saurabhharak/scam-recovery-agent.git
cd scam-recovery-agent
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

**LLM + vision keys:** use Featherless (free hackathon credit) or OpenAI. Set
`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `LLM_MODEL`, and `VISION_MODEL` in `.env`.

### 3. Configure

```bash
cp .env.example .env
# Edit .env with your keys:
# CASPIAN_API_KEY=comm_sandbox_...
# TELEGRAM_BOT_TOKEN=7123456789:AAE...
# OPENAI_API_KEY=rc_...            (Featherless) or sk-... (OpenAI)
# OPENAI_BASE_URL=https://api.featherless.ai/v1   (or https://api.openai.com/v1)
# LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
# VISION_MODEL=Qwen/Qwen3-VL-8B-Instruct
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
scam-recovery-agent/
├── src/
│   └── bodyguard/
│       ├── __init__.py          # Package
│       ├── main.py              # Entry point — connects channels, loads DB, starts listen()
│       ├── handler.py           # THE ONE on_message handler — routes text + screenshots
│       ├── case_manager.py      # State machine + in-memory cache (auto-persists)
│       ├── store.py             # SQLite persistence layer
│       ├── recovery_engine.py   # LLM drafts + vision screenshot extraction
│       ├── alert_system.py      # Proactive sends, follow-ups, 5-min reminders
│       ├── email_link.py        # Pre-filled Gmail/mailto compose links
│       ├── prompts.py           # All prompt templates (single source of truth)
│       └── config.py            # Environment config
├── tests/
│   ├── __init__.py
│   ├── conftest.py              # Test doubles (FakeMessage, FakeAlerts, FakeEngine)
│   ├── test_case_manager.py     # State machine + CRUD
│   ├── test_handlers.py         # Intent routing
│   ├── test_llm_json_parsing.py # Robust LLM JSON extraction
│   ├── test_vision_extraction.py# Screenshot extraction + media handling
│   ├── test_multi_transaction.py# Multi-transaction + victim/fraudster info
│   ├── test_victim_info.py      # Victim name capture
│   ├── test_persistence.py      # SQLite roundtrip + blocking gate
│   ├── test_draft_review.py     # Cyber review→confirm→file
│   ├── test_bank_review.py      # Bank review→confirm→forward
│   └── test_email_link.py       # Gmail compose link generation
├── scripts/
│   ├── verify.sh                # Pre-demo verification script
│   └── live_test.py             # One-shot live handler test
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
- **KISS** — one LLM + one vision model, two channels, no framework
- **DRY** — one prompt file, one message sender, one case structure
- **YAGNI** — no dashboard, no multi-tenant — just what the demo needs
- **Fail Fast** — invalid state transitions rejected; low-confidence intents clarified
- **TDD (tests first)** — every feature is proven before it ships

## Demo Script

See [PLAN.md](PLAN.md) for the full ≤3-minute demo narrative:
1. **The Trigger** — victim reports scam via email
2. **Parallel Actions** — bank complaint, cyber report, emergency alerts
3. **Recovery Journey** — status updates, escalation
4. **Resolution** — reimbursement confirmation, case summary

## Running Tests

```bash
uv run pytest
```

**75 tests** covering: state machine transitions, intent routing, LLM JSON robustness,
vision screenshot extraction, multi-transaction merging, victim/fraudster info,
SQLite persistence, blocking triage gate, review→confirm gates, and email links.

## License

MIT
