"""Live test: generate the cyber crime complaint draft with the 3 real transactions.

Simulates the case state the agent holds (3 transactions from the screenshots)
and runs the actual Featherless LLM to produce the cybercrime complaint.
"""

import os
from dotenv import load_dotenv; load_dotenv()

from openai import OpenAI
from bodyguard.recovery_engine import RecoveryEngine

llm = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ["OPENAI_BASE_URL"])
engine = RecoveryEngine(llm)

# The 3 transactions extracted from the live screenshots
transactions = [
    {"amount": "₹5,000", "utr": "174096116135", "recipient": "Swapnil 555 Harak", "bank": None, "timestamp": None},
    {"amount": "₹20,000", "utr": "893002697931", "recipient": "Swapnil 555 Harak", "bank": "YES BANK", "timestamp": None},
    {"amount": "₹5,000", "utr": "661178921771", "recipient": "Swapnil 555 Harak", "bank": None, "timestamp": None},
]

txn_lines = []
for i, t in enumerate(transactions, 1):
    txn_lines.append(
        f"{i}. Amount: {t['amount']} | UTR: {t['utr']} | Paid to: {t['recipient']} "
        f"| Bank: {t['bank'] or 'unknown'} | Time: {t['timestamp'] or 'unknown'}"
    )

victim_str = "Name: Saurabh Harak | Contact: Hrk_555 | Bank: (TBD)"
fraudster_str = "UPI handle: Swapnil 555 Harak | Name: Swapnil 555 Harak"

print("=== Generating cyber crime complaint draft ===", flush=True)
draft = engine.draft_cyber_complaint(
    victim_info=victim_str,
    fraudster_info=fraudster_str,
    transactions="\n".join(txn_lines),
    scam_type="upi_fraud",
    scam_summary="Victim paid a fraudster via PhonePe in three separate UPI transactions",
)
print(draft, flush=True)
