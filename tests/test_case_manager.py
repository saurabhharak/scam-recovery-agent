"""Tests for the case state machine."""

import pytest
from bodyguard.case_manager import CaseManager, CaseState


def test_create_case_in_triage():
    mgr = CaseManager()
    case = mgr.get_or_create("conv_001", "victim@email.com")
    assert case.state == CaseState.TRIAGE
    assert case.case_id == "conv_001"
    assert case.victim_contact == "victim@email.com"


def test_valid_transition_triage_to_bank_alert():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.advance_state("conv_001", CaseState.BANK_ALERT)
    assert mgr.get("conv_001").state == CaseState.BANK_ALERT


def test_valid_transition_triage_to_recovery_tracking():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.advance_state("conv_001", CaseState.CREDIT_FREEZE)
    mgr.advance_state("conv_001", CaseState.RECOVERY_TRACKING)
    assert mgr.get("conv_001").state == CaseState.RECOVERY_TRACKING


def test_invalid_transition_triage_to_resolved():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    with pytest.raises(ValueError, match="Invalid state transition"):
        mgr.advance_state("conv_001", CaseState.RESOLVED)


def test_invalid_transition_resolved_to_anything():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    # Go through the full flow to RESOLVED
    mgr.advance_state("conv_001", CaseState.CREDIT_FREEZE)
    mgr.advance_state("conv_001", CaseState.RECOVERY_TRACKING)
    mgr.advance_state("conv_001", CaseState.RESOLVED)
    with pytest.raises(ValueError, match="Invalid state transition"):
        mgr.advance_state("conv_001", CaseState.TRIAGE)


def test_add_and_complete_actions():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.add_action("conv_001", "File cyber complaint")
    mgr.complete_action("conv_001", "File cyber complaint", "Case #CYB-001")
    case = mgr.get("conv_001")
    assert len(case.actions_completed) == 1
    assert len(case.pending_actions) == 0
    assert case.actions_completed[0].result == "Case #CYB-001"


def test_update_case_fields():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.update_case(
        "conv_001",
        bank_name="HDFC",
        transaction_id="TXN123456",
        amount_lost="₹50,000",
    )
    case = mgr.get("conv_001")
    assert case.bank_name == "HDFC"
    assert case.transaction_id == "TXN123456"
    assert case.amount_lost == "₹50,000"


def test_get_timeline_includes_completed_and_pending():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.add_action("conv_001", "Freeze credit")
    mgr.add_action("conv_001", "Change passwords")
    mgr.complete_action("conv_001", "Freeze credit", "Done")
    timeline = mgr.get_timeline("conv_001")
    assert "✅ Freeze credit" in timeline
    assert "⏳ Change passwords" in timeline


def test_get_summary_for_llm_returns_json():
    mgr = CaseManager()
    mgr.get_or_create("conv_001", "victim@email.com")
    mgr.update_case(
        "conv_001",
        bank_name="SBI",
        amount_lost="₹10,000",
        scam_type="phishing",
    )
    summary = mgr.get_summary_for_llm("conv_001")
    assert '"bank": "SBI"' in summary
    assert '"amount": "₹10,000"' in summary
    assert '"scam_type": "phishing"' in summary


def test_case_idempotent_get_or_create():
    mgr = CaseManager()
    case1 = mgr.get_or_create("conv_001", "victim@email.com")
    case2 = mgr.get_or_create("conv_001", "different@email.com")
    assert case1 is case2
    assert case1.victim_contact == "victim@email.com"
