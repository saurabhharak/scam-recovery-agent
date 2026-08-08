"""Proactive alerts and follow-up scheduler.

This is the ONLY module (besides handler.py) that touches channels.
It wraps client.send_message() with logging and error handling — no other
module calls client.send_message() directly (DRY).
"""

import threading
import time
from datetime import datetime, timezone

from caspian_sdk import CommClient

from bodyguard.case_manager import Case, case_manager


class AlertSystem:
    """Proactive message sender. The harness executes; the LLM never calls send directly."""

    def __init__(self, client: CommClient):
        self.client = client
        self._timers: dict[str, threading.Timer] = {}

    def notify_emergency_contacts(
        self, case: Case, message: str, contact_list: list[str]
    ) -> None:
        """Send emergency alerts to all contacts on their preferred channels."""
        for contact in contact_list:
            try:
                self.client.send_message(
                    conversation_id=case.case_id,
                    text=f"⚠️ URGENT: {message}",
                )
                _log_send(case.case_id, "EMERGENCY_ALERT", contact)
            except Exception as e:
                print(f"[ALERT_SYSTEM] Failed to alert {contact}: {e}")

    def send_proactive_message(
        self, conversation_id: str, text: str
    ) -> None:
        """Send a proactive message to a case thread."""
        try:
            self.client.send_message(
                conversation_id=conversation_id,
                text=text,
            )
            _log_send(conversation_id, "PROACTIVE", text[:80])
        except Exception as e:
            print(f"[ALERT_SYSTEM] Failed to send message to {conversation_id}: {e}")

    def schedule_follow_up(
        self, case_id: str, hours: int, message: str
    ) -> None:
        """Schedule a follow-up message N hours from now.

        For the demo, hours can be small (e.g., a few seconds) to simulate
        time passing quickly. In production, this would use a proper scheduler.
        """
        seconds = hours * 3600  # hours → seconds (use small values for demo)
        timer = threading.Timer(seconds, self._deliver_follow_up, args=[case_id, message])
        timer.daemon = True
        timer.start()
        self._timers[case_id] = timer
        _log_send(case_id, "SCHEDULED", f"Follow-up in {hours}h")

    def _deliver_follow_up(self, case_id: str, message: str) -> None:
        """Deliver a scheduled follow-up to the case thread."""
        case = case_manager.get(case_id)
        if case and case.state.value != "RESOLVED":
            self.send_proactive_message(case_id, message)
            self._timers.pop(case_id, None)

    def run_recovery_loop(self, case_id: str) -> None:
        """Simulate the recovery tracking loop for the demo.

        Sends status updates and escalations at fixed intervals. In production,
        this would be a background job with actual time-based scheduling.
        """
        def _loop():
            time.sleep(10)  # Day 1 update (10 seconds for demo)
            case = case_manager.get(case_id)
            if case:
                days = _days_elapsed(case.timestamp_started)
                self.send_proactive_message(
                    case_id,
                    f"🛡️ Recovery Update: Day {int(days)}. ✅ Bank complaint filed. "
                    "✅ Cyber cell report submitted. ✅ Credit frozen. "
                    "I'm monitoring your case and will follow up with the bank tomorrow."
                )

            time.sleep(15)  # Day 2 escalation (15 more seconds for demo)
            case = case_manager.get(case_id)
            if case:
                self.send_proactive_message(
                    case_id,
                    "⚠️ ESCALATION: Bank has not responded in 48 hours. "
                    "I've drafted an escalation email citing RBI guidelines. "
                    "Check your email to forward it to the Banking Ombudsman."
                )

        thread = threading.Thread(target=_loop, daemon=True)
        thread.start()


def _log_send(case_id: str, msg_type: str, detail: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()[:26]
    print(f"[{ts}] CASE:{case_id[:12]} SEND:{msg_type} {detail}")


def _days_elapsed(iso_timestamp: str) -> float:
    then = datetime.fromisoformat(iso_timestamp)
    now = datetime.now(timezone.utc)
    return round((now - then).total_seconds() / 86400, 1)
