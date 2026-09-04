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

REGIONS = ["us", "de", "uk", "fr", "es"]
REGION_NAMES = {"us": "🇺🇸 US", "de": "🇩🇪 DE", "uk": "🇬🇧 UK", "fr": "🇫🇷 FR", "es": "🇪🇸 ES"}


def _send_telegram(message: str) -> None:
    """Send a Telegram notification if TG_BOT_TOKEN and TG_CHAT_ID are set."""
    token = os.environ.get("TG_BOT_TOKEN", "")
    chat_id = os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("  [telegram] TG_BOT_TOKEN or TG_CHAT_ID not set, skipping", flush=True)
        return
    try:
        result = subprocess.run(
            ["bash", str(NOTIFY_SCRIPT), message],
            timeout=15,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  [telegram] send failed rc={result.returncode}: {result.stderr.strip()}", flush=True)
    except Exception as e:
        print(f"  [telegram] exception: {e}", flush=True)


def _build_report(status: str, results: list[dict], elapsed: float, log_path: Path) -> str:
    """Build a Telegram briefing for root-cycle runs."""
    icon = "✅" if status == "completed" else "❌"
    sec = int(elapsed)
    minutes = sec // 60
    secs = sec % 60

    from datetime import datetime, timezone, timedelta
    kst = timezone(timedelta(hours=9))
    utc = timezone.utc
    now_kst = datetime.now(kst)
    now_utc = datetime.now(utc)
    # Amazon US server time (EDT = UTC-4, EST = UTC-5)
    now_edt = now_utc - timedelta(hours=4)

    total_crawled = 0
    total_published = 0
    total_titles_filled = 0
    total_fill_missing = 0
    total_fill_noprice = 0
    total_fail = 0

    # DB stats (with product_details enrichment, matching Sheet3 behavior)
    import sqlite3
    db_path = REPO_ROOT / "artifacts" / "db" / "bestsellers.sqlite"
    db_stats: dict[str, dict] = {}
    if db_path.exists():
        try:
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            for r in results:
                region = r["region"]
                key = "ROOT" if region == "us" else f"{region}:ROOT"
                latest = conn.execute(
                    "SELECT run_id FROM list_entries WHERE node_id=? ORDER BY fetched_at DESC LIMIT 1",
                    (key,)
                ).fetchone()
                if latest:
                    # product_details에서 ASIN별 최신 기록1건만 가져오는 서브쿼리
                    row = conn.execute(
                        "SELECT COUNT(DISTINCT le.asin) as cnt, "
                        "SUM(CASE WHEN le.title != '' AND le.title IS NOT NULL "
                        "  THEN 1 WHEN pd.title != '' AND pd.title IS NOT NULL THEN 1 ELSE 0 END) as titled, "
                        "SUM(CASE WHEN le.rating IS NOT NULL THEN 1 WHEN pd.rating IS NOT NULL THEN 1 ELSE 0 END) as rated, "
                        "SUM(CASE WHEN le.price_amount IS NOT NULL THEN 1 "
                        "  WHEN pd.buy_box_price IS NOT NULL THEN 1 WHEN pd.list_price_amount IS NOT NULL THEN 1 "
                        "  ELSE 0 END) as priced "
                        "FROM list_entries le "
                        "LEFT JOIN ("
                        "  SELECT asin, title, rating, buy_box_price, list_price_amount "
                        "  FROM product_details "
                        "  WHERE (asin, fetched_at) IN (SELECT asin, MAX(fetched_at) FROM product_details GROUP BY asin)"
                        ") pd ON le.asin = pd.asin "
                        "WHERE le.node_id=? AND le.run_id=?",
                        (key, latest["run_id"])
                    ).fetchone()
                    db_stats[region] = {
                        "cnt": row["cnt"] or 0,
                        "titled": row["titled"] or 0,
                        "rated": row["rated"] or 0,
                        "priced": row["priced"] or 0,
                    }
            conn.close()
        except Exception:
            pass

    lines = [
        f"{icon} Amazon Beauty Bestseller 리포트",
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"  {now_kst.strftime('%Y-%m-%d %H:%M')} KST | {minutes}분{secs}초 소요",
        f"  Amazon 서버: {now_edt.strftime('%Y-%m-%d %H:%M')} EDT (미국동부)",
        "",
    ]

    for r in results:
        region = REGION_NAMES.get(r["region"], r["region"])
        crawled = r.get("crawled", 0)
        published = r.get("published", 0)
        titles_filled = r.get("titles_filled", 0)
        fill_missing = r.get("fill_missing", 0)
        fill_noprice = r.get("fill_noprice", 0)
        fail = r.get("fail", 0)

        total_crawled += crawled
        total_published += published
        total_titles_filled += titles_filled
        total_fill_missing += fill_missing
        total_fill_noprice += fill_noprice
        total_fail += fail

        # DB stats for this region
        stats = db_stats.get(r["region"], {})
        cnt = stats.get("cnt", crawled)
        titled = stats.get("titled", 0)
        rated = stats.get("rated", 0)
        priced = stats.get("priced", 0)

        title_pct = f"{titled*100//cnt}%" if cnt else "-"
        rate_pct = f"{rated*100//cnt}%" if cnt else "-"
        price_pct = f"{priced*100//cnt}%" if cnt else "-"

        lines.append(f"{region}")
        lines.append(f"  수집: {crawled}건 | Sheet3 반영: {published}건")
        lines.append(f"  제목: {title_pct} ({titled}/{cnt}) | 평점: {rate_pct} | 가격: {price_pct}")
        if titles_filled > 0:
            lines.append(f"  제목보강: {titles_filled}건")
        if fill_missing > 0:
            lines.append(f"  상세보강: {fill_missing}건")
        if fill_noprice > 0:
            lines.append(f"  가격보강: {fill_noprice}건")
        if fail > 0:
            lines.append(f"  ⚠️ 실패: {fail}건")
        lines.append("")

    # Total DB stats
    total_cnt = sum(s.get("cnt", 0) for s in db_stats.values())
    total_titled = sum(s.get("titled", 0) for s in db_stats.values())
    total_rated = sum(s.get("rated", 0) for s in db_stats.values())
    total_priced = sum(s.get("priced", 0) for s in db_stats.values())

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"총합: {total_crawled}건 수집 → {total_published}건 Sheet3 반영")
    if total_cnt:
        t_pct = f"{total_titled*100//total_cnt}%" if total_cnt else "-"
        lines.append(f"  제목: {total_titled}/{total_cnt} ({t_pct}) | 평점: {total_rated} | 가격: {total_priced}")
    if total_titles_filled > 0:
        lines.append(f"  + 제목보강 {total_titles_filled}건")
    if total_fill_missing > 0 or total_fill_noprice > 0:
        lines.append(f"  + 상세보강 {total_fill_missing + total_fill_noprice}건")
    if total_fail > 0:
        lines.append(f"  ⚠️ 실패 {total_fail}건")
    lines.append("")
    lines.append("⏰ 타이머: 다음 실행 내일 05:00 KST")
    lines.append(f"📊 Sheet3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit")
    lines.append(f"📝 Log: {log_path.name}")
    lines.append("")
    lines.append("* 제목보강 = ROOT 페이지에서 제목을 못 받은ASIN들의 개별 상품 페이지(/dp/ASIN)에서 제목을 가져오는 과정")

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


def _run_cli(args: list[str], env: dict) -> tuple[int, str, str]:
    """Run a CLI command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "crawl_amazon_beauty_bestsellers.cli"] + args
    proc = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


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

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    start_ts = time.time()
    print(f"[{started}] run_job start: root-cycle5 regions + fill-gaps")
    alert = _check_staleness()
    if alert:
        print(f"[{started}] {alert}")

    all_results: list[dict] = []
    all_stdout_lines: list[str] = []
    all_stderr_lines: list[str] = []
    overall_rc = 0

    # Phase 1: root-cycle for each region (list crawl + Sheet 3 publish)
    for region in REGIONS:
        region_label = REGION_NAMES[region]
        print(f"  [{region_label}] root-cycle...")
        rc, stdout, stderr = _run_cli(["root-cycle", "--region", region], env)
        all_stdout_lines.append(stdout)
        all_stderr_lines.append(stderr)

        result = {"region": region, "crawled": 0, "published": 0, "titles_filled": 0, "fail": 0}
        for line in stdout.strip().splitlines():
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if "crawled" in obj:
                    result["crawled"] = obj["crawled"]
                if "published" in obj:
                    result["published"] = obj["published"]
                elif "history_appended" in obj:
                    result["published"] = obj["history_appended"]
            except (json.JSONDecodeError, KeyError):
                pass
        if rc != 0 and rc != 4:
            result["fail"] = 1
            overall_rc = 1
        elif rc == 4:
            result["fail"] = 1
            result["crawled"] = 0

        # Phase 1.5: fill titles for this region
        if result["crawled"] > 0:
            print(f"  [{region_label}] fill-titles...")
            rc_t, stdout_t, stderr_t = _run_cli(["fill-titles", "--region", region], env)
            all_stdout_lines.append(stdout_t)
            all_stderr_lines.append(stderr_t)
            for line in stdout_t.strip().splitlines():
                try:
                    obj = json.loads(line)
                    if not isinstance(obj, dict):
                        continue
                    if "filled" in obj:
                        result["titles_filled"] = obj["filled"]
                except (json.JSONDecodeError, KeyError):
                    pass

        all_results.append(result)

    # Phase 2: fill-gaps for detail enrichment (optional, controlled by --no-detail)
    if not args.no_detail:
        print("  fill-gaps --region all ...")
        rc, stdout, stderr = _run_cli(["fill-gaps", "--region", "all"], env)
        all_stdout_lines.append(stdout)
        all_stderr_lines.append(stderr)

        for line in stdout.strip().splitlines():
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                region = obj.get("region", "").lower()
                r = next((x for x in all_results if x["region"] == region), None)
                if r:
                    if "missing" in obj:
                        r["fill_missing"] = obj["missing"]
                    if "noprice_us" in obj:
                        r["fill_noprice"] = obj["noprice_us"]
                    if "noprice_local" in obj:
                        r["fill_noprice"] = r.get("fill_noprice", 0) + obj["noprice_local"]
            except (json.JSONDecodeError, KeyError):
                pass

    elapsed = time.time() - start_ts
    stdout_combined = "\n".join(all_stdout_lines)
    stderr_combined = "\n".join(all_stderr_lines)
    log_path.write_text(
        "\n".join([f"# started {started}", "# stdout", stdout_combined, "# stderr", stderr_combined]),
        encoding="utf-8",
    )
    release_lock()

    finished = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    status = "completed" if overall_rc == 0 else "failed"
    print(f"[{finished}] run_job {status} rc={overall_rc} log={log_path}")

    # Send Telegram briefing
    report = _build_report(status, all_results, elapsed, log_path)
    _send_telegram(report)

    return overall_rc


if __name__ == "__main__":
    sys.exit(main())
