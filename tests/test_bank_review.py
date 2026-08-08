"""Tests for the bank complaint draft review → confirm → forwarded flow.

Like the cyber complaint, the bank complaint must NOT be marked as forwarded
until the user reviews the draft AND explicitly confirms. On confirm, a
reference is stored and the case advances.
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle, _kick_off_recovery


def _set_up_bank_case(clean_case_manager, case_id="conv_bank_rv_1"):
    case = clean_case_manager.get_or_create(case_id, "victim@example.com")
    case.victim_info = {"name": "Saurabh Harak", "bank": "HDFC", "account": "XXXX1234"}
    case.fraudster_info = {"upi_handle": "scammer@okhdfcbank"}
    case.bank_name = "HDFC"
    case.transactions = [
        {"amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
         "bank": "HDFC", "timestamp": "09:12 am"},
    ]
    case.scam_type = "upi_fraud"
    case.scam_summary = "OTP scam"
    clean_case_manager.update_case(case_id, victim_info=case.victim_info,
                                   fraudster_info=case.fraudster_info,
                                   transactions=case.transactions,
                                   bank_name=case.bank_name)
    return case


def test_bank_draft_sent_for_review_but_not_marked_forwarded(clean_case_manager, alerts, engine_factory):
    """Bank draft is sent for review — the action stays pending until confirm."""
    case = _set_up_bank_case(clean_case_manager)
    engine = engine_factory()

    _kick_off_recovery(None, case, engine, alerts)

    pending = [a.action for a in case.pending_actions]
    assert "Forward bank complaint to fraud desk" in pending
    completed = [a.action for a in case.actions_completed]
    assert "Forward bank complaint to fraud desk" not in completed
    # Review/confirm instruction sent
    assert any("review" in t.lower() or "confirm" in t.lower() for _, t in alerts.sent)


def test_kick_off_lands_in_bank_alert_state(clean_case_manager, alerts, engine_factory):
    """After kick-off, the case is in BANK_ALERT — so the bank confirm is reachable."""
    case = _set_up_bank_case(clean_case_manager)
    engine = engine_factory()

    _kick_off_recovery(None, case, engine, alerts)

    assert case.state == CaseState.BANK_ALERT


def test_bank_confirm_marks_forwarded_and_stores_reference(clean_case_manager, message_factory, alerts, engine_factory):
    """Explicit CONFIRM marks the bank complaint forwarded and stores a reference."""
    case = _set_up_bank_case(clean_case_manager, case_id="conv_bank_rv_2")
    case.state = CaseState.BANK_ALERT
    clean_case_manager.update_case(case.case_id, state=case.state)
    clean_case_manager.add_action(case.case_id, "Forward bank complaint to fraud desk")

    msg = message_factory("Confirmed, I've forwarded it", conversation_id="conv_bank_rv_2")
    engine = engine_factory(intent="CONFIRM_ACTION", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_bank_rv_2")
    completed = [a.action for a in case.actions_completed]
    assert "Forward bank complaint to fraud desk" in completed
    pending = [a.action for a in case.pending_actions]
    assert "Forward bank complaint to fraud desk" not in pending
    # A bank reference/FIR number is stored
    assert case.bank_fir_number
    assert msg.replies
    assert any("forwarded" in r.lower() for r in msg.replies)


def test_bank_confirm_advances_state(clean_case_manager, message_factory, alerts, engine_factory):
    """Confirming the bank complaint advances the case to RECOVERY_TRACKING."""
    case = _set_up_bank_case(clean_case_manager, case_id="conv_bank_rv_3")
    case.state = CaseState.BANK_ALERT
    clean_case_manager.update_case(case.case_id, state=case.state)
    clean_case_manager.add_action(case.case_id, "Forward bank complaint to fraud desk")

    msg = message_factory("Yes done", conversation_id="conv_bank_rv_3")
    engine = engine_factory(intent="CONFIRM_ACTION", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_bank_rv_3")
    assert case.state == CaseState.RECOVERY_TRACKING


def test_bank_corrections_keep_pending(clean_case_manager, message_factory, alerts, engine_factory):
    """User requesting changes keeps the bank complaint pending — not forwarded."""
    case = _set_up_bank_case(clean_case_manager, case_id="conv_bank_rv_4")
    case.state = CaseState.BANK_ALERT
    clean_case_manager.update_case(case.case_id, state=case.state)
    clean_case_manager.add_action(case.case_id, "Forward bank complaint to fraud desk")

    msg = message_factory("Change the transaction ID, it's wrong", conversation_id="conv_bank_rv_4")
    engine = engine_factory(intent="INFO_RESPONSE", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_bank_rv_4")
    pending = [a.action for a in case.pending_actions]
    assert "Forward bank complaint to fraud desk" in pending
    completed = [a.action for a in case.actions_completed]
    assert "Forward bank complaint to fraud desk" not in completed
