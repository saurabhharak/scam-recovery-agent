# Caspian AI Agent Hackathon — Requirements & Reference

> Single source of truth for completing the hackathon. Verified against the official
> Unstop page (via API) and Devpost rules on 2026-08-08.

## The Brief (in one line)

Build an AI agent that **uses `caspian-sdk`** and runs on **at least two supported
communication channels through a single `on_message` handler**. Any domain, any use case.

- Judged on: **creativity/originality of the use case** + **functional implementation**.
- A rough agent doing something nobody thought of beats a polished one doing the obvious.
- Mocked/staged demos are NOT judged. Finalists may be asked to demo live.

## Key Dates (IST = UTC+5:30)

| Event | Date |
|---|---|
| Hacking window | 2026-07-28 → **2026-08-11 23:59 IST** (Devpost rules) |
| Registration deadline | **2026-08-10 00:00 IST** (Unstop) |
| Unstop submission close | 2026-08-17 00:00 IST (Unstop form; multiple submissions allowed) |
| Devpost submission close | 2026-08-11 23:59 IST |
| Judging | Aug 12–13 |
| Winners announced | 2026-08-20 |

⚠️ **TARGET AUG 11 AS THE REAL SUBMISSION DEADLINE** — the platforms disagree; Devpost is stricter. Do not wait for the 17th.

## Eligibility

- Students, freshers, and working professionals (all sectors) — open to everyone
- Team of **1–2**, solo allowed; inter-college/inter-specialisation teams OK
- **18+ required** (Devpost rules)
- One submission per team; free to enter; no prior Caspian experience needed

## Submission Requirements (checklist)

1. **Public GitHub repository** — public at time of submission and through judging
2. **Demo video** — ≤ 3 minutes, on YouTube / Vimeo / Loom (publicly accessible);
   must show the agent working on **at least two channels**
3. All code written during the 15-day window (open-source libs/models allowed; AI coding assistants allowed)
4. Submission in **English**; include **setup instructions** in the repo

### The Unstop submission form (3 mandatory fields)

1. **"Have you starred the GitHub repo: https://github.com/TryCaspian/caspian-sdk"** → answer **Yes**
2. **GitHub Link** → your public repo URL
3. **Video Link** → your demo video URL

## Prizes (Unstop official)

- **Winner:** ₹20,000 cash + $1,500 in Caspian credits
- **1st Runner Up:** $300 Caspian credits
- **2nd Runner Up:** $200 Caspian credits
- Starter credit for paid channels: email `ayush@trycaspianai.com`
- (Devpost lists a $14,500 pool incl. $25 Featherless credits for first 500 — same event, two listings)

## Contacts

- **Ayush** — ayush@trycaspianai.com (starter credits / questions)
- **Rushant Ashtputre** — rushant@saasden.club

---

# Building the Solution — Reference Material

## Core concept

One agent identity, every channel. All channels deliver a normalized `Message`
(`message.text`, `message.sender`, stable `conversation_id`) to the **same handler**;
`message.reply()` routes back to the correct channel/thread. Adding a channel is one
`connect_*()` call — never new handler code.

## Setup (30 seconds)

1. Mint a free API key (no signup):
   `curl -s -X POST https://api.trycaspianai.com/v1/projects/sandbox -H 'Content-Type: application/json' -d '{"name":"my-agent"}'`
   → returns `{"project_id":..., "api_key":"comm_sandbox_..."}`
2. Write to `.env`:
   ```
   CASPIAN_API_KEY=<api_key>
   CASPIAN_BASE_URL=https://api.trycaspianai.com
   ```
3. Install: `pip install caspian-sdk` (Python) or `npm install caspian-sdk` (TS, Node 18+)

## Minimal working agent (Python)

```python
from caspian_sdk import CommClient

client = CommClient()                            # reads CASPIAN_API_KEY from .env
email = client.connect_email(username="my-agent")  # free, instant, idempotent
# client.connect_telegram(bot_token=...)          # second channel: token from @BotFather
# client.install_discord(display_name="My Bot")   # or one-click OAuth

@client.on_message
def handle(message):
    answer = your_agent_logic(message.text)       # any framework: OpenAI Agents, LangGraph, raw LLM
    message.reply(answer)                          # plain text

client.listen()  # one loop, every channel
```

TypeScript: same contract, camelCase (`connectEmail`, `onMessage`, `listen()`), zero runtime deps.

## Channels — live on the hosted gateway (2026-08-08)

Verify live channels any time: `curl -s https://api.trycaspianai.com/v1/channels -H "Authorization: Bearer $CASPIAN_API_KEY"`

| Channel | Setup | Notes |
|---|---|---|
| **Email** | none | Free; `connect_email(username=...)` → user@agents.trycaspianai.com; idempotent |
| **Telegram** | BotFather token | Free; `connect_telegram(bot_token=...)` |
| **Discord** | one-click OAuth or own bot token | Free; `install_discord(display_name=...)` or `connect_discord(bot_token=...)` |
| **Slack** | one-click OAuth (Quick/Branded/Distribute) | Free; `install_slack(display_name=...)` or `connect_slack(...)` |
| **X / Twitter** | OAuth or own app tokens | Paid; reactive DMs only (never cold-DM) |
| **SMS / phone** | own Twilio/Telnyx number | BYO; `connect_phone(provider=..., ...)` |
| **Bluesky** | own handle + app password | Free, BYO; `connect_bluesky(identifier=..., app_password=...)` |

NOT live on hosted gateway yet (do not try; they 400): WhatsApp, iMessage, Instagram, Facebook, voice.
Multiple rows for one channel in `/v1/channels` = multiple providers → pass `provider=`.

**Easiest qualifying combo:** email (zero setup) + Telegram (bot token) or Discord (one-click).

## Verification (do this before recording the demo)

```bash
curl -s -X POST https://api.trycaspianai.com/v1/test-emails -H "Authorization: Bearer $CASPIAN_API_KEY" \
  -H 'Content-Type: application/json' -d '{"text":"hello, are you alive?"}'
```
- Within ~10s the running handler must print the message and reply.
- Confirm: `curl -s "https://api.trycaspianai.com/v1/events?type=message.sent"` → a `message.sent` event = integration complete.
- No reply from a REAL email? Check SPAM first — new sending domains get filtered; `message.sent` event means it sent.
- 409 on connect = token/number/account already connected elsewhere.

## Useful extras

- **Behavior guides:** `client.behavior_prompt()` → per-channel etiquette to append to your system prompt
  (Slack threads, WhatsApp 24h window, SMS length, iMessage no-markdown, X 280 chars).
- **Rich messages (`blocks`):** cards, buttons, lists — render natively per channel, degrade to text elsewhere.
- **Instant acks:** `client.listen(ack="On it, one moment…")` for channels without typing indicators (X, SMS, email).
- **Serverless:** `handle_webhook()` → run on AWS Lambda / Vercel / Cloudflare Workers.
- **Multi-tenant:** `client.create_customer(name)` / `client.create_agent(name)`, pass `customer_id`/`agent_id`.
- **Restart safety:** `connect_email()` is idempotent; `listen()` dedupes within a run; persist your own cursor for cross-restart dedup.
- **Custom email domain:** `client.add_domain("agents.acme.com")` → add `dns_records`, poll until `active`.

## Official links (always refer to these)

- Integration guide (agent-readable, always current): https://api.trycaspianai.com/SKILL.md
- SDK repo: https://github.com/TryCaspian/caspian-sdk
- Docs: https://www.trycaspianai.com/docs/
- REST reference: https://api.trycaspianai.com/docs
- llms.txt: https://github.com/TryCaspian/caspian-sdk/blob/main/llms.txt
- Discord community: https://discord.com/invite/A28qnkvgCM
- Unstop event: https://unstop.com/hackathons/caspian-ai-agent-hackathon-caspian-1726439
- Devpost event: https://caspian.devpost.com/
