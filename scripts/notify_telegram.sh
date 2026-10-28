#!/usr/bin/env bash
# Send a Telegram message. Requires TG_BOT_TOKEN and TG_CHAT_ID env vars.
# Usage: notify_telegram.sh "message text"
set -euo pipefail

TG_BOT_TOKEN="${TG_BOT_TOKEN:-${TELEGRAM_BOT_TOKEN:-${BOT_TOKEN:-}}}"
TG_CHAT_ID="${TG_CHAT_ID:-${TELEGRAM_CHAT_ID:-${TELEGRAM_ALERT_CHAT_ID:-${CHAT_ID:-}}}}"

if [[ -z "${TG_BOT_TOKEN:-}" || -z "${TG_CHAT_ID:-}" ]]; then
  echo "Telegram token/chat env not set, skipping notification" >&2
  exit 0
fi

MESSAGE="${1:-}"
if [[ -z "$MESSAGE" ]]; then
  echo "Usage: $0 \"message\"" >&2
  exit 1
fi

response="$(curl -s -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/sendMessage" \
  -d chat_id="${TG_CHAT_ID}" \
  -d text="${MESSAGE}" \
  --max-time 10)"

if [[ "$response" != *'"ok":true'* ]]; then
  echo "Telegram send failed" >&2
  exit 1
fi
