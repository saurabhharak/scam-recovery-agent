"""LLM-driven content generation.

The LLM proposes drafts — it NEVER sends anything. That's the harness's job.
This module has zero channel awareness and zero knowledge of sending mechanisms.
"""

import json
import time
from typing import Any

from openai import OpenAI

from bodyguard.config import get_config
from bodyguard.prompts import (
    BANK_COMPLAINT_PROMPT,
    CLASSIFY_INTENT_PROMPT,
    CREDIT_FREEZE_GUIDE,
    CYBER_COMPLAINT_PROMPT,
    EMERGENCY_ALERT_PROMPT,
    FOLLOW_UP_EMAIL_PROMPT,
    PASSWORD_2FA_GUIDE,
    RESOLUTION_SUMMARY_PROMPT,
    STATUS_UPDATE_PROMPT,
    SYSTEM_PROMPT,
    TRIAGE_PROMPT,
)


class RecoveryEngine:
    """Generates drafts via LLM. Injected with an LLM client — no hardcoded provider."""

    def __init__(self, llm_client: OpenAI):
        self.llm = llm_client
        self.model = get_config().llm_model

    def _generate(self, system: str, user: str, timeout: float = 15.0) -> str:
        """Generate text with timeout and fallback."""
        try:
            response = self.llm.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=0.7,
                max_tokens=800,
                timeout=timeout,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception as e:
            print(f"[RECOVERY_ENGINE] LLM call failed: {e}")
            return ""

    def classify_intent(
        self, message_text: str, case_state: str, case_summary: str
    ) -> dict[str, Any]:
        prompt = CLASSIFY_INTENT_PROMPT.format(
            case_state=case_state,
            case_summary=case_summary,
            message_text=message_text,
        )
        result = self._generate(SYSTEM_PROMPT, prompt, timeout=10.0)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"intent": "UNKNOWN", "confidence": 0.0, "extracted_info": {}}

    def extract_triage_info(self, message_text: str) -> dict[str, Any]:
        prompt = TRIAGE_PROMPT.format(message_text=message_text)
        result = self._generate(SYSTEM_PROMPT, prompt, timeout=10.0)
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {
                "bank_name": None,
                "transaction_id": None,
                "amount_lost": None,
                "scam_type": "other",
                "urgency": "high",
                "summary": "Unknown incident",
            }

    def draft_bank_complaint(
        self, *, bank_name: str, transaction_id: str, amount_lost: str,
        scam_type: str, date: str
    ) -> str:
        prompt = BANK_COMPLAINT_PROMPT.format(
            bank_name=bank_name,
            transaction_id=transaction_id,
            amount_lost=amount_lost,
            scam_type=scam_type,
            date=date,
        )
        return self._generate(SYSTEM_PROMPT, prompt)

    def draft_cyber_complaint(
        self, *, bank_name: str, transaction_id: str, amount_lost: str,
        scam_type: str, date: str
    ) -> str:
        prompt = CYBER_COMPLAINT_PROMPT.format(
            bank_name=bank_name,
            transaction_id=transaction_id,
            amount_lost=amount_lost,
            scam_type=scam_type,
            date=date,
        )
        return self._generate(SYSTEM_PROMPT, prompt)

    def draft_emergency_alert(
        self, *, victim_name: str, scam_summary: str
    ) -> str:
        prompt = EMERGENCY_ALERT_PROMPT.format(
            victim_name=victim_name, scam_summary=scam_summary
        )
        return self._generate(SYSTEM_PROMPT, prompt)

    def draft_status_update(
        self, *, case_state: str, actions_completed: str,
        pending_actions: str, days_elapsed: float
    ) -> str:
        prompt = STATUS_UPDATE_PROMPT.format(
            case_state=case_state,
            actions_completed=actions_completed,
            pending_actions=pending_actions,
            days_elapsed=days_elapsed,
        )
        return self._generate(SYSTEM_PROMPT, prompt)

    def credit_freeze_guide(self) -> str:
        return self._generate(SYSTEM_PROMPT, CREDIT_FREEZE_GUIDE)

    def password_2fa_guide(self) -> str:
        return self._generate(SYSTEM_PROMPT, PASSWORD_2FA_GUIDE)

    def draft_follow_up(
        self, *, bank_name: str, transaction_id: str, amount_lost: str,
        complaint_date: str, hours_elapsed: int
    ) -> str:
        prompt = FOLLOW_UP_EMAIL_PROMPT.format(
            bank_name=bank_name,
            transaction_id=transaction_id,
            amount_lost=amount_lost,
            complaint_date=complaint_date,
            hours_elapsed=hours_elapsed,
        )
        return self._generate(SYSTEM_PROMPT, prompt)

    def draft_resolution_summary(
        self, *, duration: str, amount_lost: str, amount_recovered: str,
        actions_completed: str, resolution_outcome: str
    ) -> str:
        prompt = RESOLUTION_SUMMARY_PROMPT.format(
            duration=duration,
            amount_lost=amount_lost,
            amount_recovered=amount_recovered,
            actions_completed=actions_completed,
            resolution_outcome=resolution_outcome,
        )
        return self._generate(SYSTEM_PROMPT, prompt)
