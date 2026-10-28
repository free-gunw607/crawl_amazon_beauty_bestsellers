from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCK_PATH = REPO_ROOT / ".agent" / "locks" / "run_job.lock"
LOG_DIR = REPO_ROOT / ".agent" / "logs"
NOTIFY_SCRIPT = REPO_ROOT / "scripts" / "notify_telegram.sh"
ENV_FILE = REPO_ROOT / ".env"
SHEET3_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
GWS_CONFIG_DIR = str(Path.home() / ".config" / "gws-amazon")
NOTIFY_ENV_FILES = [
    ENV_FILE,
    Path.home() / "agent-coding/agent-system/A3-runtime-standards/local-config/secrets/email/smtp.env",
    Path.home() / ".config/a4-mailer/smtp.env",
    Path.home() / "telegram_filtered_forwarder/.env",
    Path.home() / "agent-coding/agent-projects/A4-worker-repos/telegram_filtered_forwarder/.env",
    Path.home() / "agent-coding/agent-projects/A4-worker-repos/build_ops_powerhouse/.env",
    Path.home() / "agent-coding/agent-projects/A4-worker-repos/capture_finance_pdf_news/.env",
]

E_LOCK_CONFLICT = 11
E_NO_ACTIVE_NODES = 12
E_RUN_FAILED = 13

REGIONS = ["us", "de", "uk", "fr", "es"]
REGION_NAMES = {"us": "🇺🇸 US", "de": "🇩🇪 DE", "uk": "🇬🇧 UK", "fr": "🇫🇷 FR", "es": "🇪🇸 ES"}


def _load_env_file(path: Path, allowed_keys: set[str] | None = None) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip("\"'")
        if allowed_keys is not None and key not in allowed_keys:
            continue
        if key and key not in os.environ:
            os.environ[key] = value


def _load_notification_env() -> None:
    """Load gitignored notification env files without printing secret values."""
    _load_env_file(ENV_FILE)
    shared_keys = {
        "TG_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "BOT_TOKEN", "TG_CHAT_ID",
        "TELEGRAM_CHAT_ID", "TELEGRAM_ALERT_CHAT_ID", "CHAT_ID",
    }
    for path in NOTIFY_ENV_FILES[1:]:
        _load_env_file(path, shared_keys)


def _send_telegram(message: str) -> None:
    """Send a Telegram notification when a known token/chat env pair is set."""
    _load_notification_env()
    token = (
        os.environ.get("TG_BOT_TOKEN")
        or os.environ.get("TELEGRAM_BOT_TOKEN")
        or os.environ.get("BOT_TOKEN")
        or ""
    )
    chat_id = (
        os.environ.get("TG_CHAT_ID")
        or os.environ.get("TELEGRAM_CHAT_ID")
        or os.environ.get("TELEGRAM_ALERT_CHAT_ID")
        or os.environ.get("CHAT_ID")
        or ""
    )
    if not token or not chat_id:
        print("  [telegram] token/chat env not set, skipping", flush=True)
        return
    try:
        env = dict(os.environ)
        env["TG_BOT_TOKEN"] = token
        env["TG_CHAT_ID"] = chat_id
        result = subprocess.run(
            ["bash", str(NOTIFY_SCRIPT), message],
            timeout=15,
            capture_output=True,
            text=True,
            env=env,
        )
        if result.returncode != 0:
            print(f"  [telegram] send failed rc={result.returncode}: {result.stderr.strip()}", flush=True)
    except Exception as e:
        print(f"  [telegram] exception: {e}", flush=True)


def _send_email(subject: str, body: str, attachments: list[Path] | None = None) -> tuple[bool, str]:
    """Send operational reports through the shared SMTP transport only."""
    _load_notification_env()
    env = dict(os.environ)
    recipients = [
        item.strip()
        for item in (
            os.environ.get("AMZ_BS_NOTIFY_EMAIL_TO")
            or os.environ.get("EMAIL_TO")
            or ""
        ).replace(";", ",").split(",")
        if item.strip()
    ]
    if not recipients:
        print("  [email] no recipient found (set AMZ_BS_NOTIFY_EMAIL_TO), not sent", flush=True)
        return False, "no_recipient_configured"

    attachments = attachments or []
    shared_ops = Path.home() / "agent-coding/agent-system/A3-runtime-standards/ops-scripts"
    if shared_ops.is_dir():
        sys.path.insert(0, str(shared_ops))
    from shared_mailer import load_email_config, send_email

    smtp_config = load_email_config(env)
    for key, legacy_key in {
        "SMTP_HOST": "AMZ_BS_SMTP_HOST", "SMTP_PORT": "AMZ_BS_SMTP_PORT",
        "SMTP_USER": "AMZ_BS_SMTP_USER", "SMTP_PASSWORD": "AMZ_BS_SMTP_PASSWORD",
        "EMAIL_FROM": "AMZ_BS_SMTP_FROM", "SMTP_STARTTLS": "AMZ_BS_SMTP_STARTTLS",
    }.items():
        if os.environ.get(legacy_key):
            smtp_config[key] = os.environ[legacy_key]
    sent, detail = send_email(subject, body, recipients, attachments or [], smtp_config)
    if sent:
        print(f"  [email] sent via shared SMTP to {len(recipients)} recipient(s)", flush=True)
    else:
        print(f"  [email] shared SMTP failed ({detail}); Gmail OAuth is not used for operational mail", flush=True)
    return sent, detail


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
    total_history_appended = 0
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
        history_appended = r.get("history_appended", 0)
        titles_filled = r.get("titles_filled", 0)
        fill_missing = r.get("fill_missing", 0)
        fill_noprice = r.get("fill_noprice", 0)
        fail = r.get("fail", 0)

        total_crawled += crawled
        total_published += published
        total_history_appended += history_appended
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
        lines.append(f"  root_rank_history 신규: {history_appended}행")
        lines.append(f"  제목(보정 전): {title_pct} ({titled}/{cnt}) | 평점: {rate_pct} | 가격: {price_pct}")
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
    lines.append(f"  root_rank_history 신규: {total_history_appended}행")
    if total_cnt:
        t_pct = f"{total_titled*100//total_cnt}%" if total_cnt else "-"
        lines.append(f"  제목(보정 전): {total_titled}/{total_cnt} ({t_pct}) | 평점: {total_rated} | 가격: {total_priced}")
    if total_titles_filled > 0:
        lines.append(f"  + 제목보강 {total_titles_filled}건")
    if total_fill_missing > 0 or total_fill_noprice > 0:
        lines.append(f"  + 상세보강 {total_fill_missing + total_fill_noprice}건")
    if total_fail > 0:
        lines.append(f"  ⚠️ 실패 {total_fail}건")
    lines.append("")
    lines.append("⏰ 타이머: 다음 실행 내일 05:00 KST")
    lines.append(f"📊 Sheet3: https://docs.google.com/spreadsheets/d/{SHEET3_ID}/edit")
    lines.append(f"📝 Log: {log_path.name}")
    lines.append("")
    lines.append("* 제목은 05:20 실제 Sheet 빈칸 보정 후 별도 완료 보고에서 최종 100/100을 확인합니다.")

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
    _load_env_file(ENV_FILE)


def _run_cli(args: list[str], env: dict, timeout_sec: int = 900) -> tuple[int, str, str]:
    """Run a CLI command and return (returncode, stdout, stderr)."""
    cmd = [sys.executable, "-m", "crawl_amazon_beauty_bestsellers.cli"] + args
    try:
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout_sec,
        )
    except subprocess.TimeoutExpired as exc:
        return 124, exc.stdout or "", f"timeout after {timeout_sec}s: {' '.join(args)}"
    return proc.returncode, proc.stdout, proc.stderr


def main() -> int:
    _load_env()
    parser = argparse.ArgumentParser(prog="run_job")
    parser.add_argument("--no-detail", action="store_true")
    parser.add_argument("--no-notify", action="store_true", help="Leave delivery to an enclosing orchestrator.")
    parser.add_argument("--summary-json", type=Path, help="Write the completed run summary for an enclosing report.")
    parser.add_argument(
        "--regions",
        nargs="+",
        choices=REGIONS,
        default=REGIONS,
        help="Limit the cycle to specific regions (used by bounded stale-region recovery).",
    )
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
    env.setdefault("AMZ_BS_ROOT_BACKEND", "gws")
    env.setdefault("AMZ_BS_ROOT_SHEETS_ID", SHEET3_ID)
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", GWS_CONFIG_DIR)
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    started = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    start_ts = time.time()
    selected_regions = args.regions
    mode = "root-cycle only" if args.no_detail else "root-cycle regions + fill-titles + fill-gaps"
    print(f"[{started}] run_job start: {mode}")
    alert = _check_staleness()
    if alert:
        print(f"[{started}] {alert}")

    all_results: list[dict] = []
    all_stdout_lines: list[str] = []
    all_stderr_lines: list[str] = []
    overall_rc = 0

    # Phase 1: root-cycle for each region (list crawl + Sheet 3 publish)
    for region in selected_regions:
        region_label = REGION_NAMES[region]
        print(f"  [{region_label}] root-cycle...")
        rc, stdout, stderr = _run_cli(["root-cycle", "--region", region], env, timeout_sec=600)
        all_stdout_lines.append(stdout)
        all_stderr_lines.append(stderr)

        result = {
            "region": region,
            "crawled": 0,
            "published": 0,
            "history_appended": 0,
            "titles_filled": 0,
            "fail": 0,
        }
        for line in stdout.strip().splitlines():
            try:
                obj = json.loads(line)
                if not isinstance(obj, dict):
                    continue
                if "crawled" in obj:
                    result["crawled"] = obj["crawled"]
                if "published" in obj:
                    result["published"] = obj["published"]
                if "history_appended" in obj:
                    result["history_appended"] = obj["history_appended"]
                    if "published" not in obj:
                        result["published"] = obj["history_appended"]
            except (json.JSONDecodeError, KeyError):
                pass
        if rc != 0 and rc != 4:
            result["fail"] = 1
            overall_rc = 1
        elif rc == 4:
            result["fail"] = 1
            result["crawled"] = 0

        # Phase 1.5: fill titles for this region. The daily cron uses
        # --no-detail so the core Sheet publish cannot be held by /dp/ calls.
        if result["crawled"] > 0 and not args.no_detail:
            print(f"  [{region_label}] fill-titles...")
            rc_t, stdout_t, stderr_t = _run_cli(["fill-titles", "--region", region], env, timeout_sec=240)
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
    if not args.no_detail and selected_regions == REGIONS:
        print("  fill-gaps --region all ...")
        rc, stdout, stderr = _run_cli(["fill-gaps", "--region", "all"], env, timeout_sec=900)
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

    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps(
                {
                    "started": started,
                    "finished": finished,
                    "status": status,
                    "elapsed_seconds": round(elapsed),
                    "regions": all_results,
                    "log": str(log_path),
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    if not args.no_notify:
        report = _build_report(status, all_results, elapsed, log_path)
        _send_telegram(report)
        email_ok, email_detail = _send_email(f"[Amazon Beauty] {status} {time.strftime('%Y-%m-%d %H:%M KST')}", report)
        if not email_ok:
            _send_telegram(f"⚠️ Amazon report email delivery failed: {email_detail}. Check SMTP transport; Google OAuth is not used for mail.")

    return overall_rc


if __name__ == "__main__":
    try:
        code = main()
    except BaseException as exc:
        if isinstance(exc, SystemExit):
            raise
        _load_env()
        msg = "\n".join([
            "❌ Amazon Beauty Bestseller 리포트",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"run_job crashed: {type(exc).__name__}: {exc}",
            f"repo: {REPO_ROOT}",
            f"Sheet3: https://docs.google.com/spreadsheets/d/{SHEET3_ID}/edit",
        ])
        _send_telegram(msg)
        email_ok, email_detail = _send_email(f"[Amazon Beauty] crashed {time.strftime('%Y-%m-%d %H:%M KST')}", msg)
        if not email_ok:
            _send_telegram(f"⚠️ Amazon crash email delivery failed: {email_detail}. Check SMTP transport.")
        release_lock()
        if isinstance(exc, KeyboardInterrupt):
            sys.exit(130)
        raise
    sys.exit(code)
