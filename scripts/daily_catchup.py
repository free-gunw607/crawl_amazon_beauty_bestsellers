from __future__ import annotations

"""Bounded recovery for a missed or partially failed daily Amazon cycle."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REGIONS = ["us", "de", "uk", "fr", "es"]


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env.setdefault(key.strip(), value.strip().strip("\"'"))
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("AMZ_BS_ROOT_BACKEND", "sa" if env.get("GDRIVE_CREDS") else "gws")
    env.setdefault("AMZ_BS_ROOT_SHEETS_ID", "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80")
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", str(Path.home() / ".config" / "gws-amazon"))
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    return env


def _stale_regions(env: dict[str, str]) -> list[str]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from watchdog_sheet import _gws_values, _parse_stamp

    today = datetime.now().date()
    stale: list[str] = []
    for region in REGIONS:
        rows = _gws_values(f"[{region.upper()}] Top 100!A1:C1", env)
        stamp = rows[0][0] if rows and rows[0] else ""
        products = _gws_values(f"[{region.upper()}] Top 100!A5:B104", env)
        valid_rows = [
            row for row in products
            if len(row) >= 2 and str(row[0]).strip().isdigit() and str(row[1]).strip()
        ]
        ranks = {int(row[0]) for row in valid_rows}
        asins = {str(row[1]).strip() for row in valid_rows}
        try:
            if (
                _parse_stamp(stamp).date() != today
                or len(valid_rows) != 100
                or ranks != set(range(1, 101))
                or len(asins) != 100
            ):
                stale.append(region)
        except ValueError:
            stale.append(region)
    return stale


def _title_gaps(env: dict[str, str]) -> dict[str, list[tuple[str, str]]]:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from enrich_titles_until_complete import _sheet_title_count

    gaps: dict[str, list[tuple[str, str]]] = {}
    for region in REGIONS:
        titled, total, missing = _sheet_title_count(region, env)
        if total < 100 or missing:
            gaps[region] = missing
    return gaps


def _latest_completed_run(today: str) -> Path | None:
    root = REPO_ROOT / ".agent" / "state" / "daily_pipeline"
    candidates = sorted(root.glob(f"{today}_*"), reverse=True)
    for candidate in candidates:
        summary = candidate / "root.json"
        if not summary.is_file():
            continue
        try:
            if (candidate / "fallback.json").is_file():
                return candidate
        except (OSError, json.JSONDecodeError):
            continue
    return None


def _failed_root_regions(run_dir: Path | None, env: dict[str, str] | None = None) -> list[str]:
    if run_dir is None:
        return []
    try:
        root = json.loads((run_dir / "root.json").read_text(encoding="utf-8"))
        rows = root.get("regions", [])
        failed = [
            str(row.get("region", "")).lower()
            for row in rows
            if isinstance(row, dict)
            and (int(row.get("crawled", 0) or 0) < 100
                 or int(row.get("published", 0) or 0) < 100
                 or int(row.get("fail", 0) or 0) > 0)
        ]
        if env is None or not root.get("finished"):
            return failed
        from watchdog_sheet import _gws_values, _parse_stamp

        finished = datetime.fromisoformat(str(root["finished"])).astimezone(
            timezone(timedelta(hours=9))
        ).replace(tzinfo=None)
        still_stale: list[str] = []
        for region in failed:
            rows = _gws_values(f"[{region.upper()}] Top 100!A1:C1", env)
            stamp = rows[0][0] if rows and rows[0] else ""
            try:
                if _parse_stamp(stamp) < finished:
                    still_stale.append(region)
            except ValueError:
                still_stale.append(region)
        return still_stale
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return []


def _recent_root_block(run_dir: Path | None, now: float | None = None) -> bool:
    if run_dir is None:
        return False
    try:
        root = json.loads((run_dir / "root.json").read_text(encoding="utf-8"))
        log_path = Path(str(root.get("log", "")))
        if not log_path.is_file():
            return False
        age = (time.time() if now is None else now) - log_path.stat().st_mtime
        if age >= 55 * 60:
            return False
        text = log_path.read_text(encoding="utf-8", errors="replace").lower()
        return any(marker in text for marker in ("captcha", "robot check", "automated access", "request blocked", '"blocked"'))
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _recent_marketplace_block(run_dir: Path, now: float | None = None) -> bool:
    titles_path = run_dir / "titles.json"
    try:
        summary = json.loads(titles_path.read_text(encoding="utf-8"))
        rows = summary.get("regions", [])
        blocked = any(isinstance(row, dict) and row.get("blocked") for row in rows)
        age = (time.time() if now is None else now) - titles_path.stat().st_mtime
        return blocked and age < 55 * 60
    except (OSError, json.JSONDecodeError, TypeError):
        return False


def _fallback_missing_drive(run_dir: Path | None) -> bool:
    if run_dir is None:
        return True
    try:
        summary = json.loads((run_dir / "fallback.json").read_text(encoding="utf-8"))
        drive = summary.get("drive")
        workbook = Path(str(summary.get("xlsx", "")))
        return not workbook.is_file() or not isinstance(drive, dict) or not bool(drive.get("file_id"))
    except (OSError, json.JSONDecodeError, TypeError):
        return True


def _pending_recovery_alert(
    gaps: dict[str, list[tuple[str, str]]],
    drive_gap: bool,
    state: dict[str, object],
) -> dict[str, object]:
    now = time.time()
    last = float(state.get("recovery_alert_epoch", 0) or 0)
    if now - last < 6 * 60 * 60:
        print("[catchup] unresolved title alert cooldown active", flush=True)
        return state
    lines = ["Amazon Beauty daily recovery is still incomplete."]
    lines.extend(f"{region.upper()}: {len(missing)} blank title(s)" for region, missing in gaps.items())
    if drive_gap:
        lines.append("Fallback XLSX is not confirmed in Drive.")
    lines.append("Automatic recovery will retry the remaining delivery gaps on the next catch-up interval.")
    message = "\n".join(lines)
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from run_job import _send_email, _send_telegram

        sent, detail = _send_email("[Amazon Beauty] recovery pending", message)
        if not sent:
            _send_telegram(f"⚠️ {message}\nEmail: {detail}")
        else:
            _send_telegram(message)
    except Exception as exc:
        print(f"[catchup] pending title alert failed: {exc}", flush=True)
    state["recovery_alert_epoch"] = now
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--not-before-hour", type=int, default=5)
    parser.add_argument("--email", action="store_true")
    args = parser.parse_args()
    if datetime.now().hour < args.not_before_hour:
        return 0

    env = _env()
    state_dir = REPO_ROOT / ".agent" / "state" / "catchup"
    state_path = state_dir / f"{datetime.now():%Y%m%d}.json"
    try:
        stale = _stale_regions(env)
        gaps = _title_gaps(env)
    except Exception as exc:
        previous = {}
        if state_path.is_file():
            try:
                previous = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                previous = {}
        now = time.time()
        last_error_at = float(previous.get("last_error_epoch", 0) or 0)
        if now - last_error_at >= 6 * 60 * 60:
            print(f"[catchup] Sheet check unavailable; deferring recovery: {exc}", flush=True)
            last_error_at = now
        else:
            print("[catchup] Sheet check remains unavailable; alert cooldown active", flush=True)
        state_dir.mkdir(parents=True, exist_ok=True)
        state_path.write_text(
            json.dumps({"status": "sheet_check_unavailable", "last_error_epoch": last_error_at,
                        "last_error": f"{type(exc).__name__}: {exc}"}),
            encoding="utf-8",
        )
        return 0
    latest_run = _latest_completed_run(datetime.now().strftime("%Y%m%d"))
    failed_regions = _failed_root_regions(latest_run, env)
    stale = sorted((set(stale) | (set(failed_regions) & set(REGIONS))), key=REGIONS.index)
    # No local run means this node cannot prove that its local fallback is stale
    # or missing. The shared live Sheet is the cross-node source of truth.
    drive_gap = _fallback_missing_drive(latest_run) if latest_run else False
    if not stale and not gaps and not drive_gap:
        print("[catchup] all regional tabs are current and titles are complete")
        return 0

    # Retry stale regional data after the same 55-minute floor used for Amazon
    # block recovery. This continues until the Sheet is current without firing
    # repeated full crawls every minute.
    previous: dict[str, object] = {}
    if state_path.is_file():
        try:
            previous = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            previous = {}
    if stale:
        if _recent_root_block(latest_run):
            print("[catchup] recent Amazon block detected in the last root run; waiting for 55-minute cooldown", flush=True)
            if gaps or drive_gap:
                previous = _pending_recovery_alert(gaps, drive_gap, previous)
                state_path.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
            return 0
        last_attempt = float(previous.get("stale_attempt_epoch", 0) or 0)
        if time.time() - last_attempt < 55 * 60:
            print("[catchup] stale-list recovery cooldown active", flush=True)
            if gaps or drive_gap:
                previous = _pending_recovery_alert(gaps, drive_gap, previous)
                state_path.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
            return 0
    state_dir.mkdir(parents=True, exist_ok=True)
    if stale:
        state_path.write_text(
            json.dumps({**previous, "status": "attempted", "attempted_at": datetime.now().isoformat(), "stale_attempt_epoch": time.time(), "stale_regions": stale}),
            encoding="utf-8",
        )
        print(f"[catchup] recovering stale regions: {','.join(stale)}", flush=True)
        recovery = subprocess.run(
            [sys.executable, "scripts/run_daily_pipeline.py", "--trigger", "catchup", "--regions", *[region.upper() for region in stale]],
            cwd=REPO_ROOT,
            env=env,
        )
        return recovery.returncode

    run_dir = latest_run
    if run_dir is None:
        if stale:
            print("[catchup] stale live regions need a full crawl; no same-day run is available", flush=True)
            recovery = subprocess.run(
                [sys.executable, "scripts/run_daily_pipeline.py", "--trigger", "catchup", "--regions", *[region.upper() for region in stale]],
                cwd=REPO_ROOT,
                env=env,
            )
            return recovery.returncode
        print("[catchup] live Sheet is current; recovering title gaps without recrawling root lists", flush=True)
        recovery = subprocess.run(
            [sys.executable, "scripts/enrich_titles_until_complete.py", "--regions", *REGIONS,
             "--max-rounds", "4", "--sleep-sec", "45", "--max-sleep-sec", "300", "--no-backfill-history", "--alert"],
            cwd=REPO_ROOT,
            env=env,
        )
        return recovery.returncode

    if gaps and _recent_marketplace_block(run_dir):
        print("[catchup] Amazon block cooldown is active; title recovery will resume after 55 minutes", flush=True)
        return 0

    print(f"[catchup] resuming title gaps without recrawling: {run_dir}", flush=True)
    recovery = subprocess.run(
        [sys.executable, "scripts/run_daily_pipeline.py", "--trigger", "catchup", "--resume-existing", str(run_dir), "--silent-incomplete"],
        cwd=REPO_ROOT,
        env=env,
    )
    if recovery.returncode != 0:
        previous = _pending_recovery_alert(gaps, drive_gap, previous)
    previous.update({"title_recovery_checked_at": datetime.now().isoformat(), "title_recovery_returncode": recovery.returncode})
    state_path.write_text(json.dumps(previous, ensure_ascii=False), encoding="utf-8")
    return recovery.returncode


if __name__ == "__main__":
    raise SystemExit(main())
