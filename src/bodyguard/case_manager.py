"""Case state machine and in-memory storage.

Channel-agnostic: this module has zero awareness of email vs Telegram.
The handler and alert_system are the only modules that touch channels.
"""

import json
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CaseState(Enum):
    TRIAGE = "TRIAGE"
    BANK_ALERT = "BANK_ALERT"
    CYBER_COMPLAINT = "CYBER_COMPLAINT"
    CONTACT_ALERT = "CONTACT_ALERT"
    CREDIT_FREEZE = "CREDIT_FREEZE"
    PASSWORD_2FA = "PASSWORD_2FA"
    RECOVERY_TRACKING = "RECOVERY_TRACKING"
    RESOLVED = "RESOLVED"


# Explicit valid transitions — no other path is allowed
VALID_TRANSITIONS: dict[CaseState, set[CaseState]] = {
    CaseState.TRIAGE: {
        CaseState.BANK_ALERT,
        CaseState.CYBER_COMPLAINT,
        CaseState.CONTACT_ALERT,
        CaseState.CREDIT_FREEZE,
        CaseState.PASSWORD_2FA,
    },
    CaseState.BANK_ALERT: {CaseState.CYBER_COMPLAINT, CaseState.RECOVERY_TRACKING},
    CaseState.CYBER_COMPLAINT: {CaseState.RECOVERY_TRACKING},
    CaseState.CONTACT_ALERT: {CaseState.RECOVERY_TRACKING},
    CaseState.CREDIT_FREEZE: {CaseState.RECOVERY_TRACKING},
    CaseState.PASSWORD_2FA: {CaseState.RECOVERY_TRACKING},
    CaseState.RECOVERY_TRACKING: {CaseState.RESOLVED},
    CaseState.RESOLVED: set(),
}


@dataclass
class CaseAction:
    action: str
    timestamp: str
    result: str = ""
    deadline: str | None = None


@dataclass
class Case:
    case_id: str
    victim_contact: str
    state: CaseState = CaseState.TRIAGE
    bank_name: str | None = None
    transaction_id: str | None = None
    amount_lost: str | None = None
    scam_type: str | None = None
    scam_summary: str | None = None
    timestamp_started: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    emergency_contacts: list[str] = field(default_factory=list)
    actions_completed: list[CaseAction] = field(default_factory=list)
    pending_actions: list[CaseAction] = field(default_factory=list)
    cyber_complaint_number: str | None = None
    bank_fir_number: str | None = None
    follow_up_due: str | None = None
    recipient: str | None = None
    # Cybercrime requires ALL transactions + victim/fraudster identifiers
    transactions: list[dict] = field(default_factory=list)
    victim_info: dict = field(default_factory=dict)
    fraudster_info: dict = field(default_factory=dict)
    message_count: int = 0


class CaseManager:
    """In-memory case store keyed on conversation_id. Single source of truth.

    YAGNI: no database, no Redis. A dict is sufficient for the 3-min demo.
    Post-hackathon: swap this module for a SQLite backend — zero other changes.
    """

    def __init__(self):
        self._cases: dict[str, Case] = {}

    def get(self, case_id: str) -> Case | None:
        return self._cases.get(case_id)

    def get_or_create(self, case_id: str, victim_contact: str) -> Case:
        if case_id not in self._cases:
            self._cases[case_id] = Case(
                case_id=case_id,
                victim_contact=victim_contact,
            )
        return self._cases[case_id]

    def advance_state(self, case_id: str, new_state: CaseState) -> Case:
        case = self._cases[case_id]
        if new_state not in VALID_TRANSITIONS.get(case.state, set()):
            raise ValueError(
                f"Invalid state transition: {case.state.value} → {new_state.value}"
            )
        old_state = case.state.value
        case.state = new_state
        _log_action(case_id, "STATE_CHANGE", f"{old_state} → {new_state.value}")
        return case

    def update_case(self, case_id: str, **fields: Any) -> Case:
        case = self._cases[case_id]
        for key, value in fields.items():
            if hasattr(case, key):
                setattr(case, key, value)
        case.message_count += 1
        _log_action(case_id, "CASE_UPDATE", str(fields))
        return case

    def add_action(self, case_id: str, action: str, deadline: str | None = None) -> None:
        case = self._cases[case_id]
        ts = datetime.now(timezone.utc).isoformat()
        case.pending_actions.append(
            CaseAction(action=action, timestamp=ts, deadline=deadline)
        )

    def complete_action(self, case_id: str, action_name: str, result: str = "") -> None:
        case = self._cases[case_id]
        for pending in list(case.pending_actions):
            if pending.action == action_name:
                case.pending_actions.remove(pending)
                pending.result = result
                case.actions_completed.append(pending)
                _log_action(case_id, "ACTION_COMPLETED", f"{action_name}: {result}")
                return

    def add_transaction(self, case_id: str, txn: dict) -> bool:
        """Add a transaction to the case. Returns True if added, False if duplicate.

        Dedupes on UTR — a user may send the same screenshot twice. Keeps the
        single `transaction_id`/`amount_lost` fields in sync (first txn) and
        sums the total amount for the cybercrime complaint.
        """
        case = self._cases[case_id]
        utr = txn.get("utr")
        # Dedup by UTR if present
        if utr and any(t.get("utr") == utr for t in case.transactions):
            _log_action(case_id, "TXN_DUP", f"UTR {utr} already recorded")
            return False
        case.transactions.append(txn)
        # Keep legacy single fields pointing at the first transaction
        if not case.transaction_id and utr:
            case.transaction_id = utr
        if not case.recipient and txn.get("recipient"):
            case.recipient = txn["recipient"]
        if not case.bank_name and txn.get("bank"):
            case.bank_name = txn["bank"]
        # Recompute total amount
        total = 0
        for t in case.transactions:
            total += _parse_amount(t.get("amount"))
        if total:
            # Format without trailing .0 for whole rupees
            case.amount_lost = f"₹{total:,.0f}" if total == int(total) else f"₹{total:,}"
        _log_action(case_id, "TXN_ADDED", f"UTR {utr} amount {txn.get('amount')}")
        return True

    def get_timeline(self, case_id: str) -> str:
        case = self._cases[case_id]
        lines = [f"*Case Status: {case.state.value}*"]
        lines.append(f"Started: {case.timestamp_started[:19]}")
        lines.append(f"Bank: {case.bank_name or '—'}")
        # Total lost — compute from transactions if not already set
        if case.amount_lost:
            lines.append(f"Total Lost: {case.amount_lost}")
        elif case.transactions:
            total = sum(_parse_amount(t.get("amount")) for t in case.transactions)
            if total:
                total_str = f"₹{total:,.0f}" if total == int(total) else f"₹{total:,}"
                lines.append(f"Total Lost: {total_str}")

        # List ALL transactions (cybercrime needs every one)
        if case.transactions:
            lines.append("")
            lines.append(f"*Transactions ({len(case.transactions)}):*")
            for i, t in enumerate(case.transactions, 1):
                lines.append(
                    f"  {i}. {t.get('amount') or '—'} — {t.get('recipient') or '—'} "
                    f"(UTR: {t.get('utr') or '—'}) {t.get('timestamp') or ''}".rstrip()
                )
        elif case.transaction_id:
            lines.append(f"TXN ID: {case.transaction_id}")
        lines.append("")

        if case.actions_completed:
            lines.append("*Completed:*")
            for a in case.actions_completed:
                lines.append(f"  ✅ {a.action} ({a.timestamp[:19]})")
                if a.result:
                    lines.append(f"     {a.result}")

        if case.pending_actions:
            lines.append("*Pending:*")
            for a in case.pending_actions:
                deadline = f" (by {a.deadline})" if a.deadline else ""
                lines.append(f"  ⏳ {a.action}{deadline}")

        return "\n".join(lines)

    def get_summary_for_llm(self, case_id: str) -> str:
        """Compact summary for the LLM context window. Not raw history."""
        case = self._cases[case_id]
        return json.dumps(
            {
                "state": case.state.value,
                "bank": case.bank_name,
                "amount": case.amount_lost,
                "txn_id": case.transaction_id,
                "scam_type": case.scam_type,
                "days_since": _days_since(case.timestamp_started),
                "completed": [a.action for a in case.actions_completed],
                "pending": [a.action for a in case.pending_actions],
            },
            ensure_ascii=False,
        )


# Singleton — one store for the entire agent lifetime
case_manager = CaseManager()


def _log_action(case_id: str, action: str, detail: str) -> None:
    ts = datetime.now(timezone.utc).isoformat()[:26]
    print(f"[{ts}] CASE:{case_id[:12]} ACTION:{action} {detail}")


def _days_since(iso_timestamp: str) -> float:
    then = datetime.fromisoformat(iso_timestamp)
    now = datetime.now(timezone.utc)
    return round((now - then).total_seconds() / 86400, 1)


def _parse_amount(amount: str | None) -> float:
    """Parse an amount string like '₹5,000' or '5000.00' to a float."""
    if not amount:
        return 0.0
    cleaned = amount.replace("₹", "").replace(",", "").replace("Rs", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0
