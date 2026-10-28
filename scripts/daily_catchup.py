from __future__ import annotations

"""Bounded recovery for a missed or partially failed daily Amazon cycle."""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
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
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", "/home/liam/agent-coding/agent-system/A3-runtime-standards/local-config/gws")
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
        try:
            if _parse_stamp(stamp).date() != today:
                stale.append(region)
        except ValueError:
            stale.append(region)
    return stale


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
    if not stale:
        print("[catchup] all regional tabs already have today's stamp")
        return 0

    # A stale Sheet can persist through an infrastructure outage.  One bounded
    # recovery attempt per host/day avoids an hourly sequence of identical
    # crawl failures and duplicate emails.
    if state_path.is_file() and json.loads(state_path.read_text(encoding="utf-8")).get("status") == "attempted":
        print(f"[catchup] already attempted today: {state_path}")
        return 0
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps({"status": "attempted", "attempted_at": datetime.now().isoformat(), "stale_regions": stale}),
        encoding="utf-8",
    )

    print(f"[catchup] recovering stale regions: {','.join(stale)}", flush=True)
    # A takeover must run every completion step, not just the live-list upload.
    # Otherwise a missed primary run leaves titles, history maintenance, fallback,
    # and the final delivery incomplete even though the top-100 tabs look fresh.
    recovery = subprocess.run(
        [sys.executable, "scripts/run_daily_pipeline.py", "--trigger", "catchup"],
        cwd=REPO_ROOT,
        env=env,
    )
    return recovery.returncode


if __name__ == "__main__":
    raise SystemExit(main())
