#!/usr/bin/env bash
# Install/remove the systemd user timer for crawl_amazon_beauty_bestsellers.
# v1.0: Single timer, daily 5AM KST (UTC 20:00), all 5 regions.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNIT_DIR="${HOME}/.config/systemd/user"
UNITS=(
  amzbs-beauty.service
  amzbs-beauty.timer
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
  systemctl --user enable --now amzbs-beauty.timer
  if command -v loginctl >/dev/null 2>&1; then
    loginctl enable-linger "$USER" 2>/dev/null \
      && echo "linger enabled (timers run without an active login session)" \
      || echo "NOTE: linger not enabled; timers run only while a user session exists"
  fi
  echo "amzbs-beauty.timer installed (daily 5AM KST)"
  systemctl --user list-timers --no-pager
}

uninstall_units() {
  systemctl --user disable --now amzbs-beauty.timer 2>/dev/null || true
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
  echo "all timers removed; no further automated cycles will fire"
}

show_status() {
  systemctl --user list-timers 'amzbs-*' --no-pager || true
}

case "${1:-}" in
  install) install_units ;;
  uninstall) uninstall_units ;;
  status) show_status ;;
  *) usage ;;
esac
