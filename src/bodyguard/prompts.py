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
{{
    "victim_name": "string or null",     # the victim's full name, if mentioned
    "bank_name": "string or null",
    "transaction_id": "string or null",
    "amount_lost": "string or null",
    "scam_type": "one of: upi_fraud, phishing, identity_theft, fake_landlord, investment_scam, other",
    "urgency": "one of: critical, high, medium",
    "summary": "one-line summary of what happened"
}}

Victim's message: {message_text}"""


CLASSIFY_INTENT_PROMPT = """You are an intent classifier for a scam recovery agent.

Classify the incoming message into EXACTLY ONE intent. This is a routing decision,
not an information extraction task.

Case state: {case_state}
Case summary: {case_summary}

Message: {message_text}

IMPORTANT: Respond with ONLY a JSON object, nothing else. No markdown, no prose.

The JSON must have exactly these keys:
{{
    "intent": "one of: NEW_SCAM_REPORT, INFO_RESPONSE, STATUS_CHECK, ADD_CONTACT, CONFIRM_ACTION, UNKNOWN",
    "confidence": 0.0-1.0,
    "extracted_info": {{}}
}}

Intent definitions:
- NEW_SCAM_REPORT: victim reports a NEW scam/fraud incident ("I got scammed", "₹50k gone", "fraud transaction")
- INFO_RESPONSE: victim provides details requested during triage (bank name, transaction ID, amount)
- STATUS_CHECK: victim asks about case progress ("any updates?", "what's happening?")
- ADD_CONTACT: victim wants to add an emergency contact ("alert my brother", "+91...")
- CONFIRM_ACTION: victim confirms completing an action ("yes, sent it", "done", "filed")
- UNKNOWN: anything else

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

=== VICTIM DETAILS ===
{victim_info}

=== FRAUDSTER DETAILS (if known) ===
{fraudster_info}

=== ALL TRANSACTIONS ===
{transactions}

Scam type: {scam_type}
Summary: {scam_summary}

The complaint should include:
1. The victim's full details (name, contact) as the complainant
2. EVERY transaction in a numbered list (date, time, amount, UTR/transaction ID, recipient UPI/account)
3. The total amount lost across all transactions
4. All known fraudster identifiers (UPI handle, phone number, name used, bank account if visible)
5. A clear incident description in factual language
6. Request for investigation and fund recovery
7. Statement that evidence (screenshots, call records) is available on request

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


UPI_TEXT_EXTRACTION_PROMPT = """You are extracting UPI transaction details from text shared by a scam victim.

The text comes from the "share" feature of a UPI app (Google Pay, PhonePe, Paytm,
BHIM) or a bank SMS. It may be formatted as structured text or free-form.

Extract the following fields and return ONLY a JSON object, no prose:

{{
    "amount": "string or null",          # e.g. "₹50,000" or "5000.00"
    "utr": "string or null",             # UTR / UPI transaction ID / bank ref number (12-digit number)
    "recipient": "string or null",       # UPI handle or name paid to (e.g. "scammer@okhdfcbank")
    "bank": "string or null",            # sender's bank
    "timestamp": "string or null",       # date and time of transaction
    "is_fraud_evidence": true            # always true — the victim is reporting this as fraud
}}

Shared text:
{shared_text}"""


VISION_EXTRACTION_PROMPT = """You are extracting UPI transaction details from a screenshot.

Look at this payment screenshot carefully. It may be from PhonePe, Google Pay, Paytm,
BHIM, or a bank SMS notification.

Extract these fields and return ONLY a JSON object, no prose:

{{
    "amount": "string or null",          # e.g. "₹5,000" or "5000.00"
    "utr": "string or null",             # UTR / UPI transaction ID / bank ref number (12-digit number)
    "recipient": "string or null",       # UPI handle or name paid to (e.g. "scammer@okhdfcbank")
    "bank": "string or null",            # sender's bank
    "timestamp": "string or null"        # date and time of transaction
}}

If a field is not visible in the screenshot, use null. Do not guess or invent values.
The victim is reporting this as fraud, so accuracy of the UTR and amount is critical."""


SCREENSHOT_GUIDANCE = """I received your screenshot, but I can't reliably read images yet.

Please help me by **copying the transaction details** from your UPI app and pasting them here. Here's how:

1. Open the payment app (PhonePe / Google Pay / Paytm)
2. Go to **History / Passbook** → tap on that transaction
3. Tap the **share / copy details** option (or screenshot → "Share as text")
4. Paste what it shows — I need:
   - **Amount**
   - **UTR / transaction ID** (12-digit number)
   - **Recipient UPI ID** (e.g. scammer@okhdfcbank)
   - **Date & time**
   - **Your bank**

Even just pasting the amount + UTR is enough to start your recovery."""
