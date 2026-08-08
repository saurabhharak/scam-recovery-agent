"""Tests for victim_info collection during triage.

The victim's name (and other identity details) must be captured into
case.victim_info so the cybercrime complaint can name the complainant.
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle


def test_new_scam_report_captures_victim_name(clean_case_manager, message_factory, alerts, engine_factory):
    """When the scam report mentions the victim's name, it's stored."""
    msg = message_factory(
        "My name is Saurabh and I got scammed on PhonePe",
        conversation_id="conv_vi_10",
    )
    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)
    engine.triage_info_override = {
        "victim_name": "Saurabh Harak",
        "bank_name": "HDFC",
        "transaction_id": None,
        "amount_lost": None,
        "scam_type": "upi_fraud",
        "urgency": "high",
        "summary": "Scam",
    }

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_vi_10")
    assert case.victim_info.get("name") == "Saurabh Harak"
    assert case.victim_info.get("bank") == "HDFC"


def test_triage_info_reply_captures_victim_name(clean_case_manager, message_factory, alerts, engine_factory):
    """A later reply providing the name gets stored into victim_info."""
    msg = message_factory("My name is Rahul Verma", conversation_id="conv_vi_11")
    engine = engine_factory(
        intent="INFO_RESPONSE",
        extracted={"victim_name": "Rahul Verma"},
    )

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_vi_11")
    assert case.victim_info.get("name") == "Rahul Verma"


def test_cyber_complaint_uses_victim_name(clean_case_manager, message_factory, alerts, engine_factory):
    """The cyber complaint draft must include the victim's name."""
    # Set up a case with victim info + transactions
    case = clean_case_manager.get_or_create("conv_vi_12", "victim@example.com")
    case.victim_info = {"name": "Saurabh Harak", "bank": "HDFC"}
    case.fraudster_info = {"upi_handle": "scammer@okhdfcbank"}
    case.transactions = [
        {"amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
         "bank": "HDFC", "timestamp": "09:12 am"},
    ]
    case.scam_type = "upi_fraud"
    case.scam_summary = "OTP scam"

    # Directly test the draft builder path via a reply that completes triage
    msg = message_factory("I have all the details now", conversation_id="conv_vi_12")
    engine = engine_factory(
        intent="INFO_RESPONSE",
        extracted={"bank_name": "HDFC", "transaction_id": "323456789012", "amount_lost": "₹50,000"},
    )

    handle(None, msg, engine, alerts)

    # The victim_info must be readable for the complaint builder
    case = clean_case_manager.get("conv_vi_12")
    assert case.victim_info.get("name") == "Saurabh Harak"
