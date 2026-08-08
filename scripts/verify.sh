#!/usr/bin/env bash
# Pre-demo verification script — run before recording the demo video.
# Checks: env vars, dependencies, API connectivity, bot status.

set -euo pipefail

echo "=== Scam Recovery Commander — Pre-Demo Verification ==="
echo ""

# 1. Environment variables
echo "1/5 Checking environment variables..."
missing=0
for var in CASPIAN_API_KEY TELEGRAM_BOT_TOKEN OPENAI_API_KEY; do
  source .env 2>/dev/null || true
  if [ -z "${!var:-}" ]; then
    echo "   ❌ $var is not set in .env"
    missing=1
  else
    echo "   ✅ $var is set"
  fi
done
if [ "$missing" -eq 1 ]; then
  echo "   Copy .env.example to .env and fill in the values."
  exit 1
fi

# 2. Dependencies
echo "2/5 Checking dependencies..."
if ! uv run python -c "import caspian_sdk" 2>/dev/null; then
  echo "   ❌ caspian-sdk not installed. Run: uv sync --all-extras"
  exit 1
fi
if ! uv run python -c "import openai" 2>/dev/null; then
  echo "   ❌ openai not installed. Run: uv sync --all-extras"
  exit 1
fi
echo "   ✅ All dependencies installed"

# 3. Caspian API connectivity
echo "3/5 Checking Caspian API..."
source .env
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
  "https://api.trycaspianai.com/v1/channels" \
  -H "Authorization: Bearer $CASPIAN_API_KEY")
if [ "$RESPONSE" != "200" ]; then
  echo "   ❌ Caspian API returned HTTP $RESPONSE. Check your API key."
  exit 1
fi
echo "   ✅ Caspian API connected"

# 4. Live channels
echo "4/5 Verifying live channels..."
CHANNELS=$(curl -s "https://api.trycaspianai.com/v1/channels" \
  -H "Authorization: Bearer $CASPIAN_API_KEY")
if echo "$CHANNELS" | grep -q "email"; then
  echo "   ✅ Email channel available"
fi
if echo "$CHANNELS" | grep -q "telegram"; then
  echo "   ✅ Telegram channel available"
fi

# 5. Tests
echo "5/5 Running tests..."
echo "   (TDD policy: tests are written BEFORE code. A red suite blocks any commit.)"
if uv run pytest tests/ -q 2>/dev/null; then
  echo "   ✅ All tests pass"
else
  echo "   ❌ Tests failed — TDD gate. Fix before recording the demo."
  exit 1
fi

echo ""
echo "=== Verification complete ==="
echo "Next steps:"
echo "  1. Start the agent: uv run python -m bodyguard.main"
echo "  2. Send a test:     curl -s -X POST https://api.trycaspianai.com/v1/test-emails ..."
echo "  3. Record the demo:  OBS, screen capture, show BOTH channels side by side"
echo "  4. Submit on Unstop:  answer 'Yes' to starred repo, paste GitHub + video links"
