from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = REPO_ROOT / ".agent" / "locks" / "run_job.lock"
LOG_DIR = REPO_ROOT / ".agent" / "logs"

E_LOCK_CONFLICT = 11
E_NO_ACTIVE_NODES = 12
E_RUN_FAILED = 13


def _check_staleness() -> str | None:
    import sqlite3

    db_path = REPO_ROOT / "artifacts" / "db" / "bestsellers.sqlite"
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT finished_at FROM runs WHERE status='completed' ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        conn.close()
    except sqlite3.Error:
        return None
    if row is None or not row[0]:
        return None
    try:
        from datetime import datetime

        last = datetime.strptime(row[0][:19], "%Y-%m-%dT%H:%M:%S")
        age_hours = (datetime.now() - last).total_seconds() / 3600
    except ValueError:
        return None
    if age_hours > 3.5:
        return f"WATCHDOG ALERT: last completed run is {age_hours:.1f}h old (>3.5h threshold)"
    return None


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def acquire_lock() -> int | None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            info = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
            pid = int(info.get("pid", 0))
            started = float(info.get("started_ts", 0))
            if _pid_alive(pid) and time.time() - started < 3600 * 2:
                return pid
        except (json.JSONDecodeError, ValueError):
            pass
        LOCK_PATH.unlink()
    payload = {"pid": os.getpid(), "started_ts": time.time()}
    tmp = LOCK_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload), encoding="utf-8")
    tmp.replace(LOCK_PATH)
    return None


def release_lock():
    try:
        current = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if current.get("pid") == os.getpid():
            LOCK_PATH.unlink()
    except (FileNotFoundError, json.JSONDecodeError):
        pass


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_job")
    parser.add_argument("--no-detail", action="store_true")
    args = parser.parse_args()

    holder = acquire_lock()
    if holder is not None:
        print(json.dumps({"error": "lock_conflict", "held_by_pid": holder}))
        return E_LOCK_CONFLICT

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S") + "_" + uuid.uuid4().hex[:6]
    log_path = LOG_DIR / f"run_job_{stamp}.log"

    cmd = [sys.executable, "-m", "crawl_amazon_beauty_bestsellers.cli", "run", "--active"]
    if args.no_detail:
        cmd.append("--no-detail")
    marketplace = os.environ.get("AMZBS_MARKETPLACE", "")
    if marketplace:
        cmd += ["--marketplace", marketplace]

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    print(f"[{started}] run_job start: {' '.join(cmd)}")
    alert = _check_staleness()
    if alert:
        print(f"[{started}] {alert}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    log_path.write_text(
        "\n".join([f"# started {started}", "# stdout", proc.stdout, "# stderr", proc.stderr]),
        encoding="utf-8",
    )
    release_lock()
    finished = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    status = "completed" if proc.returncode == 0 else "failed"
    print(f"[{finished}] run_job {status} rc={proc.returncode} log={log_path}")
    if proc.returncode != 0:
        return E_RUN_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
