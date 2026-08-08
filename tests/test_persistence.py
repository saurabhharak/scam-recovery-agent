"""Tests for SQLite persistence + blocking triage for victim bank info.

Requirements:
1. Cases survive agent restart (SQLite backend)
2. Triage BLOCKS until the victim provides bank + account info — user can
   type it OR send a screenshot; agent re-asks every 5 minutes until received
3. Multiple users are isolated; each conversation_id = one case
"""

import json
import os
import tempfile

import pytest

from bodyguard.case_manager import CaseState, Case, CaseManager, case_manager
from bodyguard.handler import handle, _handle_media


# ── Persistence ────────────────────────────────────────────────────────────

def test_save_and_load_case_roundtrip():
    """A case saved to SQLite loads back with all fields intact."""
    from bodyguard.store import Persistence

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    p = Persistence(db_path)

    case = Case(
        case_id="conv_p1",
        victim_contact="victim@example.com",
        state=CaseState.RECOVERY_TRACKING,
        bank_name="HDFC",
        transaction_id="323456789012",
        amount_lost="₹70,000",
        transactions=[
            {"amount": "₹50,000", "utr": "323456789012", "recipient": "s@hdfc", "bank": "HDFC", "timestamp": "09:12 am"},
            {"amount": "₹20,000", "utr": "323456789013", "recipient": "s@hdfc", "bank": "HDFC", "timestamp": "09:30 am"},
        ],
        victim_info={"name": "Saurabh Harak", "bank": "HDFC", "account": "XXXX1234"},
        fraudster_info={"upi_handle": "s@hdfc"},
    )
    p.save(case)

    loaded = p.load("conv_p1")
    assert loaded is not None
    assert loaded.case_id == "conv_p1"
    assert loaded.state == CaseState.RECOVERY_TRACKING
    assert loaded.amount_lost == "₹70,000"
    assert len(loaded.transactions) == 2
    assert loaded.transactions[0]["utr"] == "323456789012"
    assert loaded.victim_info["name"] == "Saurabh Harak"
    assert loaded.victim_info["account"] == "XXXX1234"
    assert loaded.fraudster_info["upi_handle"] == "s@hdfc"


def test_load_missing_case_returns_none():
    from bodyguard.store import Persistence

    tmp = tempfile.mkdtemp()
    p = Persistence(os.path.join(tmp, "test.db"))
    assert p.load("nonexistent") is None


def test_load_all_cases_returns_multiple():
    from bodyguard.store import Persistence

    tmp = tempfile.mkdtemp()
    p = Persistence(os.path.join(tmp, "test.db"))

    c1 = Case(case_id="conv_a", victim_contact="a@x.com")
    c2 = Case(case_id="conv_b", victim_contact="b@x.com", bank_name="SBI")
    p.save(c1)
    p.save(c2)

    all_cases = p.load_all()
    assert {c.case_id for c in all_cases} == {"conv_a", "conv_b"}
    assert next(c for c in all_cases if c.case_id == "conv_b").bank_name == "SBI"


def test_case_manager_reloads_from_store(clean_case_manager):
    """On startup, case_manager loads all persisted cases."""
    from bodyguard.store import Persistence
    import bodyguard.case_manager as cm

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test.db")
    p = Persistence(db_path)

    saved = Case(case_id="conv_r1", victim_contact="v@x.com", bank_name="HDFC")
    p.save(saved)

    mgr = CaseManager()
    mgr.load_all_from(p)
    case = mgr.get("conv_r1")
    assert case is not None
    assert case.bank_name == "HDFC"


# ── Blocking triage for victim bank info ───────────────────────────────────

def test_triage_blocks_when_bank_info_missing(clean_case_manager, message_factory, alerts, engine_factory):
    """Without victim bank/account, the agent must NOT proceed and must ask."""
    # First: report the scam (NEW_SCAM_REPORT) to create the case
    msg0 = message_factory("I got scammed on PhonePe", conversation_id="conv_blk_1")
    engine0 = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)
    handle(None, msg0, engine0, alerts)

    # Then: reply with transaction info but NO victim bank/account → gate blocks
    msg = message_factory("HDFC bank, TXN123, ₹50,000", conversation_id="conv_blk_1")
    engine = engine_factory(
        intent="INFO_RESPONSE",
        extracted={"bank_name": "HDFC", "transaction_id": "TXN123", "amount_lost": "₹50,000"},
    )

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_blk_1")
    # Still in TRIAGE — has not advanced to recovery
    assert case.state == CaseState.TRIAGE
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    # Must ask for bank/account, offer screenshot OR typing
    assert "bank" in combined
    assert "account" in combined


def test_triage_proceeds_once_bank_info_provided(clean_case_manager, message_factory, alerts, engine_factory):
    """Once victim provides bank + account, triage can proceed."""
    case = clean_case_manager.get_or_create("conv_blk_2", "victim@example.com")
    case.victim_info = {"name": "Saurabh", "bank": "HDFC", "account": "XXXX1234"}
    clean_case_manager.update_case("conv_blk_2", victim_info=case.victim_info)

    msg = message_factory("HDFC bank, TXN123, ₹50,000", conversation_id="conv_blk_2")
    engine = engine_factory(
        intent="INFO_RESPONSE",
        extracted={"bank_name": "HDFC", "transaction_id": "TXN123", "amount_lost": "₹50,000"},
    )

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_blk_2")
    # All info present → recovery kicks off, state advances past TRIAGE
    assert case.state != CaseState.TRIAGE


def test_bank_info_from_screenshot_unblocks(clean_case_manager, message_factory, alerts, engine_factory):
    """A screenshot showing the victim's bank also satisfies the gate."""
    msg = message_factory("", conversation_id="conv_blk_3")
    msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/bank_stmt.jpg"}]
    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    engine.vision_extract_result = {
        "amount": "₹50,000", "utr": "323456789012", "recipient": "s@hdfc",
        "bank": "HDFC", "timestamp": "09:12 am",
    }

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_blk_3")
    assert case.bank_name == "HDFC"


def test_missing_info_reply_mentions_reminder(clean_case_manager, message_factory, alerts, engine_factory):
    """When info is still missing, the reply tells the user the agent will
    remind them (5-min nudge) and that we can't proceed without it."""
    msg = message_factory("some bank info", conversation_id="conv_blk_4")
    engine = engine_factory(intent="INFO_RESPONSE", extracted={"bank_name": "HDFC"})

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_blk_4")
    assert case.state == CaseState.TRIAGE
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    assert "cannot proceed" in combined or "can't proceed" in combined or "can't" in combined


# ── Multi-user isolation ───────────────────────────────────────────────────

def test_multiple_users_isolated(clean_case_manager, message_factory, alerts, engine_factory):
    """Each conversation_id has its own independent case."""
    msg_a = message_factory("I got scammed", sender="alice@x.com", conversation_id="conv_u_a")
    engine_a = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)
    handle(None, msg_a, engine_a, alerts)

    msg_b = message_factory("Scammed too", sender="bob@x.com", conversation_id="conv_u_b")
    engine_b = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)
    handle(None, msg_b, engine_b, alerts)

    case_a = clean_case_manager.get("conv_u_a")
    case_b = clean_case_manager.get("conv_u_b")
    assert case_a is not case_b
    assert case_a.victim_contact == "alice@x.com"
    assert case_b.victim_contact == "bob@x.com"
    # Mutating one doesn't affect the other
    case_a.bank_name = "HDFC"
    assert case_b.bank_name is None
