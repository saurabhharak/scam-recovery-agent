"""Tests for screenshot (vision) extraction and media handling.

When a panicked user sends a UPI transaction screenshot, the agent must:
1. Detect the media attachment
2. Download it and extract transaction details via a vision model
3. Update the case with UTR, amount, recipient, bank, timestamp
4. Fail fast (ask for the UTR) if extraction is incomplete
"""

from bodyguard.case_manager import CaseState
from bodyguard.handler import handle
from bodyguard.recovery_engine import parse_json_response


# ── Vision JSON parsing ────────────────────────────────────────────────────

def test_parse_json_handles_vision_output_with_fences():
    """Vision models often wrap JSON in markdown fences — parser must handle."""
    raw = '```json\n{"amount": "₹5,000", "utr": "661178921771", "recipient": "Swapnil 555 Harak", "bank": "AXIS BANK", "timestamp": "08:42 pm on 02 Aug 2026"}\n```'
    parsed = parse_json_response(raw)
    assert parsed.get("utr") == "661178921771"
    assert parsed.get("amount") == "₹5,000"


def test_parse_json_handles_vision_output_with_prose():
    """Vision models sometimes add prose around the JSON."""
    raw = 'Here is the extracted data: {"amount": "5000", "utr": "661178921771"} thanks!'
    parsed = parse_json_response(raw)
    assert parsed.get("utr") == "661178921771"


# ── Media message routing ──────────────────────────────────────────────────

def test_image_message_routes_to_vision_extraction(clean_case_manager, message_factory, alerts, engine_factory):
    """A message with a media attachment should trigger vision extraction."""
    msg = message_factory("", conversation_id="conv_shot_1")
    msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/shot.jpg"}]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    # Simulate successful vision extraction
    engine.vision_extract_result = {
        "amount": "₹5,000", "utr": "661178921771", "recipient": "Swapnil 555 Harak",
        "bank": "AXIS BANK", "timestamp": "08:42 pm on 02 Aug 2026",
    }

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_shot_1")
    assert case.transaction_id == "661178921771"
    assert case.amount_lost == "₹5,000"
    assert case.bank_name == "AXIS BANK"
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    assert "661178921771" in combined  # confirms the UTR back to the user


def test_image_message_with_missing_utr_asks_user(clean_case_manager, message_factory, alerts, engine_factory):
    """If vision extraction fails to find a UTR, ask the user for it (fail fast)."""
    msg = message_factory("", conversation_id="conv_shot_2")
    msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/blurry.jpg"}]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    engine.vision_extract_result = {
        "amount": "₹5,000", "utr": None, "recipient": "Swapnil", "bank": None, "timestamp": None,
    }

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_shot_2")
    assert case.transaction_id is None
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    assert "utr" in combined  # asks for the UTR


def test_text_message_with_phonepe_text_and_media_still_works(clean_case_manager, message_factory, alerts, engine_factory):
    """PhonePe sends marketing text + screenshot. Vision must take priority."""
    msg = message_factory(
        "Paid using PhonePe UPI.\nExplore the app now: https://phon.pe/download2025",
        conversation_id="conv_shot_3",
    )
    msg.media = [{"mime_type": "image/jpeg", "url": "https://example.com/phonepay.jpg"}]

    engine = engine_factory(intent="UNKNOWN", confidence=0.0)  # text is marketing, not intent
    engine.vision_extract_result = {
        "amount": "₹1", "utr": "324117570295", "recipient": "Kitchens@", "bank": None, "timestamp": None,
    }

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_shot_3")
    assert case.transaction_id == "324117570295"
    assert case.amount_lost == "₹1"


def test_no_media_uses_text_flow(clean_case_manager, message_factory, alerts, engine_factory):
    """Without media, the normal text intent flow runs (no vision call)."""
    msg = message_factory("Help! I got scammed on PhonePe", conversation_id="conv_text_1")

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.95)

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_text_1")
    assert case.state == CaseState.TRIAGE
    assert not engine.vision_extract_called


# ── Media URL normalization ────────────────────────────────────────────────

def test_media_url_missing_slash_is_normalized(clean_case_manager, message_factory, alerts, engine_factory):
    """The Caspian gateway emits media URLs with a missing slash:
    'https://api.telegram.orgfile/bot...' instead of
    'https://api.telegram.org/file/bot...'. The handler must normalize it
    so the vision model can fetch the image.
    """
    from bodyguard.handler import _normalize_media_url

    malformed = "https://api.telegram.orgfile/bot123:ABC/photos/file_0.jpg"
    fixed = _normalize_media_url(malformed)
    assert fixed == "https://api.telegram.org/file/bot123:ABC/photos/file_0.jpg"


def test_media_url_already_correct_unchanged():
    from bodyguard.handler import _normalize_media_url

    good = "https://api.telegram.org/file/bot123:ABC/photos/file_0.jpg"
    assert _normalize_media_url(good) == good


def test_image_message_uses_normalized_url(clean_case_manager, message_factory, alerts, engine_factory):
    """The vision extraction must receive the corrected URL."""
    msg = message_factory("", conversation_id="conv_url_1")
    msg.media = [{"mime_type": "image/jpeg",
                  "url": "https://api.telegram.orgfile/bot123:ABC/photos/file_0.jpg"}]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    engine.vision_extract_result = {
        "amount": "₹5,000", "utr": "661178921771", "recipient": "Swapnil", "bank": "AXIS", "timestamp": None,
    }

    handle(None, msg, engine, alerts)

    # The engine was called with the corrected URL
    assert engine.last_media_url == "https://api.telegram.org/file/bot123:ABC/photos/file_0.jpg"
    case = clean_case_manager.get("conv_url_1")
    assert case.transaction_id == "661178921771"


# ── Multiple screenshots ───────────────────────────────────────────────────

def test_multiple_screenshots_merge_results(clean_case_manager, message_factory, alerts, engine_factory):
    """User sends 2+ screenshots — agent must merge partial info from each.

    Screenshot 1: amount + recipient (PhonePe receipt)
    Screenshot 2: UTR + bank (bank SMS)
    Merged: complete case data.
    """
    msg = message_factory("", conversation_id="conv_multi_1")
    msg.media = [
        {"mime_type": "image/jpeg", "url": "https://example.com/receipt.jpg"},
        {"mime_type": "image/jpeg", "url": "https://example.com/sms.jpg"},
    ]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    # Vision returns per-image results (list) — engine merges them
    engine.vision_extract_result = [
        {"amount": "₹5,000", "utr": None, "recipient": "Swapnil 555 Harak", "bank": None, "timestamp": None},
        {"amount": None, "utr": "661178921771", "recipient": None, "bank": "AXIS BANK", "timestamp": "08:42 pm on 02 Aug 2026"},
    ]

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_multi_1")
    # Merged from both screenshots
    assert case.transaction_id == "661178921771"
    assert case.amount_lost == "₹5,000"
    assert case.bank_name == "AXIS BANK"
    assert case.recipient == "Swapnil 555 Harak" if hasattr(case, "recipient") else True


def test_multiple_screenshots_one_incomplete_merges_rest(clean_case_manager, message_factory, alerts, engine_factory):
    """If one screenshot is blurry/useless, the others still provide data."""
    msg = message_factory("", conversation_id="conv_multi_2")
    msg.media = [
        {"mime_type": "image/jpeg", "url": "https://example.com/blurry.jpg"},
        {"mime_type": "image/jpeg", "url": "https://example.com/utr.jpg"},
    ]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    engine.vision_extract_result = [
        {},  # blurry — nothing extracted
        {"amount": "₹50,000", "utr": "323456789012", "recipient": "scammer@okhdfcbank", "bank": "HDFC", "timestamp": "09:12 am"},
    ]

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_multi_2")
    assert case.transaction_id == "323456789012"
    assert case.amount_lost == "₹50,000"
    assert case.bank_name == "HDFC"


def test_multiple_screenshots_asks_for_missing_utr(clean_case_manager, message_factory, alerts, engine_factory):
    """Even after merging, if UTR is still missing, ask the user for it."""
    msg = message_factory("", conversation_id="conv_multi_3")
    msg.media = [
        {"mime_type": "image/jpeg", "url": "https://example.com/1.jpg"},
        {"mime_type": "image/jpeg", "url": "https://example.com/2.jpg"},
    ]

    engine = engine_factory(intent="NEW_SCAM_REPORT", confidence=0.9)
    engine.vision_extract_result = [
        {"amount": "₹5,000", "utr": None, "recipient": "Swapnil", "bank": None, "timestamp": None},
        {"amount": None, "utr": None, "recipient": None, "bank": "AXIS", "timestamp": None},
    ]

    handle(None, msg, engine, alerts)

    case = clean_case_manager.get("conv_multi_3")
    assert case.transaction_id is None  # still missing
    assert msg.replies
    combined = " ".join(msg.replies).lower()
    assert "utr" in combined  # asks for it
