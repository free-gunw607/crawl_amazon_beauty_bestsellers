#!/usr/bin/env bash
# Install/remove the hourly systemd user timer for crawl_amazon_beauty_bestsellers.
# Owner approval recorded 2026-08-25 (schedule activation gate).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="crawl-amazon-bs.service"
TIMER_NAME="crawl-amazon-bs.timer"

usage() {
  echo "usage: $0 install|uninstall|status" >&2
  exit 2
}

install_units() {
  mkdir -p "$UNIT_DIR"
  cp "$REPO_ROOT/deploy/systemd/$SERVICE_NAME" "$UNIT_DIR/"
  cp "$REPO_ROOT/deploy/systemd/$TIMER_NAME" "$UNIT_DIR/"
  systemctl --user daemon-reload
  systemctl --user enable --now "$TIMER_NAME"
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER" 2>/dev/null \
      && echo "linger enabled (timer runs without an active login session)" \
      || echo "NOTE: linger not enabled; timer runs only while a user session exists"
  fi
  systemctl --user list-timers "$TIMER_NAME" --no-pager
}

uninstall_units() {
  systemctl --user disable --now "$TIMER_NAME" 2>/dev/null || true
  rm -f "$UNIT_DIR/$SERVICE_NAME" "$UNIT_DIR/$TIMER_NAME"
  systemctl --user daemon-reload
  echo "timer removed; no further automated cycles will fire"
}

show_status() {
  systemctl --user list-timers "$TIMER_NAME" --no-pager || true
}

case "${1:-}" in
  install) install_units ;;
  uninstall) uninstall_units ;;
  status) show_status ;;
  *) usage ;;
esac
