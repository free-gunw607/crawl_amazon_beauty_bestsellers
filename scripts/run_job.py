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
    """Build a detailed but easy-to-read Telegram briefing."""
    icon = "✅" if status == "completed" else "❌"
    minutes = elapsed / 60

    # Parse JSON output from CLI
    runs = []
    ok_count = 0
    fail_count = 0
    json_start = stdout.rfind("\n{")
    if json_start >= 0:
        try:
            data = json.loads(stdout[json_start:])
            runs = data.get("runs", [])
            ok_count = data.get("ok", 0)
            fail_count = data.get("failed", 0)
        except (json.JSONDecodeError, KeyError):
            pass

    # Region mapping
    def _region(node_id: str) -> str:
        if node_id.startswith("uk:"):
            return "🇬🇧 UK"
        if node_id.startswith("de:"):
            return "🇩🇪 DE"
        if node_id.startswith("fr:"):
            return "🇫🇷 FR"
        if node_id.startswith("es:"):
            return "🇪🇸 ES"
        return "🇺🇸 US"

    # Aggregate by region
    region_order = ["🇺🇸 US", "🇩🇪 DE", "🇬🇧 UK", "🇫🇷 FR", "🇪🇸 ES"]
    region_stats: dict[str, dict] = {}
    for r in region_order:
        region_stats[r] = {
            "nodes": 0, "items": 0,
            "title": 0, "price": 0, "rating": 0,
            "fail": 0, "errors": [],
        }

    total_items = 0
    total_title = 0
    total_price = 0
    total_rating = 0
    total_detail = 0

    for run in runs:
        node_id = run.get("node_id", "")
        reg = _region(node_id)
        region_stats[reg]["nodes"] += 1

        if "error" in run:
            region_stats[reg]["fail"] += 1
            region_stats[reg]["errors"].append(run["error"][:60])
            continue

        lc = run.get("list_count", 0)
        snap = run.get("snapshot", {})
        wp = snap.get("with_price", 0)
        wr = snap.get("with_rating", 0)
        dc = run.get("detail_count", 0)

        region_stats[reg]["items"] += lc
        region_stats[reg]["title"] += lc  # list_count = items with title
        region_stats[reg]["price"] += wp
        region_stats[reg]["rating"] += wr
        total_items += lc
        total_title += lc
        total_price += wp
        total_rating += wr
        total_detail += dc

    # Build message
    from datetime import datetime, timezone, timedelta

    kst = timezone(timedelta(hours=9))
    now = datetime.now(kst).strftime("%Y-%m-%d %H:%M")

    def _pct(part: int, whole: int) -> str:
        return f"{part*100//whole}" if whole > 0 else "-"

    lines = [
        f"{icon} Beauty Bestseller 실시간 리포트",
        f"━━━━━━━━━━━━━━━━━━━━━━",
        f"  {now} KST | {minutes:.0f}분 소요",
        "",
    ]

    for reg in region_order:
        s = region_stats[reg]
        if s["nodes"] == 0:
            continue
        t_pct = _pct(s["title"], s["items"])
        p_pct = _pct(s["price"], s["items"])
        r_pct = _pct(s["rating"], s["items"])
        lines.append(f"{reg}  ({s['nodes']}개 카테고리)")
        lines.append(f"  items: {s['items']}개")
        lines.append(f"  title: {s['title']}/{s['items']} ({t_pct}%)")
        lines.append(f"  price: {s['price']}/{s['items']} ({p_pct}%)")
        lines.append(f"  rating: {s['rating']}/{s['items']} ({r_pct}%)")
        lines.append(f"  detail: {total_detail}건 수집")
        if s["fail"] > 0:
            lines.append(f"  ⚠️ 상세크롤 실패: {s['fail']}건")
        lines.append("")

    # Summary
    t_pct = _pct(total_title, total_items)
    p_pct = _pct(total_price, total_items)
    r_pct = _pct(total_rating, total_items)
    total_fail = sum(s["fail"] for s in region_stats.values())
    lines.append("━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"총합: {ok_count}개 성공, {fail_count}개 실패")
    lines.append(f"  items: {total_items}개")
    lines.append(f"  title: {total_title}/{total_items} ({t_pct}%)")
    lines.append(f"  price: {total_price}/{total_items} ({p_pct}%)")
    lines.append(f"  rating: {total_rating}/{total_items} ({r_pct}%)")
    lines.append(f"  detail: {total_detail}건 수집")
    if total_fail > 0:
        lines.append(f"  detail 실패: {total_fail}건 (captcha/차단)")
    lines.append("")
    lines.append(f"📝 Log: {log_path.name}")

    return "\n".join(lines)


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
