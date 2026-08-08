# Engineering Principles — Scam Recovery Commander

> Curated from production AI agent patterns (2026), classic software engineering principles,
> and tailored to our specific architecture. This is not theory — every principle maps to a
> concrete decision in our codebase.

---

## 1. The Agent Harness Pattern (The Most Important One)

**Principle:** The LLM proposes; the harness executes. Never let the model call tools directly.

Why it matters for us: Our agent drafts bank complaint emails, cyber cell reports, and emergency
alerts. The LLM generates the *content* but the *execution* (sending the email, posting to Telegram)
must go through validated, logged, permission-gated harness code.

```
BAD:  LLM → calls send_email() directly → email sent
GOOD: LLM → proposes draft → harness validates → harness sends → harness logs
```

**Our implementation:**

```
handler.py          ← LLM proposes intent + content
case_manager.py     ← Harness validates state transitions
recovery_engine.py  ← LLM generates drafts (NOT sends)
alert_system.py     ← Harness executes sends with logging
```

Every risky action (sending a bank complaint, alerting emergency contacts) starts as a
**draft** that the harness then commits. The LLM can't accidentally send 50 emails because
`send_email` is never a tool the LLM can call directly — it's harness code.

---

## 2. SOLID Principles (Applied to AI Agents)

### S — Single Responsibility

| Component | One job | Does NOT |
|---|---|---|
| `handler.py` | Route messages to intents | Manage state, generate content |
| `case_manager.py` | Case state machine + storage | Send messages, call LLM |
| `recovery_engine.py` | Generate drafts via LLM | Store cases, send messages |
| `alert_system.py` | Proactive sends + scheduling | Manage case state |
| `prompts.py` | Prompt templates only | Any logic |

Every module has exactly one reason to change. If bank complaint format changes, only
`prompts.py` changes. If we add a new recovery step, only `recovery_engine.py` changes.

### O — Open/Closed

The state machine handles 7 states today. Adding an 8th state (e.g., `INSURANCE_CLAIM`)
should NOT require modifying the handler — only adding a new handler function + registering
it in a state-to-handler map.

```python
# handler.py — STATE_HANDLERS dict, extend without modifying router
STATE_HANDLERS = {
    "TRIAGE": handle_triage,
    "BANK_ALERT": handle_bank_alert,
    "CYBER_COMPLAINT": handle_cyber_complaint,
    # NEW: "INSURANCE_CLAIM": handle_insurance_claim <- added here only
}
```

### L — Liskov Substitution

All channel responses use the same `message.reply()` contract. Whether on email or Telegram,
the handler calls the same method. The SDK's channel adapters are interchangeable at the
handler level — we never branch on channel type in the handler.

```python
# BAD:
if message.channel == "email":
    format_formal_response(...)
elif message.channel == "telegram":
    format_quick_response(...)

# GOOD:
message.reply(content)  # SDK routes + formats per channel. Use behavior_prompt() for tone.
```

### I — Interface Segregation

Cases don't expose their full internal dict. `case_manager` exposes purpose-built methods:

```python
# BAD:  handler directly reads case["bank_name"]
# GOOD: case_manager.get_case_field(conversation_id, "bank_name")
#       case_manager.advance_state(conversation_id, "BANK_ALERT")
#       case_manager.add_action(conversation_id, action_dict)
```

LLM calls have thin interfaces: `classify_intent(text) → Intent` and `generate_draft(prompt_template, case) → str`.

### D — Dependency Inversion

The LLM provider (OpenAI, Anthropic, Featherless) is injected, not hardcoded:

```python
# recovery_engine.py
class RecoveryEngine:
    def __init__(self, llm_client: LLMClient):  # depends on abstraction
        self.llm = llm_client

# main.py
engine = RecoveryEngine(OpenAIClient(api_key=...))  # concrete injected at startup
```

Switching from OpenAI to Anthropic means one line change in `main.py`, zero changes in engine.

---

## 3. KISS (Keep It Simple, Stupid)

Applied ruthlessly to a hackathon project:

- **One LLM, two roles.** Not two LLMs, not a multi-agent swarm. One model does intent
  classification (fast, cheap prompt) AND content generation (longer, smarter prompt).
  Switch to a cheaper model for classification only if cost becomes real.
- **In-memory case store.** No database, no Redis, no vector DB. A `dict` keyed on
  `conversation_id`. Cases are ephemeral (demo scenario). Post-hackathon, swap to SQLite
  by changing one module.
- **No orchestration framework.** No LangGraph, no CrewAI. The handler is a plain function
  with a state machine dict. Adding a framework is premature — we don't have a problem it solves.
- **Two channels, not five.** Email + Telegram qualifies. Adding more channels dilutes the
  demo and adds nothing to the judging criteria.
- **`message.reply()` only.** No rich blocks, no buttons, no cards for v1. Plain text
  works on all channels. Add blocks only if the demo needs them for polish — never before
  the core flow works.

---

## 4. DRY (Don't Repeat Yourself)

- **One system prompt** shared across both LLM roles; append `behavior_prompt()` for per-channel
  tone instead of writing two prompts.
- **One case data structure.** `case_manager.py` is the single source of truth for what a case
  looks like. No module redefines or copies fields.
- **One message sender utility.** `alert_system.py` wraps `client.send_message()` with logging
  and error handling. No module calls `client.send_message()` directly.
- **Prompt templates in one file.** `prompts.py` has every template. If a template exists,
  it lives there — never inline strings in the recovery engine.

---

## 5. YAGNI (You Ain't Gonna Need It)

Things we are deliberately NOT building because they don't help us win:

- ❌ Multi-tenant support (one agent, one user per demo — `customer_id`/`agent_id` not needed)
- ❌ User authentication / login (demo script uses known sender emails)
- ❌ Persistent database (in-memory dict is sufficient for a 3-minute demo)
- ❌ Web dashboard (demo is terminal + two channels side by side)
- ❌ Scheduled background jobs (demo simulates "24 hours later" by fast-forwarding)
- ❌ PDF generation for reports (plain text summary in the demo)
- ❌ Rate limiting / abuse prevention (not relevant for a single demo run)
- ❌ Custom email domain (free instant inbox works perfectly)

**The rule:** if removing it doesn't break the 3-minute demo, don't build it.

---

## 6. Fail Fast

The agent must fail clearly at every layer, never silently:

```python
# Intent classification: if confidence < threshold, ask for clarification
intent, confidence = classify_intent(message.text)
if confidence < 0.7:
    message.reply("I want to help. Can you tell me more about what happened?")
    return

# State transitions: reject invalid ones with a clear error
if not VALID_TRANSITIONS[current_state].includes(new_state):
    log_error(f"Invalid transition: {current_state} → {new_state}")
    message.reply("Something went wrong with your case. Let me get a human to help.")
    return

# LLM calls: timeout, retry, then degrade gracefully
try:
    draft = llm.generate(prompt, timeout=10)
except LLMTimeoutError:
    draft = FALLBACK_TEMPLATES.get(template_name, "Generating your document... please wait.")
```

State machine has explicit valid transitions (from our PLAN.md). Any attempt to jump from
TRIAGE → RESOLVED without passing through intermediate states is caught and logged.

---

## 7. Context Window Management

Our handler runs in a long-lived `client.listen()` loop. The LLM's context window is finite.
Rules:

- **Summarize, don't append.** After 10 messages in a case, compact older turns into a
  running summary: "Victim reported ₹50,000 UPI fraud from HDFC account on Aug 9. TXN ID
  TXN123456. Bank complaint filed. Cyber report submitted."
- **Case state is context.** The case dict IS the context the LLM needs. Pass structured
  case data as JSON, not raw conversation history.
- **Tool results are JIT.** Don't load the full SDK docs or channel list into the prompt.
  Only include what the current turn needs.

---

## 8. Model Proposes; Harness Executes (In Practice)

Applied to our specific actions:

| Action | LLM's job | Harness's job |
|---|---|---|
| Bank complaint | Generate the email body | Validate recipient, log the send, track in case |
| Cyber complaint | Generate the form text | Log reference number, add to timeline |
| Emergency alert | Generate the alert message | Verify contacts list, log each send, confirm delivery |
| Status update | Generate summary text | Pull actual case timeline, verify data |
| Follow-up | Detect deadline breach | Compare timestamps, trigger escalation |

The LLM never decides WHO to alert or WHEN — that's harness logic. The LLM only decides
WHAT to say.

---

## 9. Separation of Concerns (Channel-Agnostic Core)

```
┌──────────────────────────────────────────────────┐
│               caspian-sdk (CommClient)            │  ← Channel plumbing
├──────────────────────────────────────────────────┤
│  handler.py      ← routes messages to intents     │  ← Single entry point
├──────────────────────────────────────────────────┤
│  case_manager.py ← state machine + storage        │  ← Channel-agnostic core
│  recovery_engine.py ← LLM → drafts                │  ← No channel awareness
│  prompts.py      ← templates                      │  ← No channel awareness
├──────────────────────────────────────────────────┤
│  alert_system.py ← sends via client.send_message  │  ← Thin channel wrapper
└──────────────────────────────────────────────────┘
```

The core (case_manager, recovery_engine, prompts) has ZERO awareness of which channel a
message came from. Only the handler and alert_system know about channels — and they use
the SDK's abstraction, not raw channel APIs.

---

## 10. Observability (Even for a Hackathon)

Minimal but critical for debugging the demo:

```python
# Every action logged with structured data
def log_action(case_id, action, detail):
    print(f"[{timestamp}] CASE:{case_id} ACTION:{action} {detail}")

# Examples of what gets logged:
log_action("conv_abc123", "STATE_CHANGE", "TRIAGE → BANK_ALERT")
log_action("conv_abc123", "LLM_CALL", "classify_intent: 0.94 confidence, 0.3s")
log_action("conv_abc123", "MESSAGE_SENT", "email, 450 chars, bank_complaint draft")
log_action("conv_abc123", "CONTACT_ALERT", "notified +919876543210 via telegram")
```

When the demo breaks (and it will during rehearsal), these logs tell us exactly where.
Print to stdout; the terminal running `client.listen()` is our observability dashboard.

---

## 11. Conflict Resolution (When Principles Clash)

| Conflict | Resolution |
|---|---|
| DRY vs KISS | DRY wins if the duplication is in 3+ places. KISS wins under 3. |
| SOLID vs deadline | Single Responsibility is non-negotiable. Interface Segregation is optional. |
| YAGNI vs "what if judges ask..." | YAGNI wins. Build what the demo needs; nothing else. |
| Fail Fast vs user experience | Fail Fast internally (log, catch). Be empathetic externally ("Let me get a human"). |
| Rich features vs demo time | The demo shows 1 complete flow, not 10 half-built features. Scope down. |

---

## 12. Testing Strategy (Hackathon-Calibrated)

What to test (because it WILL break):
1. **State machine:** Valid and invalid transitions. Write 5 tests.
2. **Intent classification:** "I got scammed" → NEW_SCAM_REPORT. "HDFC" → INFO_RESPONSE. Write 3 tests.
3. **Case CRUD:** Create, update, advance state. Write 3 tests.

What NOT to test:
- SDK integration (Caspian's tests cover this; assume it works)
- LLM output quality (too slow to test deterministically; validate manually)
- Channel connectivity (test live, not in unit tests)

Total test budget: ~10 unit tests, 5 minutes to run, covers the deterministic parts.

---

## 13. Anti-Patterns (What We Reject)

| Anti-pattern | Why we reject it |
|---|---|
| Giant system prompt | Leads to prompt injection and unpredictable behavior. Use structured instructions. |
| LLM calls tools directly | Security nightmare. Harness gates all execution. |
| `execute_anything` tool | Never. Every action is a purpose-built function with validation. |
| Channel branching in handler | Defeats the point of the SDK. Let `behavior_prompt()` handle tone. |
| Multi-agent before single-agent works | Our single handler IS the agent. Adding more agents adds failure modes. |
| `try/except Exception` (bare) | Catch specific errors. Bare except hides bugs that kill the demo. |

---

## Quick Reference Card (Print This)

```python
# ✅ DO
message.reply(text)                              # Let SDK route the reply
case = case_manager.get(conversation_id)         # Access state via manager
draft = engine.generate(prompt_template, case)   # LLM generates, harness sends
log_action(case_id, action, detail)              # Log everything

# ❌ DON'T
if message.channel == "email": ...               # Don't branch on channel
case["bank_name"] = ...                           # Don't mutate case dict directly
llm.call_tool("send_email", ...)                  # LLM never sends directly
raise Exception("something broke")               # Don't bare-raise
print("debug:", variable)                         # Use log_action, not print
```

---

## 14. TDD Workflow (Project Policy — Tests FIRST)

**Rule:** Tests are written BEFORE the code they test. This is not a suggestion — it is
the project's policy (matching the hackathon's fail-fast philosophy and ENGINEERING.md §12).

### The Loop (Red → Green → Refactor)

```
RED    Write a failing test for ONE behavior (assert intent → handler mapping,
       state change, or reply text). Run it. Confirm it fails for the RIGHT reason
       (missing feature, not a typo).

GREEN  Write the minimal code to pass. No extra features, no premature abstraction.

REFACTOR  Clean up duplication WITHOUT changing behavior. Tests still pass.
```

### What This Looks Like in Practice

1. New behavior? **Write `tests/test_*.py` FIRST** — it defines the contract.
2. Run `uv run pytest` → the new test fails (RED).
3. Implement in `src/bodyguard/` → tests pass (GREEN).
4. Extract helpers only when the same dance repeats (DRY threshold: 3+ places).

### Test Doubles (never touch network in tests)

`tests/conftest.py` provides:
- `FakeMessage` — mimics SDK `Message`; records `.reply()` and `.typing()` calls
- `FakeAlerts` — records sends; `run_recovery_loop` is a **no-op** (no threads in tests)
- `FakeEngine` — returns canned `classify_intent` / `extract_triage_info`; no real LLM

### Hard Rules

- Tests NEVER call the real LLM, real channels, or real timers.
- The module-level `case_manager` singleton is reset before each test (autouse fixture).
- `uv run pytest` is the gate before ANY commit. Red → commit only after GREEN.
- If a test exposes a design flaw (like an invalid state transition), **fix the design**,
  not the test — unless the test itself encodes a mistake.

### Why This Wins the Demo

The 3-minute demo has no retakes. A handler that fails mid-recording kills the video.
TDD means every state handler, every reply, every transition is proven before the
camera ever records. When the demo breaks (and it will during rehearsal), the tests
tell us exactly which handler is wrong — in milliseconds, not minutes.
