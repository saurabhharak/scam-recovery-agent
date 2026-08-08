"""Prompt templates for the Scam Recovery Commander.

All LLM prompts live here — never inline strings in the handler or engine.
"""

SYSTEM_PROMPT = """You are the Digital Bodyguard — a calm, competent, and highly effective
scam recovery specialist. Your job is to help scam victims recover their money, secure their
accounts, and navigate the recovery process.

Core principles:
- Be calm and empathetic. The victim is in shock. Your confidence is their anchor.
- Be actionable. Every response must include clear next steps.
- Be thorough. Leave no recovery path unexplored.
- Never panic. Never lecture. Never blame the victim.

You operate across email and Telegram. Adapt your tone to the channel but never your
competence. For email: be formal, structured, and detailed. For Telegram: be concise,
actionable, and urgent.

You do not provide legal advice. You provide practical recovery steps based on established
fraud recovery procedures in India (RBI guidelines, cyber crime reporting, CIBIL processes)."""


TRIAGE_PROMPT = """A scam victim has just reported an incident. Extract the following
information from their message. If something is missing, ask for it specifically.

Return a JSON object:
{
    "bank_name": "string or null",
    "transaction_id": "string or null",
    "amount_lost": "string or null",
    "scam_type": "one of: upi_fraud, phishing, identity_theft, fake_landlord, investment_scam, other",
    "urgency": "one of: critical, high, medium",
    "summary": "one-line summary of what happened"
}

Victim's message: {message_text}"""


CLASSIFY_INTENT_PROMPT = """Classify this message from a scam recovery case. The case context
is provided for reference.

Case state: {case_state}
Case summary: {case_summary}

Message: {message_text}

Return a JSON object:
{
    "intent": "one of: NEW_SCAM_REPORT, INFO_RESPONSE, STATUS_CHECK, ADD_CONTACT, CONFIRM_ACTION, UNKNOWN",
    "confidence": 0.0-1.0,
    "extracted_info": {}
}

If confidence is below 0.7, the system will ask the victim to clarify."""


BANK_COMPLAINT_PROMPT = """Write a formal bank fraud complaint email. Use the victim's case
details below. The email should be addressed to the bank's fraud department.

Case details:
- Bank: {bank_name}
- Transaction ID: {transaction_id}
- Amount lost: {amount_lost}
- Scam type: {scam_type}
- Date of incident: {date}

The email should:
1. State the facts clearly and chronologically
2. Include all identifying transaction details
3. Request immediate blocking of the beneficiary account
4. Reference RBI guidelines on fraud liability
5. Request a written acknowledgement and FIR number

Tone: firm, professional, detailed. Include placeholders for the victim to fill in their
account number and contact details."""


CYBER_COMPLAINT_PROMPT = """Draft a cyber crime complaint for filing at cybercrime.gov.in
or the nearest cyber cell. Use these case details:

- Bank: {bank_name}
- Transaction ID: {transaction_id}
- Amount lost: {amount_lost}
- Scam type: {scam_type}
- Date of incident: {date}

The complaint should include:
1. Incident description in clear, factual language
2. All transaction details (date, time, amount, UTR/transaction ID)
3. Suspected perpetrator details (if known — phone number, name used, platform)
4. Request for investigation and fund recovery
5. Statement that evidence (screenshots, call records) is available on request

Format as a narrative that can be pasted directly into the cyber crime portal.
Use Indian legal terminology where appropriate."""


EMERGENCY_ALERT_PROMPT = """Write an urgent alert message for the victim's emergency contacts.
This goes out on Telegram and must be clear, alarming but not panic-inducing.

Victim name: {victim_name}
What happened: {scam_summary}

The alert must:
1. Identify that this is a scam emergency
2. Warn contacts NOT to send money to anyone claiming to be the victim
3. Warn contacts NOT to share any OTPs or personal information
4. State that the victim is safe and handling the situation
5. Provide this bot as the contact point for updates

Tone: urgent, clear, protective. Maximum 5 bullet points."""


STATUS_UPDATE_PROMPT = """Generate a recovery status update. Use the case timeline below.

Case state: {case_state}
Actions completed: {actions_completed}
Pending actions: {pending_actions}
Days since incident: {days_elapsed}

The update should:
1. Start with a one-line summary (good news first if any)
2. List completed actions with ✅ marks
3. List pending actions with ⏳ marks and deadlines
4. Include any escalation notices (e.g., "Bank has not responded in 48h")
5. End with the next concrete step

Tone: factual, reassuring, forward-looking."""


CREDIT_FREEZE_GUIDE = """Write a step-by-step guide for the victim to freeze their credit
report and prevent identity theft. Include:

1. How to place a CIBIL credit freeze/dispute
2. How to alert Experian and Equifax
3. How to enable SMS/email alerts on all bank accounts
4. How to check for unauthorized credit inquiries
5. Timeline: how long each step takes

Format: numbered steps with estimated time per step. Channel-appropriate."""


PASSWORD_2FA_GUIDE = """Write a step-by-step guide for the victim to harden all their accounts:

1. Which accounts to prioritize (bank, email, social media, payment apps)
2. How to enable 2FA on each (WhatsApp 2FA, Google Authenticator, bank app 2FA)
3. How to check and revoke active login sessions
4. How to change passwords securely (password manager, no reused passwords)
5. Common scammer account-recovery tricks to watch for

Format: checklist style. Short, actionable, prioritized by risk."""


FOLLOW_UP_EMAIL_PROMPT = """Write a follow-up escalation email to a bank that has not responded
to a fraud complaint within 48 hours. Reference the original complaint.

Case details:
- Bank: {bank_name}
- Transaction ID: {transaction_id}
- Amount lost: {amount_lost}
- Original complaint date: {complaint_date}
- Hours elapsed: {hours_elapsed}

The escalation should:
1. Reference the original complaint by date and transaction
2. Note the 48-hour silence
3. Cite RBI guidelines on fraud complaint resolution timelines
4. Threaten escalation to the Banking Ombudsman if no response within 24 hours
5. Copy the cyber crime cell reference number

Tone: escalated but professional. This is the second warning, not the first."""


RESOLUTION_SUMMARY_PROMPT = """Generate a final case resolution summary. The case is closed.

Case details:
- Total duration: {duration}
- Amount lost: {amount_lost}
- Amount recovered: {amount_recovered}
- Actions taken: {actions_completed}
- Outcome: {resolution_outcome}

The summary should:
1. Celebrate the recovery (or acknowledge the outcome honestly)
2. List every action taken chronologically
3. Provide a final security checklist for the victim
4. Include resources for ongoing vigilance
5. Remind them the Bodyguard stays on watch for 30 more days

Tone: warm, conclusive, empowering."""
