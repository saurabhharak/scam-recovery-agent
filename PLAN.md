# 🛡️ Scam Recovery Commander — Implementation Plan

## Agent Identity
**Name:** Digital Bodyguard  
**Channel 1:** Email (`bodyguard@agents.trycaspianai.com`) — victim's primary contact; formal comms  
**Channel 2:** Telegram (`@DigitalBodyguardBot`) — instant alerts, emergency contacts, recovery steps  

## How It Qualifies (Hackathon Rules Checklist)

| Rule | Status |
|---|---|
| Uses `caspian-sdk` | ✅ `CommClient`, `on_message`, `connect_email`, `connect_telegram` |
| ≥2 channels, ONE handler | ✅ Email + Telegram, single `handle()` function |
| Channels through one handler | ✅ Same handler receives both; `message.reply()` routes correctly |
| Public GitHub repo | ✅ Will push before submission |
| Demo video ≤3 min | ✅ Must show agent on both channels live |
| Code written during window | ✅ All code will be new |
| Setup instructions in README | ✅ Will include |

## Channels to Deploy (both FREE)

1. **Email** (`connect_email(username="bodyguard")`) — zero setup, instant, idempotent
   - Victim contacts us from their real email
   - Formal complaint drafts sent back
   - Daily follow-ups with timeline status
2. **Telegram** (`connect_telegram(bot_token=<from @BotFather>)`) — needs one bot token
   - Urgent alerts to victim's emergency contacts
   - Step-by-step recovery checklist
   - Quick status queries

## Core Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    SINGLE on_message HANDLER                     │
│                                                                 │
│  message.text → classify_intent() → route to case state machine │
│  message.sender → identify which case this belongs to           │
│  message.conversation_id → stable per-case session              │
│  message.reply() → answer on correct channel automatically      │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  CASE MANAGER │   │ RECOVERY ENGINE│   │ ALERT SYSTEM  │
│  (in-memory)  │   │  (LLM-driven) │   │  (proactive)  │
├───────────────┤   ├───────────────┤   ├───────────────┤
│ - create case │   │ - bank email  │   │ - notify      │
│ - track state │   │ - cyber report │   │   emergency   │
│ - follow-ups  │   │ - CIBIL freeze │   │   contacts    │
│ - case history│   │ - password 2FA │   │ - daily recap │
└───────────────┘   └───────────────┘   └───────────────┘
```

## Case State Machine

```
TRIGGER ("I've been scammed...")
    │
    ▼
TRIAGE ─── extract: amount, bank, transaction_id, scam_type
    │
    ├──▶ BANK_ALERT ─── email bank fraud desk
    │
    ├──▶ CYBER_COMPLAINT ─── draft cyber cell report
    │
    ├──▶ CONTACT_ALERT ─── notify emergency contacts (Telegram)
    │
    ├──▶ CREDIT_FREEZE ─── guide through CIBIL/credit lock
    │
    ├──▶ PASSWORD_2FA ─── step-by-step account hardening
    │
    └──▶ RECOVERY_TRACKING ─── monitor, follow up, reimburse
            │
            ├── daily status check-in
            ├── escalate if no bank response in 48h
            └── RESOLVED ─── summary report
```

### Case State Data (per `conversation_id`)

```python
case = {
    "case_id": "conversation_id",   # stable per thread
    "victim_email": "sender@...",
    "state": "TRIAGE",              # current state machine position
    "bank_name": "HDFC",
    "transaction_id": "TXN123456",
    "amount_lost": "₹50,000",
    "scam_type": "upi_fraud",
    "timestamp_started": "2026-08-09T14:30:00+05:30",
    "emergency_contacts": ["+91-...", "+91-..."],
    "actions_completed": [],        # [{action, timestamp, result}]
    "pending_actions": [],          # [{action, deadline}]
    "cyber_complaint_number": None,
    "bank_fir_number": None,
    "follow_up_due": None,
}
```

## Intent Classification (LLM-powered)

Incoming `message.text` is classified into:

| Intent | Example messages | Action |
|---|---|---|
| `NEW_SCAM_REPORT` | "I got scammed", "₹50k gone", "fraud transaction" | Create new case, enter TRIAGE |
| `INFO_RESPONSE` | "HDFC bank", "TXN123456", "UPI fraud" | Fill case data, advance state |
| `STATUS_CHECK` | "Any updates?", "What's happening?" | Return case status + timeline |
| `ADD_CONTACT` | "Alert my brother +91..." | Add emergency contact |
| `CONFIRM_ACTION` | "Yes, send the email" | Execute pending action |
| `UNKNOWN` | Anything else | Ask for clarification |

## Per-Channel Behavior (via `behavior_prompt()`)

- **Email:** Formal, empathetic, structured. Full complaint letters. HTML or clean text.
- **Telegram:** Concise, urgent, actionable. Rich buttons for checklists. Quick status.

```python
system_prompt = system_prompt + "\n\n" + client.behavior_prompt()
```

## What We Need to Build

### 1. Project Scaffold
```
scam-recovery-commander/
├── README.md              # Setup instructions + demo link
├── .env.example           # Template for CASPIAN_API_KEY etc.
├── pyproject.toml         # Project metadata + dependencies (modern Python, uv-compatible)
├── uv.lock                # Locked dependency versions (generated by uv sync)
├── src/
│   └── bodyguard/         # Single package matching agent identity
│       ├── __init__.py
│       ├── main.py            # Entry point: CommClient, connect channels, listen()
│       ├── handler.py         # The ONE on_message handler + intent routing
│       ├── case_manager.py    # Case state machine, CRUD, in-memory store
│       ├── recovery_engine.py # LLM-driven action generators (emails, reports)
│       ├── alert_system.py    # Proactive alerts, follow-up scheduler
│       ├── prompts.py         # System prompts for the LLM
│       └── config.py          # Environment config
├── tests/
│   ├── __init__.py
│   └── test_case_manager.py   # State machine + CRUD tests
├── scripts/
│   └── verify.sh              # Pre-demo verification script
├── HACKATHON.md               # Hackathon rules + SDK reference
├── PLAN.md                    # This file
├── ENGINEERING.md             # Engineering principles
└── AGENTS.md                  # Auto-loaded project context
```

**Key structural decisions:**
- `src/` layout — prevents accidental imports of the package before installation
- `bodyguard` package — matches the agent's identity; single package, no premature splitting
- `pyproject.toml` — modern Python standard; `requirements.txt` is deprecated; uv reads this directly
- `config.py` — single source for env vars; every module imports `get_config()` instead of reading `os.getenv` directly (DRY)
- `scripts/verify.sh` — automated pre-demo check for env vars, API connectivity, live channels, and tests

### 2. LLM Integration
- Use any LLM (OpenAI, Anthropic Claude, Gemini — pick cheapest/fastest)
- $25 Featherless credits available
- Prompt: "You are a scam recovery specialist. Be calm, empathetic, and actionable."
- Two LLM roles:
  a) Intent classifier (fast, cheap model)
  b) Content generator (bank emails, cyber complaints — smarter model)

### 3. SDK Features to Use

| Feature | Where | Why |
|---|---|---|
| `client.on_message` | `main.py` | Single handler, both channels |
| `message.reply()` | `handler.py` | Auto-routes to correct channel |
| `message.sender` / `message.conversation_id` | `case_manager.py` | Case identity + tracking |
| `client.send_message(conversation_id, text)` | `alert_system.py` | Proactive follow-ups |
| `client.behavior_prompt()` | `handler.py` | Per-channel tone |
| `client.listen(ack="...")` | `main.py` | Instant ack for email |
| Rich `blocks` (cards/buttons) | Telegram replies | Recovery checklists |
| `message.typing()` | For long LLM calls | Keep the typing indicator alive |

## Demo Script (≤3 minutes) — The Narrative

### 0:00–0:30 — The Trigger
> **Email from victim:** "Help! I just got scammed. Someone called claiming to be from HDFC and I shared my OTP. ₹50,000 was debited from my account 10 minutes ago. What do I do?"

**Agent (email reply):** "I'm on it. Stay calm — we're going to handle this together. I've frozen your credit profile and I'm drafting complaints now. Meanwhile: 1) Do NOT share any more OTPs. 2) Lock your debit card via the HDFC app. 3) I'll send you a police complaint draft in 2 minutes. You're not alone in this."

### 0:30–1:30 — Parallel Actions
**Agent sends (email):** Drafted bank fraud complaint letter with transaction details filled in, ready to forward to `fraud@hdfcbank.com`.

**Agent sends (Telegram to emergency contacts):** "⚠️ URGENT: Saura's accounts may be compromised. A scammer impersonating HDFC called them and stole ₹50,000. Please: 1) Do NOT send money to anyone claiming to be Saura. 2) Do NOT share any OTPs. 3) Saura is safe and handling it. 4) Reply to this bot if you need to reach them."

**Agent sends (email):** "Step 3: Police complaint drafted. File this at cybercrime.gov.in. Here's your reference number template and the exact text to paste."

### 1:30–2:30 — Recovery Journey
**Agent (Telegram — 24 hours later follow-up):** "🛡️ Recovery Update: Day 1 complete. ✅ Bank complaint filed. ✅ Cyber cell report submitted (Case #CYB/2026/...). ✅ Credit frozen. ❌ Bank has not responded yet — I'll escalate tomorrow. Check your email for the full timeline."

**Agent (email — 48 hours later escalation):** "Dear HDFC Fraud Department, this is a follow-up to FIR #12345 filed on Aug 9 regarding unauthorized transaction TXN123456 for ₹50,000. We have not received a response in 48 hours. Per RBI guidelines, banks must resolve fraud complaints within 3 days..."

### 2:30–3:00 — Resolution
**Agent (email):** "🎉 Bank confirmed reimbursement of ₹50,000. Full recovery complete. Here's your case summary: Timeline, actions taken, contacts notified, final outcome. Your accounts are secure. I'll stay on watch for 30 more days — contact me anytime."

## Key SDK Integration Details

### main.py skeleton
```python
from caspian_sdk import CommClient
from handler import handle

client = CommClient()  # reads CASPIAN_API_KEY from .env

email = client.connect_email(username="bodyguard")
telegram = client.connect_telegram(bot_token=TELEGRAM_BOT_TOKEN)

print(f"Bodyguard email: {email['address']}")
print(f"Telegram bot: @{telegram['address']}")

@client.on_message
def on_message(message):
    handle(client, message)

client.listen(ack="🛡️ Bodyguard activated. Processing your report...")
```

### handler.py skeleton
```python
def handle(client, message):
    conversation_id = message.conversation_id
    case = case_manager.get_or_create(conversation_id, message)

    intent = classify_intent(message.text, case)

    if intent == "NEW_SCAM_REPORT":
        case_manager.create_case(conversation_id, message)
        message.reply(TRIAGE_RESPONSE)
        alert_system.notify_contacts(client, case)

    elif intent == "INFO_RESPONSE":
        case_manager.update_case(conversation_id, message.text)
        next_action = recovery_engine.get_next_action(case)
        message.reply(next_action)

    elif intent == "STATUS_CHECK":
        timeline = case_manager.get_timeline(conversation_id)
        message.reply(timeline)

    # ... more intents
```

## Timeline (2 days to build)

| Day | Tasks |
|---|---|
| **Day 1** (Today) | Scaffold project, get API key, connect email + Telegram, test basic handler. Build case manager + intent classifier. |
| **Day 2** (Tomorrow) | Build recovery engine (LLM-generated bank emails, police complaints). Build alert system (emergency contacts, follow-ups). Polish + test full flow. |
| **Day 3** (Aug 11) | Record demo video. Push GitHub repo. Submit on Unstop + Devpost. |

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Telegram bot token takes time | Get it from @BotFather TODAY (5 min) |
| LLM costs | Use cheapest model for classifier, Featherless $25 for smart tasks |
| SDK quirks | Read live SKILL.md; test with `test-emails` endpoint first |
| Demo video quality | Screen record OBS; simple, unedited; show both channels side by side |
| Email goes to spam | Use `test-emails` endpoint instead of real email in demo (it's instant) |

## Prize Targets

| Place | Prize |
|---|---|
| Winner | ₹20,000 cash + $1,500 Caspian credits |
| 1st Runner Up | $300 Caspian credits |
| 2nd Runner Up | $200 Caspian credits |

## Submission Checklist (Aug 11)

- [ ] GitHub repo is PUBLIC
- [ ] README has setup instructions (clone → .env → pip install → run)
- [ ] Demo video ≤3 min, on YouTube/Loom, shows agent on BOTH channels
- [ ] Unstop form: Star = Yes, GitHub link, Video link
- [ ] Devpost form (if separate)
- [ ] Verify: `test-emails` endpoint returns reply
- [ ] Verify: Telegram bot replies
- [ ] Code is clean, no secrets committed, .env in .gitignore
