"""Entry point: Scam Recovery Commander (Digital Bodyguard).

Connects email + Telegram, wires the LLM engine, and starts listening.

Usage:
    python -m bodyguard.main
    # or via the pyproject.toml script entry:
    bodyguard
"""

from datetime import datetime, timezone

from openai import OpenAI
from caspian_sdk import CommClient

from bodyguard.config import get_config
from bodyguard.handler import handle
from bodyguard.recovery_engine import RecoveryEngine
from bodyguard.alert_system import AlertSystem


def run() -> None:
    config = get_config()

    # ── Caspian: one identity across channels ──
    client = CommClient(
        api_key=config.caspian_api_key,
        base_url=config.caspian_base_url,
    )

    email_conn = client.connect_email(username=config.bodyguard_username)
    telegram_conn = client.connect_telegram(bot_token=config.telegram_bot_token)

    print(f"🛡️  Digital Bodyguard ONLINE")
    print(f"   Email:    {email_conn['address']}")
    print(f"   Telegram: @{telegram_conn['address']}")
    print(f"   LLM:      {config.llm_model}")
    print(f"   Started:  {datetime.now(timezone.utc).isoformat()[:19]}Z")
    print()

    # ── LLM client (injected — swap providers in one line) ──
    llm = OpenAI(
        api_key=config.openai_api_key,
        base_url=config.openai_base_url,
    )
    engine = RecoveryEngine(llm)
    alerts = AlertSystem(client)

    # ── One handler, both channels ──
    @client.on_message
    def on_message(message):
        handle(client, message, engine, alerts)

    client.listen(ack="🛡️ Bodyguard activated. Processing your report...")


if __name__ == "__main__":
    run()
