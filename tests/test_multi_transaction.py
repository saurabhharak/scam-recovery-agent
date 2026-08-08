"""Tests for multi-transaction support + victim/fraudster info collection.

Cybercrime complaints require ALL transactions (not just one) plus the
victim's details and the fraudster's identifiers. These tests define the
contract for collecting and storing that structured data.
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle


# ── Multi-transaction storage ──────────────────────────────────────────────

def test_case_has_transactions_list(clean_case_manager):
    """A case can hold multiple transactions."""
    case = clean_case_manager.get_or_create("conv_mt_1", "victim@example.com")
    assert hasattr(case, "transactions")
    assert case.transactions == []


def test_add_transaction_via_vision(clean_case_manager, message_factory, alerts, engine_factory):
    """Each screenshot adds a NEW transaction to the list."""
    case = clean_case_manager.get_or_create("conv_mt_2", "victim@example.com")

    # First screenshot
    msg1 = message_factory("", conversation_id="conv_mt_2")
    msg1.media = [{"mime_type": "image/jpeg", "url": "https://example.com/txn1.jpg"}]
    eng1 = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    eng1.vision_extract_result = {
        "amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
        "bank": "HDFC", "timestamp": "09:12 am",
    }
    handle(None, msg1, eng1, alerts)

    # Second screenshot (another transaction)
    msg2 = message_factory("", conversation_id="conv_mt_2")
    msg2.media = [{"mime_type": "image/jpeg", "url": "https://example.com/txn2.jpg"}]
    eng2 = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    eng2.vision_extract_result = {
        "amount": "₹20,000", "utr": "323456789013", "recipient": "scammer@okhdfcbank",
        "bank": "HDFC", "timestamp": "09:30 am",
    }
    handle(None, msg2, eng2, alerts)

    case = clean_case_manager.get("conv_mt_2")
    assert len(case.transactions) == 2
    assert case.transactions[0]["utr"] == "323456789012"
    assert case.transactions[1]["utr"] == "323456789013"
    # Total amount = sum of all
    assert case.amount_lost == "₹70,000"


def test_duplicate_utr_not_added_twice(clean_case_manager, message_factory, alerts, engine_factory):
    """Same transaction screenshot sent twice should not duplicate."""
    case = clean_case_manager.get_or_create("conv_mt_3", "victim@example.com")

    for _ in range(2):
        msg = message_factory("", conversation_id="conv_mt_3")
        msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/txn.jpg"}]
        eng = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
        eng.vision_extract_result = {
            "amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
            "bank": "HDFC", "timestamp": "09:12 am",
        }
        handle(None, msg, eng, alerts)

    case = clean_case_manager.get("conv_mt_3")
    assert len(case.transactions) == 1  # deduped


# ── Victim info collection ─────────────────────────────────────────────────

def test_case_has_victim_info(clean_case_manager):
    """Case tracks victim's personal details for the complaint."""
    case = clean_case_manager.get_or_create("conv_vi_1", "victim@example.com")
    assert hasattr(case, "victim_info")
    assert case.victim_info == {}


def test_triage_asks_for_victim_info(clean_case_manager, message_factory, alerts, engine_factory):
    """After a scam report, the agent asks for the victim's details."""
    msg = message_factory("I got scammed on PhonePe", conversation_id="conv_vi_2")
    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)
    handle(None, msg, engine, alerts)
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    # Should ask for victim identity details needed for the complaint
    assert "name" in combined


# ── Fraudster info collection ──────────────────────────────────────────────

def test_case_has_fraudster_info(clean_case_manager):
    """Case tracks fraudster identifiers for the complaint."""
    case = clean_case_manager.get_or_create("conv_fi_1", "victim@example.com")
    assert hasattr(case, "fraudster_info")
    assert case.fraudster_info == {}


def test_vision_extraction_captures_fraudster_handle(clean_case_manager, message_factory, alerts, engine_factory):
    """The fraudster's UPI handle from the screenshot becomes fraudster_info."""
    case = clean_case_manager.get_or_create("conv_fi_2", "victim@example.com")
    msg = message_factory("", conversation_id="conv_fi_2")
    msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/txn.jpg"}]
    eng = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    eng.vision_extract_result = {
        "amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
        "bank": "HDFC", "timestamp": "09:12 am",
    }
    handle(None, msg, eng, alerts)
    case = clean_case_manager.get("conv_fi_2")
    assert case.fraudster_info.get("upi_handle") == "scammer@okhdfcbank"
    assert case.fraudster_info.get("name") == "scammer@okhdfcbank"


def test_timeline_shows_all_transactions(clean_case_manager):
    """get_timeline must list every transaction, not just one."""
    case = clean_case_manager.get_or_create("conv_mt_4", "victim@example.com")
    case.transactions = [
        {"amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank",
         "bank": "HDFC", "timestamp": "09:12 am"},
        {"amount": "₹20,000", "utr": "323456789013", "recipient": "scammer@okhdfcbank",
         "bank": "HDFC", "timestamp": "09:30 am"},
    ]
    timeline = clean_case_manager.get_timeline("conv_mt_4")
    assert "323456789012" in timeline
    assert "323456789013" in timeline
    assert "₹70,000" in timeline  # total
