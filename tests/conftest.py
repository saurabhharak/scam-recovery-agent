"""Test doubles + fixtures for handler tests.

Written FIRST (TDD) — they define the contract handler.py must satisfy.
No production code is touched until these tests exist.

Fixtures are auto-discovered by pytest; tests receive them by parameter name.
"""

import pytest

from bodyguard.case_manager import case_manager


class FakeMessage:
    """Mimics the Caspian SDK Message object. Records replies for assertion."""

    def __init__(self, text: str, sender: str = "victim@example.com",
                 conversation_id: str = "conv_test_001"):
        self.text = text
        self.sender = {"address": sender}
        self.conversation_id = conversation_id
        self.replies: list[str] = []
        self.typing_calls = 0
        self.media: list[dict] = []

    def reply(self, content: str) -> None:
        self.replies.append(content)

    def typing(self) -> None:
        self.typing_calls += 1


class FakeAlerts:
    """Mimics AlertSystem. run_recovery_loop is a no-op — no threads in tests."""

    def __init__(self):
        self.sent: list[tuple[str, str]] = []

    def send_proactive_message(self, conversation_id: str, text: str) -> None:
        self.sent.append((conversation_id, text))

    def run_recovery_loop(self, case_id: str) -> None:
        pass


class FakeEngine:
    """Mimics RecoveryEngine. Returns canned results — no real LLM in tests."""

    def __init__(self, intent: str = "NEW_SCAM_REPORT", confidence: float = 0.95,
                 extracted: dict | None = None):
        self.intent_result = {
            "intent": intent,
            "confidence": confidence,
            "extracted_info": extracted or {},
        }
        self.vision_extract_result: dict = {}
        self.vision_extract_called = False
        self.last_media_url: str | None = None

    def classify_intent(self, message_text: str, case_state: str, case_summary: str) -> dict:
        return self.intent_result

    def extract_triage_info(self, message_text: str) -> dict:
        return {
            "bank_name": "HDFC",
            "transaction_id": "TXN123",
            "amount_lost": "₹50,000",
            "scam_type": "upi_fraud",
            "urgency": "high",
            "summary": "OTP scam",
        }

    def extract_from_screenshot(self, media_url: str) -> dict:
        """Vision extraction — returns canned result in tests."""
        self.vision_extract_called = True
        self.last_media_url = media_url
        if isinstance(self.vision_extract_result, list):
            return self.vision_extract_result[0] if self.vision_extract_result else {}
        return self.vision_extract_result

    def extract_from_screenshots(self, media_urls: list[str]) -> dict:
        """Merge per-image vision results (mimics the real engine)."""
        self.vision_extract_called = True
        if isinstance(self.vision_extract_result, list):
            merged: dict = {}
            for result in self.vision_extract_result:
                for key, value in result.items():
                    if value is not None and not merged.get(key):
                        merged[key] = value
            return merged
        return self.vision_extract_result

    def draft_bank_complaint(self, **kwargs) -> str:
        return "Dear HDFC Fraud Department, ..."

    def draft_cyber_complaint(self, **kwargs) -> str:
        return "Cyber crime complaint text ..."

    def draft_emergency_alert(self, **kwargs) -> str:
        return "⚠️ URGENT: accounts may be compromised."

    def credit_freeze_guide(self) -> str:
        return "1. Log into CIBIL. 2. Place a freeze."

    def password_2fa_guide(self) -> str:
        return "1. Enable 2FA. 2. Change passwords."


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def message_factory():
    """Factory fixture — returns a callable that builds FakeMessage."""
    return FakeMessage


@pytest.fixture
def alerts():
    return FakeAlerts()


@pytest.fixture
def engine():
    return FakeEngine()


@pytest.fixture
def engine_factory():
    """Factory fixture — returns a callable that builds FakeEngine with overrides."""
    return FakeEngine


@pytest.fixture(autouse=True)
def clean_case_manager():
    """Reset the module-level singleton before each test — no cross-test pollution."""
    case_manager._cases.clear()
    yield case_manager
    case_manager._cases.clear()
