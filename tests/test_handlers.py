"""Handler routing tests — written FIRST (TDD).

These tests define the contract handler.py must satisfy. They fail (RED) until
the 5 remaining state handlers are implemented.
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle


def _make_engine(intent: str, confidence: float = 0.95, extracted: dict | None = None):
    from tests.conftest import FakeEngine

    return FakeEngine(intent=intent, confidence=confidence, extracted=extracted)


# ── TRIAGE ────────────────────────────────────────────────────────────────

def test_triage_new_scam_extracts_and_replies(clean_case_manager, message_factory, alerts, engine_factory):
    msg = message_factory("I got scammed, someone took ₹50k from my HDFC account")
    engine = engine_factory()  # NEW_SCAM_REPORT default

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get(msg.conversation_id)
    assert case.state == CaseState.TRIAGE
    assert case.bank_name == "HDFC"
    assert case.amount_lost == "₹50,000"
    assert msg.replies  # intro replied
    assert msg.typing_calls == 1


def test_triage_info_complete_kicks_off_recovery(clean_case_manager, message_factory, alerts):
    msg = message_factory("HDFC bank, TXN123, ₹50,000")
    engine = _make_engine(
        "INFO_RESPONSE",
        extracted={"bank_name": "HDFC", "transaction_id": "TXN123", "amount_lost": "₹50,000"},
    )

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get(msg.conversation_id)
    # When all 3 fields present → recovery kicks off.
    # The state machine forbids TRIAGE → RECOVERY_TRACKING; it must pass
    # through an intermediate state (e.g. CREDIT_FREEZE) first.
    assert case.state in (
        CaseState.BANK_ALERT,
        CaseState.CYBER_COMPLAINT,
        CaseState.CONTACT_ALERT,
        CaseState.CREDIT_FREEZE,
        CaseState.PASSWORD_2FA,
    )
    assert alerts.sent  # proactive messages were sent
    assert len(case.pending_actions) >= 1


def test_triage_info_missing_fields_asks(clean_case_manager, message_factory, alerts):
    msg = message_factory("HDFC bank")
    engine = _make_engine("INFO_RESPONSE", extracted={"bank_name": "HDFC"})

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get(msg.conversation_id)
    assert case.state == CaseState.TRIAGE
    assert any("transaction ID" in r for r in msg.replies)
    assert any("amount" in r for r in msg.replies)


# ── BANK_ALERT ────────────────────────────────────────────────────────────

def test_bank_alert_confirm_forwards(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_bank", "victim@example.com")
    case.state = CaseState.BANK_ALERT
    clean_case_manager.add_action("conv_bank", "Forward bank complaint to fraud desk")

    msg = message_factory("Yes, I forwarded it", conversation_id="conv_bank")
    engine = _make_engine("CONFIRM_ACTION")

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_bank")
    assert any(
        a.action == "Forward bank complaint to fraud desk"
        for a in case.actions_completed
    )
    assert case.state == CaseState.RECOVERY_TRACKING


# ── CYBER_COMPLAINT ───────────────────────────────────────────────────────

def test_cyber_complaint_confirm_files(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_cyber", "victim@example.com")
    case.state = CaseState.CYBER_COMPLAINT
    clean_case_manager.add_action("conv_cyber", "File cyber crime complaint at cybercrime.gov.in")

    msg = message_factory("Yes, filed it", conversation_id="conv_cyber")
    engine = _make_engine("CONFIRM_ACTION")

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_cyber")
    assert any(
        a.action == "File cyber crime complaint at cybercrime.gov.in"
        for a in case.actions_completed
    )
    assert case.cyber_complaint_number  # reference number set
    assert case.state == CaseState.RECOVERY_TRACKING


# ── CONTACT_ALERT ─────────────────────────────────────────────────────────

def test_contact_alert_adds_contact(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_contact", "victim@example.com")
    case.state = CaseState.CONTACT_ALERT

    msg = message_factory("Alert my brother +91 98765 43210", conversation_id="conv_contact")
    engine = _make_engine("ADD_CONTACT", extracted={"contact": "+919876543210"})

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_contact")
    assert "+919876543210" in case.emergency_contacts


# ── CREDIT_FREEZE ─────────────────────────────────────────────────────────

def test_credit_freeze_confirm_completes(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_freeze", "victim@example.com")
    case.state = CaseState.CREDIT_FREEZE
    clean_case_manager.add_action("conv_freeze", "Freeze CIBIL credit report")

    msg = message_factory("Done, credit is frozen", conversation_id="conv_freeze")
    engine = _make_engine("CONFIRM_ACTION")

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_freeze")
    assert any(a.action == "Freeze CIBIL credit report" for a in case.actions_completed)
    assert case.state == CaseState.RECOVERY_TRACKING


# ── PASSWORD_2FA ──────────────────────────────────────────────────────────

def test_password_2fa_confirm_completes(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_2fa", "victim@example.com")
    case.state = CaseState.PASSWORD_2FA
    clean_case_manager.add_action("conv_2fa", "Enable 2FA and change passwords")

    msg = message_factory("Done, all changed", conversation_id="conv_2fa")
    engine = _make_engine("CONFIRM_ACTION")

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_2fa")
    assert any(a.action == "Enable 2FA and change passwords" for a in case.actions_completed)
    assert case.state == CaseState.RECOVERY_TRACKING


# ── STATUS / CONFIDENCE / UNKNOWN ─────────────────────────────────────────

def test_status_check_returns_timeline(clean_case_manager, message_factory, alerts):
    clean_case_manager.get_or_create("conv_status", "victim@example.com")
    clean_case_manager.add_action("conv_status", "Freeze credit")

    msg = message_factory("Any updates?", conversation_id="conv_status")
    engine = _make_engine("STATUS_CHECK")

    handle(None, msg, engine, alerts)

    assert msg.replies
    assert "Freeze credit" in msg.replies[0]  # timeline contains pending action


def test_low_confidence_asks_clarification(clean_case_manager, message_factory, alerts):
    clean_case_manager.get_or_create("conv_low", "victim@example.com")

    msg = message_factory("something unclear", conversation_id="conv_low")
    engine = _make_engine("INFO_RESPONSE", confidence=0.3)

    handle(None, msg, engine, alerts)

    assert msg.replies
    assert "tell me more" in msg.replies[0].lower()
    case = clean_case_manager.get("conv_low")
    assert case.state == CaseState.TRIAGE
    assert len(case.pending_actions) == 0


def test_unknown_intent_triage_replies_intro(clean_case_manager, message_factory, alerts):
    clean_case_manager.get_or_create("conv_unk", "victim@example.com")

    msg = message_factory("blah blah", conversation_id="conv_unk")
    engine = _make_engine("UNKNOWN", confidence=0.0)

    handle(None, msg, engine, alerts)

    assert msg.replies
    assert "Digital Bodyguard activated" in msg.replies[0]


def test_unknown_intent_recovery_offers_options(clean_case_manager, message_factory, alerts):
    case = clean_case_manager.get_or_create("conv_unk2", "victim@example.com")
    case.state = CaseState.RECOVERY_TRACKING

    msg = message_factory("blah blah", conversation_id="conv_unk2")
    engine = _make_engine("UNKNOWN", confidence=0.0)

    handle(None, msg, engine, alerts)

    assert msg.replies
    assert "status" in msg.replies[0].lower()
