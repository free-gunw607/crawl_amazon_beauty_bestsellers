#!/usr/bin/env bash
set -u

lock_file="$1"
shift

/usr/bin/flock -n -E 75 "$lock_file" "$@"
status=$?
if [[ "$status" -eq 75 ]]; then
  echo "[schedule] another pipeline owns the Linux lock; skipping this overlapping invocation"
  exit 0
fi
exit "$status"
