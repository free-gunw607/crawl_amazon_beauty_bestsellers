#!/usr/bin/env bash
# Install/remove the systemd user timer for crawl_amazon_beauty_bestsellers.
# v1.0: Single timer, daily 5AM KST (UTC 20:00), all 5 regions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
UNITS=(
  amzbs-beauty.service
  amzbs-beauty.timer
  amzbs-beauty-watchdog.service
  amzbs-beauty-watchdog.timer
  amzbs-beauty-catchup.service
  amzbs-beauty-catchup.timer
)
CRON_MARK_BEGIN="# crawl_amazon_beauty_bestsellers BEGIN"
CRON_MARK_END="# crawl_amazon_beauty_bestsellers END"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi
GWS_BIN="$(command -v gws || true)"
if [[ -z "$GWS_BIN" && -x "${HOME}/.cargo/bin/gws" ]]; then
  GWS_BIN="${HOME}/.cargo/bin/gws"
fi
if [[ -z "$GWS_BIN" ]]; then
  echo "gws CLI is required for Drive uploads; install it before activating this schedule" >&2
  exit 1
fi
GWS_BIN_DIR="$(dirname "$GWS_BIN")"
SERVICE_ACCOUNT_FILE="${HOME}/.config/amzbs/service-account.json"
GWS_CONFIG_DIR="${HOME}/.config/gws-amazon"
if [[ -r "$SERVICE_ACCOUNT_FILE" ]]; then
  ROOT_BACKEND="sa"
else
  ROOT_BACKEND="gws"
fi

cron_block() {
  cat <<EOF
$CRON_MARK_BEGIN
SHELL=/bin/bash
PATH=$GWS_BIN_DIR:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
AMZ_BS_ROOT_BACKEND=$ROOT_BACKEND
AMZ_BS_ROOT_SHEETS_ID=1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80
AMZ_BS_DRIVE_BACKEND=gws
GDRIVE_CREDS=$SERVICE_ACCOUNT_FILE
GOOGLE_WORKSPACE_CLI_CONFIG_DIR=$GWS_CONFIG_DIR
GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND=keyring
PYTHONPATH=$REPO_ROOT/src
0 5 * * * cd $REPO_ROOT && /usr/bin/flock -n .agent/locks/daily_pipeline.lock $PYTHON_BIN scripts/run_daily_pipeline.py >> .agent/logs/cron_daily_pipeline.log 2>&1
55 5-23 * * * cd $REPO_ROOT && /usr/bin/flock -n .agent/locks/daily_pipeline.lock $PYTHON_BIN scripts/daily_catchup.py --not-before-hour 5 --email >> .agent/logs/cron_daily_catchup.log 2>&1
17 * * * * cd $REPO_ROOT && $PYTHON_BIN scripts/watchdog_sheet.py --max-age-hours 30 --alert >> .agent/logs/cron_watchdog.log 2>&1
$CRON_MARK_END
EOF
}

install_cron() {
  mkdir -p "$REPO_ROOT/.agent/logs"
  systemctl --user disable --now amzbs-beauty.timer amzbs-beauty-watchdog.timer amzbs-beauty-catchup.timer >/dev/null 2>&1 || true
  local current tmp
  current="$(crontab -l 2>/dev/null || true)"
  tmp="$(mktemp)"
  printf "%s\n" "$current" | awk -v b="$CRON_MARK_BEGIN" -v e="$CRON_MARK_END" '
    $0 == b {skip=1; next}
    $0 == e {skip=0; next}
    !skip {print}
  ' > "$tmp"
  {
    cat "$tmp"
    cron_block
  } | crontab -
  rm -f "$tmp"
  echo "cron fallback installed: daily 05:00 run_job + hourly Sheet watchdog"
  crontab -l | sed -n "/$CRON_MARK_BEGIN/,/$CRON_MARK_END/p"
}

uninstall_cron() {
  local current tmp
  current="$(crontab -l 2>/dev/null || true)"
  tmp="$(mktemp)"
  printf "%s\n" "$current" | awk -v b="$CRON_MARK_BEGIN" -v e="$CRON_MARK_END" '
    $0 == b {skip=1; next}
    $0 == e {skip=0; next}
    !skip {print}
  ' > "$tmp"
  crontab "$tmp"
  rm -f "$tmp"
  echo "cron fallback removed"
}

usage() {
  echo "usage: $0 install|uninstall|status" >&2
  exit 2
}

install_units() {
  if ! systemctl --user list-timers >/dev/null 2>&1; then
    echo "systemd user bus unavailable; installing cron fallback instead"
    install_cron
    return
  fi
  mkdir -p "$UNIT_DIR"
  for unit in "${UNITS[@]}"; do
    cp "$REPO_ROOT/deploy/systemd/$unit" "$UNIT_DIR/"
  done
  systemctl --user daemon-reload
  systemctl --user enable --now amzbs-beauty.timer amzbs-beauty-watchdog.timer amzbs-beauty-catchup.timer
  # Keep one scheduler active on a node. Once systemd timers are confirmed,
  # remove this repo's cron block to prevent duplicate crawls and reports.
  if systemctl --user list-timers --all --no-pager | grep -q 'amzbs-beauty-catchup.timer' \
    && systemctl --user list-timers --all --no-pager | grep -q 'amzbs-beauty-watchdog.timer' \
    && systemctl --user list-timers --all --no-pager | grep -q 'amzbs-beauty.timer'; then
    uninstall_cron
  else
    echo "systemd timers were not confirmed; preserving cron fallback" >&2
    install_cron
    return 1
  fi
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER" 2>/dev/null \
      && echo "linger enabled (timers run without an active login session)" \
      || echo "NOTE: linger not enabled; timers run only while a user session exists"
  fi
  echo "amzbs-beauty.timer installed (daily 5AM KST); watchdog hourly; duplicate cron block removed"
  systemctl --user list-timers --no-pager
}

uninstall_units() {
  systemctl --user disable --now amzbs-beauty.timer amzbs-beauty-watchdog.timer amzbs-beauty-catchup.timer 2>/dev/null || true
  for unit in "${UNITS[@]}"; do
    rm -f "$UNIT_DIR/$unit"
  done
  # Clean up legacy timers if they exist
  systemctl --user disable --now \
    crawl-amazon-bs.timer \
    crawl-amazon-bs-details.timer \
    amzbs-mr-us.timer \
    amzbs-mr-uk.timer \
    amzbs-mr-de.timer \
    amzbs-mr-fr.timer \
    amzbs-mr-es.timer 2>/dev/null || true
  for old in crawl-amazon-bs.{service,timer} crawl-amazon-bs-details.{service,timer} \
             amzbs-mr-{us,uk,de,fr,es}.{service,timer}; do
    rm -f "$UNIT_DIR/$old"
  done
  systemctl --user daemon-reload
  uninstall_cron
  echo "all timers removed; no further automated cycles will fire"
}

show_status() {
  systemctl --user list-timers 'amzbs-*' --no-pager || true
  crontab -l 2>/dev/null | sed -n "/$CRON_MARK_BEGIN/,/$CRON_MARK_END/p" || true
}

case "${1:-}" in
  install) install_units ;;
  uninstall) uninstall_units ;;
  status) show_status ;;
  *) usage ;;
esac
