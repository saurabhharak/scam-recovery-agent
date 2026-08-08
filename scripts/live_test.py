"""One-shot live test: simulate what the handler does on a real message."""

import os
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from caspian_sdk import CommClient

from bodyguard.handler import handle
from bodyguard.recovery_engine import RecoveryEngine
from bodyguard.alert_system import AlertSystem
from bodyguard.case_manager import case_manager


class FakeMessage:
    def __init__(self, text, conversation_id="conv_live_test"):
        self.text = text
        self.sender = {"address": "victim@example.com"}
        self.conversation_id = conversation_id
        self.replies = []
        self.typing_calls = 0

    def reply(self, content):
        self.replies.append(content)
        print(f"  [REPLY] {content[:200]}...")

    def typing(self):
        self.typing_calls += 1


client = CommClient()
llm = OpenAI(api_key=os.environ["OPENAI_API_KEY"], base_url=os.environ["OPENAI_BASE_URL"])
engine = RecoveryEngine(llm)
alerts = AlertSystem(client)

print("=== Testing handler flow ===")
case_manager._cases.clear()
msg = FakeMessage(
    "Help! I just got scammed. Someone called pretending to be from HDFC and I shared my OTP. "
    "₹50,000 was debited from my account. What do I do?"
)
try:
    handle(client, msg, engine, alerts)
    print("=== Handler completed ===")
    print(f"Replies: {len(msg.replies)}")
    print(f"Case state: {case_manager.get('conv_live_test').state}")
except Exception as e:
    import traceback
    print("=== HANDLER CRASHED ===")
    traceback.print_exc()
