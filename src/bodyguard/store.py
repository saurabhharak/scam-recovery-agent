"""SQLite persistence for cases.

Single source of truth for case state that survives agent restarts.
The in-memory `case_manager` stays the handler's API; this module snapshots
each Case to SQLite on every mutation and reloads them on startup.
"""

import json
import sqlite3
from pathlib import Path

from bodyguard.case_manager import Case, CaseState


class Persistence:
    """Thin SQLite store — cases persist across restarts and processes."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or str(Path(__file__).resolve().parent / "bodyguard.db")
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cases (
                case_id TEXT PRIMARY KEY,
                victim_contact TEXT NOT NULL,
                state TEXT NOT NULL,
                bank_name TEXT,
                transaction_id TEXT,
                amount_lost TEXT,
                scam_type TEXT,
                scam_summary TEXT,
                timestamp_started TEXT NOT NULL,
                emergency_contacts TEXT NOT NULL DEFAULT '[]',
                actions_completed TEXT NOT NULL DEFAULT '[]',
                pending_actions TEXT NOT NULL DEFAULT '[]',
                cyber_complaint_number TEXT,
                bank_fir_number TEXT,
                follow_up_due TEXT,
                recipient TEXT,
                transactions TEXT NOT NULL DEFAULT '[]',
                victim_info TEXT NOT NULL DEFAULT '{}',
                fraudster_info TEXT NOT NULL DEFAULT '{}',
                message_count INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        self._conn.commit()

    def save(self, case: Case) -> None:
        """Upsert a case (serialize the JSON-able fields)."""
        self._conn.execute(
            """
            INSERT INTO cases (
                case_id, victim_contact, state, bank_name, transaction_id,
                amount_lost, scam_type, scam_summary, timestamp_started,
                emergency_contacts, actions_completed, pending_actions,
                cyber_complaint_number, bank_fir_number, follow_up_due,
                recipient, transactions, victim_info, fraudster_info, message_count
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id) DO UPDATE SET
                victim_contact=excluded.victim_contact,
                state=excluded.state,
                bank_name=excluded.bank_name,
                transaction_id=excluded.transaction_id,
                amount_lost=excluded.amount_lost,
                scam_type=excluded.scam_type,
                scam_summary=excluded.scam_summary,
                timestamp_started=excluded.timestamp_started,
                emergency_contacts=excluded.emergency_contacts,
                actions_completed=excluded.actions_completed,
                pending_actions=excluded.pending_actions,
                cyber_complaint_number=excluded.cyber_complaint_number,
                bank_fir_number=excluded.bank_fir_number,
                follow_up_due=excluded.follow_up_due,
                recipient=excluded.recipient,
                transactions=excluded.transactions,
                victim_info=excluded.victim_info,
                fraudster_info=excluded.fraudster_info,
                message_count=excluded.message_count
            """,
            (
                case.case_id,
                case.victim_contact,
                case.state.value,
                case.bank_name,
                case.transaction_id,
                case.amount_lost,
                case.scam_type,
                case.scam_summary,
                case.timestamp_started,
                json.dumps(case.emergency_contacts),
                json.dumps([a.__dict__ for a in case.actions_completed]),
                json.dumps([a.__dict__ for a in case.pending_actions]),
                case.cyber_complaint_number,
                case.bank_fir_number,
                case.follow_up_due,
                case.recipient,
                json.dumps(case.transactions),
                json.dumps(case.victim_info),
                json.dumps(case.fraudster_info),
                case.message_count,
            ),
        )
        self._conn.commit()

    def load(self, case_id: str) -> Case | None:
        row = self._conn.execute(
            "SELECT * FROM cases WHERE case_id = ?", (case_id,)
        ).fetchone()
        return self._row_to_case(row) if row else None

    def load_all(self) -> list[Case]:
        rows = self._conn.execute("SELECT * FROM cases").fetchall()
        return [self._row_to_case(r) for r in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _row_to_case(row: sqlite3.Row) -> Case:
        from bodyguard.case_manager import CaseAction

        return Case(
            case_id=row["case_id"],
            victim_contact=row["victim_contact"],
            state=CaseState(row["state"]),
            bank_name=row["bank_name"],
            transaction_id=row["transaction_id"],
            amount_lost=row["amount_lost"],
            scam_type=row["scam_type"],
            scam_summary=row["scam_summary"],
            timestamp_started=row["timestamp_started"],
            emergency_contacts=json.loads(row["emergency_contacts"] or "[]"),
            actions_completed=[
                CaseAction(**a) for a in json.loads(row["actions_completed"] or "[]")
            ],
            pending_actions=[
                CaseAction(**a) for a in json.loads(row["pending_actions"] or "[]")
            ],
            cyber_complaint_number=row["cyber_complaint_number"],
            bank_fir_number=row["bank_fir_number"],
            follow_up_due=row["follow_up_due"],
            recipient=row["recipient"],
            transactions=json.loads(row["transactions"] or "[]"),
            victim_info=json.loads(row["victim_info"] or "{}"),
            fraudster_info=json.loads(row["fraudster_info"] or "{}"),
            message_count=row["message_count"],
        )
