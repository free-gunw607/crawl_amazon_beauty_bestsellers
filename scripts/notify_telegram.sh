#!/usr/bin/env bash
# Send a Telegram message. Requires TG_BOT_TOKEN and TG_CHAT_ID env vars.
# Usage: notify_telegram.sh "message text"
set -euo pipefail

if [[ -z "${TG_BOT_TOKEN:-}" || -z "${TG_CHAT_ID:-}" ]]; then
  echo "TG_BOT_TOKEN or TG_CHAT_ID not set, skipping notification" >&2
  exit 0
fi

MESSAGE="${1:-}"
if [[ -z "$MESSAGE" ]]; then
  echo "Usage: $0 \"message\"" >&2
  exit 1
fi

curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TG_CHAT_ID}" \
  -d text="${MESSAGE}" \
  -d parse_mode="HTML" \
  --max-time 10 >/dev/null 2>&1 || echo "Telegram send failed" >&2
