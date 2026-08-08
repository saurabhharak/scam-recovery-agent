# Project: Caspian AI Agent Hackathon

We are building an AI agent for the **Caspian AI Agent Hackathon** (15-day, fully online).

**Qualifying rule:** the agent must use **caspian-sdk** and run on **at least two supported
communication channels through a single `on_message` handler**. Judging = creativity of the use
case + functional implementation. Working-but-rough beats polished-but-obvious. Mocked demos are
not judged; finalists may be demoed live.

**Submission:** public GitHub repo + ≤3-min demo video (showing the agent working on 2+ channels).
The Unstop form also asks **"Have you starred the GitHub repo"** → answer Yes.

**Real deadlines (IST):** register before **Aug 10 00:00**; submit before **Aug 11 23:59** (Devpost
rules are stricter than Unstop's Aug 17 — treat Aug 11 as the hard deadline).

Full requirements, prizes, contacts, and the complete SDK integration reference live in:

@HACKATHON.md

We are building: **Scam Recovery Commander (Digital Bodyguard)** — an AI agent that helps scam
victims recover by coordinating bank complaints, police reports, emergency alerts, and recovery
tracking across channels. The victim panics; the agent mobilizes.

Implementation plan, architecture, state machine, demo script, and build timeline are in:

@PLAN.md

Engineering principles (SOLID, KISS, DRY, YAGNI, agent harness pattern, fail fast,
separation of concerns, anti-patterns) that govern all code in this project are in:

@ENGINEERING.md

Use these as the source of truth while building. When unsure about SDK behavior, consult
https://api.trycaspianai.com/SKILL.md (the live integration guide).
