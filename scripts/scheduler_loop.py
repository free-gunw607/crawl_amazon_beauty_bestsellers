#!/usr/bin/env python3
"""Privilege-free interim scheduler for crawl_amazon_beauty_bestsellers.

Runs the same cadence as the registered crontab entries (hourly list job at
:17, detail/vendor pass 01/07/13/19 at :47) without requiring root or a cron
daemon. Intended for WSL2 sessions without systemd; stop once `sudo service
cron start` is available. Single-instance via lockfile.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK = REPO_ROOT / ".agent" / "locks" / "scheduler_loop.lock"
MARKERS = REPO_ROOT / ".agent" / "locks"
LOG = REPO_ROOT / ".agent" / "logs" / "scheduler_loop.log"

LIST_MINUTE = 17
DETAIL_HOURS = {1, 7, 13, 19}
DETAIL_MINUTE = 47


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def acquire_lock() -> int | None:
    LOCK.parent.mkdir(parents=True, exist_ok=True)
    if LOCK.exists():
        try:
            info = json.loads(LOCK.read_text())
            if _pid_alive(int(info["pid"])):
                return int(info["pid"])
        except Exception:
            pass
    LOCK.write_text(json.dumps({"pid": os.getpid(), "started_ts": time.time()}))
    return None


def log(msg: str) -> None:
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{stamp}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as fh:
        fh.write(line + "\n")


def fired(key: str) -> bool:
    p = MARKERS / f"sched_{key}.mark"
    if not p.exists():
        return False
    try:
        return p.read_text().strip() == time.strftime("%Y%m%d_%H")
    except OSError:
        return False


def mark(key: str) -> None:
    (MARKERS / f"sched_{key}.mark").write_text(time.strftime("%Y%m%d_%H"))


def run_job(args: list[str]) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "run_job.py"), *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True,
    )
    log(f"run_job {' '.join(args)} rc={proc.returncode} tail={proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ''}")


def main() -> int:
    holder = acquire_lock()
    if holder is not None:
        log(f"another scheduler loop holds the lock (pid {holder}); exiting")
        return 0
    log(f"interim scheduler loop started (pid {os.getpid()}); crontab entries remain registered for when cron daemon runs")
    while True:
        now = time.localtime()
        if now.tm_min == LIST_MINUTE and not fired("list"):
            mark("list")
            run_job(["--no-detail"])
        if now.tm_min == DETAIL_MINUTE and now.tm_hour in DETAIL_HOURS and not fired("detail"):
            mark("detail")
            run_job([])
        time.sleep(30)


if __name__ == "__main__":
    sys.exit(main())
