"""Tests for the draft review → confirm → submit flow.

The cyber crime complaint must NOT be treated as "filed" until the user
reviews the draft AND explicitly confirms. Only then does the case mark it
as submitted (and store the reference).
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle, _kick_off_recovery


def _set_up_review_case(clean_case_manager, case_id="conv_rv_1"):
    """A case with victim info, fraudster info, and transactions — ready for the draft."""
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


def test_draft_sent_for_review_but_not_marked_filed(clean_case_manager, alerts, engine_factory):
    """After the draft is generated, it's pending review — NOT yet marked as filed."""
    case = _set_up_review_case(clean_case_manager)
    engine = engine_factory()

    _kick_off_recovery(None, case, engine, alerts)

    # The cyber complaint action should be PENDING (awaiting review/confirm)
    pending = [a.action for a in case.pending_actions]
    assert "File cyber crime complaint at cybercrime.gov.in" in pending
    # Not in completed yet — user hasn't confirmed
    completed = [a.action for a in case.actions_completed]
    assert "File cyber crime complaint at cybercrime.gov.in" not in completed
    # A review request message was sent
    assert any("review" in t.lower() or "confirm" in t.lower() for _, t in alerts.sent)


def test_user_can_request_changes_before_confirm(clean_case_manager, message_factory, alerts, engine_factory):
    """If the user says 'change X', the draft stays pending — not filed."""
    case = _set_up_review_case(clean_case_manager)
    case.state = CaseState.RECOVERY_TRACKING
    clean_case_manager.update_case(case.case_id, state=case.state)  # set state directly
    clean_case_manager.add_action(case.case_id, "File cyber crime complaint at cybercrime.gov.in")

    msg = message_factory("Please correct my name, it's Saurabh Verma not Harak",
                          conversation_id="conv_rv_1")
    engine = engine_factory(intent="INFO_RESPONSE", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_rv_1")
    # Still pending — NOT completed
    pending = [a.action for a in case.pending_actions]
    assert "File cyber crime complaint at cybercrime.gov.in" in pending
    completed = [a.action for a in case.actions_completed]
    assert "File cyber crime complaint at cybercrime.gov.in" not in completed


def test_confirm_marks_cyber_complaint_filed(clean_case_manager, message_factory, alerts, engine_factory):
    """Only an explicit CONFIRM_ACTION marks the cyber complaint as filed."""
    case = _set_up_review_case(clean_case_manager)
    clean_case_manager.add_action(case.case_id, "File cyber crime complaint at cybercrime.gov.in")
    case.state = CaseState.RECOVERY_TRACKING

    msg = message_factory("Yes, I confirm it's correct and I've filed it",
                          conversation_id="conv_rv_1")
    engine = engine_factory(intent="CONFIRM_ACTION", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_rv_1")
    completed = [a.action for a in case.actions_completed]
    assert "File cyber crime complaint at cybercrime.gov.in" in completed
    pending = [a.action for a in case.pending_actions]
    assert "File cyber crime complaint at cybercrime.gov.in" not in pending
    # Reference number is stored
    assert case.cyber_complaint_number


def test_cyber_complaint_number_stored_on_confirm(clean_case_manager, message_factory, alerts, engine_factory):
    """On confirm, the agent stores a reference number and confirms to the user."""
    case = _set_up_review_case(clean_case_manager, case_id="conv_rv_2")
    clean_case_manager.add_action(case.case_id, "File cyber crime complaint at cybercrime.gov.in")
    case.state = CaseState.RECOVERY_TRACKING

    msg = message_factory("Confirmed", conversation_id="conv_rv_2")
    engine = engine_factory(intent="CONFIRM_ACTION", extracted={})
    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_rv_2")
    assert case.cyber_complaint_number  # e.g. CYB-...
    assert msg.replies
    assert any("filed" in r.lower() for r in msg.replies)
