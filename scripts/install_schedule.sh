#!/usr/bin/env bash
# Install/remove the systemd user timers for crawl_amazon_beauty_bestsellers.
# Owner approval recorded 2026-08-25 (schedule activation gate).
#   hourly list snapshots (--no-detail) + detail/vendor pass every 6h.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
UNITS=(
  crawl-amazon-bs.service
  crawl-amazon-bs.timer
  crawl-amazon-bs-details.service
  crawl-amazon-bs-details.timer
)

usage() {
  echo "usage: $0 install|uninstall|status" >&2
  exit 2
}

install_units() {
  mkdir -p "$UNIT_DIR"
  for unit in "${UNITS[@]}"; do
    cp "$REPO_ROOT/deploy/systemd/$unit" "$UNIT_DIR/"
  done
  systemctl --user daemon-reload
  systemctl --user enable --now crawl-amazon-bs.timer crawl-amazon-bs-details.timer
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER" 2>/dev/null \
      && echo "linger enabled (timers run without an active login session)" \
      || echo "NOTE: linger not enabled; timers run only while a user session exists"
  fi
  systemctl --user list-timers --no-pager
}

uninstall_units() {
  systemctl --user disable --now crawl-amazon-bs.timer crawl-amazon-bs-details.timer 2>/dev/null || true
  for unit in "${UNITS[@]}"; do
    rm -f "$UNIT_DIR/$unit"
  done
  systemctl --user daemon-reload
  echo "timers removed; no further automated cycles will fire"
}

show_status() {
  systemctl --user list-timers 'crawl-amazon-bs*' --no-pager || true
}

case "${1:-}" in
  install) install_units ;;
  uninstall) uninstall_units ;;
  status) show_status ;;
  *) usage ;;
esac
