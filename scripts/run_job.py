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
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_telegram.sh"
ENV_FILE = REPO_ROOT / ".env"

E_LOCK_CONFLICT = 11
E_NO_ACTIVE_NODES = 12
E_RUN_FAILED = 13


def _send_telegram(message: str) -> None:
    """Send a Telegram notification if TG_BOT_TOKEN and TG_CHAT_ID are set."""
    token = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        return
    try:
        subprocess.run(
            ["bash", str(NOTIFY_SCRIPT), message],
            timeout=15,
            capture_output=True,
        )
    except Exception:
        pass


def _build_report(status: str, rc: int, elapsed: float, stdout: str, log_path: Path) -> str:
    """Build a concise Telegram briefing message."""
    icon = "OK" if status == "completed" else "FAILED"
    minutes = elapsed / 60

    # Extract region stats from stdout
    region_lines = []
    for line in stdout.splitlines():
        line = line.strip()
        if line.startswith("[") and ("title=" in line or "price=" in line):
            region_lines.append(line)

    stats = "\n".join(region_lines[-10:]) if region_lines else "(no region stats)"

    return (
        f"<b>Beauty Bestseller {icon}</b>\n"
        f"Time: {minutes:.1f}min | RC: {rc}\n"
        f"Log: {log_path.name}\n\n"
        f"<code>{stats}</code>"
    )


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


def _load_env() -> None:
    """Load .env file into os.environ (simple KEY=VALUE parser)."""
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip("\"'")
            if key and key not in os.environ:
                os.environ[key] = value


def main() -> int:
    _load_env()
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
    start_ts = time.time()
    print(f"[{started}] run_job start: {' '.join(cmd)}")
    alert = _check_staleness()
    if alert:
        print(f"[{started}] {alert}")
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    elapsed = time.time() - start_ts
    log_path.write_text(
        "\n".join([f"# started {started}", "# stdout", proc.stdout, "# stderr", proc.stderr]),
        encoding="utf-8",
    )
    release_lock()
    finished = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    status = "completed" if proc.returncode == 0 else "failed"
    print(f"[{finished}] run_job {status} rc={proc.returncode} log={log_path}")

    # Send Telegram briefing
    report = _build_report(status, proc.returncode, elapsed, proc.stdout, log_path)
    _send_telegram(report)

    if proc.returncode != 0:
        return E_RUN_FAILED
    return 0


if __name__ == "__main__":
    sys.exit(main())
