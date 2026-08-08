"""The ONE on_message handler — routes both email and Telegram messages.

This is where intent classification meets the state machine. Every message from
any channel hits this function. It never branches on channel type (Liskov).
Channel-specific tone is handled by behavior_prompt(), not if/elif chains.
"""

from datetime import datetime, timezone

from caspian_sdk import CommClient

from bodyguard.case_manager import CaseState, case_manager
from bodyguard.recovery_engine import RecoveryEngine
from bodyguard.alert_system import AlertSystem

TRIAGE_INTRO = """🛡️ *Digital Bodyguard activated.*

I'm on it. Stay calm — we're going to handle this together.

To file your complaints, I'll need a few things. First, **your details** for the police/cyber cell report:

1. Your **full name**
2. Your **bank** the money went from (HDFC, SBI, ICICI, etc.)

Then the **transaction details** — you can send me **screenshots** or paste them:
3. **Amount(s)** and **UTR / transaction ID(s)** — if money left in *multiple* transactions, send me each one (a screenshot works for each)
4. The **fraudster's UPI ID or phone number** if you have it (from the payment receipt)

Just reply with whatever you know — I'll ask for what's missing."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()[:19]


def handle(client: CommClient, message, engine: RecoveryEngine, alerts: AlertSystem):
    """Single handler for ALL channels. Never branches on channel type.

    Args:
        client: The CommClient instance (passed for reply/typing).
        message: The normalized Message from Caspian SDK.
        engine: RecoveryEngine for LLM-generated drafts.
        alerts: AlertSystem for proactive sends.
    """
    conversation_id = message.conversation_id
    sender = (message.sender or {}).get("address", "anonymous")
    text = (message.text or "").strip()
    media = getattr(message, "media", []) or []

    # A screenshot of a UPI transaction takes priority over the text intent —
    # PhonePe shares marketing text + a screenshot, and the real data is in
    # the image. A panicked user may send multiple screenshots.
    if media:
        _handle_media(client, message, engine, alerts, conversation_id, sender)
        return

    if not text:
        message.reply("I didn't catch that — what can I help with?")
        return

    case = case_manager.get_or_create(conversation_id, sender)

    # Classify intent
    intent_result = engine.classify_intent(
        message_text=text,
        case_state=case.state.value,
        case_summary=case_manager.get_summary_for_llm(conversation_id),
    )
    intent = intent_result.get("intent", "UNKNOWN")
    confidence = intent_result.get("confidence", 0.0)

    # Low confidence → ask for clarification (Fail Fast)
    if confidence < 0.7 and intent != "UNKNOWN":
        message.reply(
            "I want to help. Can you tell me more about what happened? "
            "For example: which bank, what amount, and when did this happen?"
        )
        return

    # Route to state handler via dict — open/closed, extend without modifying router
    _STATE_ROUTER.get(case.state, {}).get(
        intent, _handle_unknown
    )(client, message, case, engine, alerts, intent_result)


def _normalize_media_url(url: str) -> str:
    """Fix the malformed media URLs emitted by the Caspian gateway.

    Observed: 'https://api.telegram.orgfile/bot.../photos/file_0.jpg'
    (missing slash) — the vision model can't fetch that. Correct it to
    'https://api.telegram.org/file/bot.../photos/file_0.jpg'.
    """
    if url and "api.telegram.orgfile" in url:
        return url.replace("api.telegram.orgfile", "api.telegram.org/file")
    return url


def _handle_media(client, message, engine, alerts, conversation_id, sender):
    """Process screenshot(s) — extract UPI transaction details via vision.

    Multiple screenshots are merged (each may show partial data). If the UTR
    is still missing after merging, ask the user for it (fail fast).
    """
    media_urls = [_normalize_media_url(m.get("url")) for m in message.media if m.get("url")]
    if not media_urls:
        message.reply("I received an attachment but couldn't read it. Could you describe what happened?")
        return

    case = case_manager.get_or_create(conversation_id, sender)
    message.typing()

    if len(media_urls) == 1:
        info = engine.extract_from_screenshot(media_urls[0])
    else:
        info = engine.extract_from_screenshots(media_urls)

    utr = info.get("utr")
    amount = info.get("amount")
    recipient = info.get("recipient")
    bank = info.get("bank")

    # Record as a transaction in the case (dedupes on UTR, sums total)
    txn = {
        "amount": amount,
        "utr": utr,
        "recipient": recipient,
        "bank": bank,
        "timestamp": info.get("timestamp"),
    }
    added = case_manager.add_transaction(case.case_id, txn)

    # Fraudster identifiers from the screenshot (UPI handle/name paid to)
    if recipient and not case.fraudster_info.get("upi_handle"):
        case.fraudster_info["upi_handle"] = recipient
        case.fraudster_info["name"] = recipient  # best available from txn
        case_manager.update_case(case.case_id, fraudster_info=case.fraudster_info)

    if not utr:
        message.reply(
            "I got your screenshot(s) but couldn't read the UTR number clearly. "
            "Could you paste it here? It's a 12-digit number on the transaction "
            "receipt (also called Transaction ID or Bank Ref No)."
        )
        return

    # Confirmed the transaction back to the user
    parts = []
    if amount:
        parts.append(f"Amount: **{amount}**")
    if recipient:
        parts.append(f"Paid to: **{recipient}**")
    parts.append(f"UTR: **{utr}**")
    if bank:
        parts.append(f"Bank: **{bank}**")
    reply = "✅ I've got the transaction details from your screenshot.\n\n" + "\n".join(parts)
    reply += (
        "\n\nThis is critical evidence for your recovery. I'll use it in the "
        "bank complaint and cyber crime report."
    )
    if case.amount_lost and case.transaction_id:
        reply += "\n\nType **status** to see your case, or tell me more about the scam."
    message.reply(reply)


# ── State handlers ────────────────────────────────────────────────────────

def _handle_triage_new_scam(client, message, case, engine, alerts, result):
    info = engine.extract_triage_info(message.text)
    case_manager.update_case(
        case.case_id,
        bank_name=info.get("bank_name"),
        transaction_id=info.get("transaction_id"),
        amount_lost=info.get("amount_lost"),
        scam_type=info.get("scam_type"),
        scam_summary=info.get("summary"),
    )
    # Capture the victim's identity if mentioned (for the complaint)
    if info.get("victim_name"):
        case.victim_info["name"] = info["victim_name"]
        if info.get("bank_name"):
            case.victim_info["bank"] = info["bank_name"]
        case_manager.update_case(case.case_id, victim_info=case.victim_info)
    message.reply(TRIAGE_INTRO)
    message.typing()


BANK_INFO_GATE_MESSAGE = """⚠️ I can't proceed with the complaints until I have **your bank account details** — the cyber cell and bank fraud desk both need to know *which account* was debited.

Please share **either**:
1. **Type it**: "My bank is HDFC, account ending 1234" (or full account number — I'll mask it), **or**
2. **Send a screenshot** of your bank statement / passbook / debit SMS showing the account

Without this, I **cannot file the complaint or send the bank email** — the recovery can't start. I'll remind you every 5 minutes until you provide it.

You can type **status** anytime to see where your case stands."""


def _has_victim_bank_info(case) -> bool:
    """Gate: recovery can't start until we know which bank/account was debited."""
    bank = case.victim_info.get("bank") or case.bank_name
    account = case.victim_info.get("account")
    return bool(bank and account)


def _handle_triage_info(client, message, case, engine, alerts, result):
    info = result.get("extracted_info", {})
    case_manager.update_case(case.case_id, **{k: v for k, v in info.items() if v})

    # Capture victim name from a reply (e.g. "My name is Rahul Verma")
    if info.get("victim_name"):
        case.victim_info["name"] = info["victim_name"]
        if info.get("bank_name") and not case.victim_info.get("bank"):
            case.victim_info["bank"] = info["bank_name"]
        case_manager.update_case(case.case_id, victim_info=case.victim_info)

    # BLOCKING GATE: if victim bank/account missing, do NOT proceed — ask + remind
    if not _has_victim_bank_info(case):
        # If the reply itself contained bank info, capture it
        if info.get("bank_name") and not case.victim_info.get("bank"):
            case.victim_info["bank"] = info["bank_name"]
            case_manager.update_case(case.case_id, victim_info=case.victim_info)
        # Ask for the account info we still need
        if not case.victim_info.get("account"):
            message.reply(BANK_INFO_GATE_MESSAGE)
            alerts.schedule_repeat_reminder(
                case.case_id,
                message=BANK_INFO_GATE_MESSAGE,
                interval_seconds=300,  # every 5 minutes
            )
            return

    # Check if we have enough to advance
    if case.bank_name and case.transaction_id and case.amount_lost:
        # Start parallel recovery actions
        _kick_off_recovery(client, case, engine, alerts)
    else:
        missing = []
        if not case.bank_name:
            missing.append("bank name")
        if not case.transaction_id:
            missing.append("transaction ID")
        if not case.amount_lost:
            missing.append("amount lost")
        message.reply(
            f"Got it. I still need: {', '.join(missing)}. "
            "The faster you share these, the faster I can fight back."
        )


def _handle_recovery_info(client, message, case, engine, alerts, result):
    message.reply(
        "I've noted that detail. Your recovery is in progress — "
        "I'll send you updates as each action completes. "
        'Type "status" anytime for a full timeline.'
    )


def _handle_status_check(client, message, case, engine, alerts, result):
    timeline = case_manager.get_timeline(case.case_id)
    message.reply(timeline)


def _handle_add_contact(client, message, case, engine, alerts, result):
    info = result.get("extracted_info", {})
    contact = info.get("contact")
    if contact:
        case.emergency_contacts.append(contact)
        case_manager.update_case(case.case_id, emergency_contacts=case.emergency_contacts)
        message.reply(
            f"✅ Added {contact} to your emergency contacts. "
            "They'll receive alerts if another incident occurs."
        )
    else:
        message.reply("I couldn't find a phone number in that. Send it like: +91 XXXXXXXXXX")


def _handle_confirm_action(client, message, case, engine, alerts, result):
    message.reply("✅ Action confirmed. I'll proceed and update your case timeline.")


def _handle_cyber_complaint_filed(client, message, case, engine, alerts, result):
    """User confirmed the reviewed draft → mark the cyber complaint as FILED.

    This is the review→confirm gate: the draft was sent for review, and only
    an explicit CONFIRM marks it as submitted. Stores a reference number.
    """
    reference = f"CYB-{case.case_id[:8].upper()}"
    case_manager.complete_action(
        case.case_id,
        "File cyber crime complaint at cybercrime.gov.in",
        f"Filed, ref {reference}",
    )
    case_manager.update_case(case.case_id, cyber_complaint_number=reference)
    message.reply(
        f"✅ Your cyber crime complaint is marked as **filed** at cybercrime.gov.in.\n\n"
        f"Reference: **{reference}**\n\n"
        f"Save this number — you'll need it for follow-ups. I'll track the investigation "
        f"and remind you to check the portal if there's no progress."
    )


def _complete_and_advance(case_id: str, action_name: str, result: str, next_state: CaseState) -> None:
    """Complete a pending action and advance the state machine.

    Extracted to avoid duplicating the complete+advance dance across the
    5 confirm handlers (DRY — used 5+ times).
    """
    case_manager.complete_action(case_id, action_name, result)
    case_manager.advance_state(case_id, next_state)


def _handle_bank_alert_confirm(client, message, case, engine, alerts, result):
    _complete_and_advance(
        case.case_id,
        "Forward bank complaint to fraud desk",
        "Forwarded by victim",
        CaseState.RECOVERY_TRACKING,
    )
    message.reply("✅ Bank complaint marked as forwarded. I'll track their response.")


def _handle_cyber_complaint_confirm(client, message, case, engine, alerts, result):
    reference = f"CYB-{case.case_id[:8].upper()}"
    case_manager.complete_action(
        case.case_id,
        "File cyber crime complaint at cybercrime.gov.in",
        f"Filed, ref {reference}",
    )
    case_manager.update_case(case.case_id, cyber_complaint_number=reference)
    case_manager.advance_state(case.case_id, CaseState.RECOVERY_TRACKING)
    message.reply(
        f"✅ Cyber complaint marked as filed. Reference: {reference} "
        "I'll track the investigation."
    )


def _handle_contact_alert_confirm(client, message, case, engine, alerts, result):
    _complete_and_advance(
        case.case_id,
        "Notify emergency contacts",
        "Contacts alerted",
        CaseState.RECOVERY_TRACKING,
    )
    message.reply("✅ Emergency contacts alerted. They've been warned about the scam.")


def _handle_credit_freeze_confirm(client, message, case, engine, alerts, result):
    _complete_and_advance(
        case.case_id,
        "Freeze CIBIL credit report",
        "Credit frozen",
        CaseState.RECOVERY_TRACKING,
    )
    message.reply("✅ Credit report frozen. Identity theft prevention is in place.")


def _handle_password_2fa_confirm(client, message, case, engine, alerts, result):
    _complete_and_advance(
        case.case_id,
        "Enable 2FA and change passwords",
        "Accounts hardened",
        CaseState.RECOVERY_TRACKING,
    )
    message.reply("✅ 2FA enabled and passwords changed. Your accounts are secure.")


def _handle_unknown(client, message, case, engine, alerts, result):
    if case.state == CaseState.TRIAGE:
        message.reply(TRIAGE_INTRO)
    else:
        message.reply(
            "I'm here to help with your recovery. You can:\n"
            '• Type "status" for your case timeline\n'
            "• Share any new details about the incident\n"
            "• Add emergency contacts\n\n"
            "What would you like to do?"
        )


# ── Internal helpers ──────────────────────────────────────────────────────

def _kick_off_recovery(client, case, engine, alerts):
    """Execute parallel recovery actions — drafts sent, not LLM tools."""
    date = _now_iso()

    # 1. Draft bank complaint (proposes draft, harness sends)
    bank_draft = engine.draft_bank_complaint(
        bank_name=case.bank_name or "your bank",
        transaction_id=case.transaction_id or "unknown",
        amount_lost=case.amount_lost or "unknown",
        scam_type=case.scam_type or "other",
        date=date,
    )
    alerts.send_proactive_message(
        case.case_id,
        f"📋 *Bank Fraud Complaint — Ready to Send*\n\n"
        f"Forward this to your bank's fraud desk"
        f"{f' (e.g., fraud@{case.bank_name.lower()}.com)' if case.bank_name else ''}:"
        f"\n\n---\n\n{bank_draft}\n\n---\n\n"
        f"Reply YES to confirm you've forwarded it, and I'll mark it complete."
    )
    case_manager.add_action(case.case_id, "Forward bank complaint to fraud desk", date)

    # 2. Draft cyber complaint (with ALL transactions + victim/fraudster info)
    txn_lines = []
    for i, t in enumerate(case.transactions, 1):
        txn_lines.append(
            f"{i}. Amount: {t.get('amount') or 'unknown'} | UTR: {t.get('utr') or 'unknown'} "
            f"| Paid to: {t.get('recipient') or 'unknown'} | Bank: {t.get('bank') or 'unknown'} "
            f"| Time: {t.get('timestamp') or 'unknown'}"
        )
    transactions_str = "\n".join(txn_lines) if txn_lines else "Not yet provided"
    victim_str = (
        f"Name: {case.victim_info.get('name', 'TBD')} | "
        f"Contact: {case.victim_contact} | "
        f"Bank: {case.bank_name or 'TBD'}"
    )
    fraudster_str = (
        f"UPI handle: {case.fraudster_info.get('upi_handle', 'Not known')} | "
        f"Name: {case.fraudster_info.get('name', 'Not known')}"
    )
    cyber_draft = engine.draft_cyber_complaint(
        victim_info=victim_str,
        fraudster_info=fraudster_str,
        transactions=transactions_str,
        scam_type=case.scam_type or "other",
        scam_summary=case.scam_summary or "Financial fraud reported by victim",
    )
    alerts.send_proactive_message(
        case.case_id,
        f"👮 *Cyber Crime Complaint — Draft Ready for Your Review*\n\n"
        f"Here's your complaint for cybercrime.gov.in. Please **review it carefully**:"
        f"\n\n---\n\n{cyber_draft}\n\n---\n\n"
        f"• Reply **CONFIRM** if it's correct and you've filed it at cybercrime.gov.in\n"
        f"• Reply with any **corrections** (e.g. 'my name is wrong') and I'll regenerate it\n\n"
        f"I will NOT mark it as filed until you confirm."
    )
    case_manager.add_action(case.case_id, "File cyber crime complaint at cybercrime.gov.in", date)

    # 3. Credit freeze guide
    credit_guide = engine.credit_freeze_guide()
    alerts.send_proactive_message(case.case_id, credit_guide)
    case_manager.add_action(case.case_id, "Freeze CIBIL credit report", date)

    # 4. Password/2FA guide
    password_guide = engine.password_2fa_guide()
    alerts.send_proactive_message(case.case_id, password_guide)
    case_manager.add_action(case.case_id, "Enable 2FA and change passwords", date)

    # 5. Advance to an intermediate state — RECOVERY_TRACKING only via
    #    confirm handlers (the state machine forbids a direct jump).
    case_manager.advance_state(case.case_id, CaseState.CREDIT_FREEZE)

    # 6. Schedule follow-ups (simulated — seconds instead of hours for demo)
    alerts.run_recovery_loop(case.case_id)


# ── State → {Intent → Handler} router ─────────────────────────────────────

_STATE_ROUTER: dict = {
    CaseState.TRIAGE: {
        "NEW_SCAM_REPORT": _handle_triage_new_scam,
        "INFO_RESPONSE": _handle_triage_info,
        "STATUS_CHECK": _handle_status_check,
        "ADD_CONTACT": _handle_add_contact,
    },
    CaseState.BANK_ALERT: {
        "CONFIRM_ACTION": _handle_bank_alert_confirm,
        "STATUS_CHECK": _handle_status_check,
    },
    CaseState.CYBER_COMPLAINT: {
        "CONFIRM_ACTION": _handle_cyber_complaint_confirm,
        "STATUS_CHECK": _handle_status_check,
    },
    CaseState.CONTACT_ALERT: {
        "ADD_CONTACT": _handle_add_contact,
        "CONFIRM_ACTION": _handle_contact_alert_confirm,
        "STATUS_CHECK": _handle_status_check,
    },
    CaseState.CREDIT_FREEZE: {
        "CONFIRM_ACTION": _handle_credit_freeze_confirm,
        "STATUS_CHECK": _handle_status_check,
    },
    CaseState.PASSWORD_2FA: {
        "CONFIRM_ACTION": _handle_password_2fa_confirm,
        "STATUS_CHECK": _handle_status_check,
    },
    CaseState.RECOVERY_TRACKING: {
        "INFO_RESPONSE": _handle_recovery_info,
        "STATUS_CHECK": _handle_status_check,
        "ADD_CONTACT": _handle_add_contact,
        "CONFIRM_ACTION": _handle_cyber_complaint_filed,
    },
}
