from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET3_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
GWS_CONFIG_DIR = str(Path.home() / ".config" / "gws-amazon")
REGIONS = ["US", "DE", "UK", "FR", "ES"]


def _load_env() -> None:
    env_file = REPO_ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.strip() and key.strip() not in os.environ:
            os.environ[key.strip()] = value.strip().strip("\"'")


def _gws_value_payload(range_name: str, env: dict[str, str] | None = None) -> dict[str, object]:
    env = dict(env or os.environ)
    if env.get("AMZ_BS_ROOT_BACKEND", "gws").lower() == "sa":
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from crawl_amazon_beauty_bestsellers.root_publish import _service_account_access_token
        import requests

        response = requests.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET3_ID}/values/{range_name}",
            headers={"Authorization": f"Bearer {_service_account_access_token()}"},
            timeout=60,
        )
        response.raise_for_status()
        return response.json()
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", GWS_CONFIG_DIR)
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    proc = subprocess.run(
        [
            "gws", "sheets", "spreadsheets", "values", "get",
            "--params", json.dumps({"spreadsheetId": SHEET3_ID, "range": range_name}),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[-500:])
    stdout = proc.stdout
    payload = json.loads(stdout[stdout.index("{"):])
    return payload


def _gws_values(range_name: str, env: dict[str, str] | None = None) -> list[list[str]]:
    return _gws_value_payload(range_name, env).get("values", [])


def _history_metrics(payload: dict[str, object]) -> dict[str, object]:
    values = payload.get("values", [])
    rows = [row for row in values if isinstance(row, list) and any(str(cell).strip() for cell in row)]
    data_rows = rows[1:] if rows else []
    range_match = re.search(r":(?:[A-Z]+)(\d+)$", str(payload.get("range", "")))
    physical_last_row = int(range_match.group(1)) if range_match else len(values)
    by_region: dict[str, dict[str, object]] = {}
    daily_asins: dict[tuple[str, str], set[str]] = {}
    all_keys: set[tuple[str, str, str, str]] = set()
    duplicate_keys = 0
    blank_rows = [
        row_num for row_num, row in enumerate(values, start=1)
        if not isinstance(row, list) or not any(str(cell).strip() for cell in row)
    ]
    for row in data_rows:
        if len(row) < 4:
            continue
        day, region, asin, rank = (str(cell).strip() for cell in row[:4])
        if not day or not region or not asin or not rank:
            continue
        key = (day, region.upper(), asin, rank)
        daily_asins.setdefault((day, region.upper()), set()).add(asin)
        if key in all_keys:
            duplicate_keys += 1
        all_keys.add(key)
        current = by_region.setdefault(region.upper(), {"date": "", "rows": 0, "_keys": set()})
        if day > str(current["date"]):
            current.update({"date": day, "rows": 0, "_keys": set()})
        if day == current["date"]:
            current["rows"] = int(current["rows"]) + 1
            current["_keys"].add((asin, rank))
    for current in by_region.values():
        current["unique_keys"] = len(current.pop("_keys"))
    incomplete = [
        {"date": day, "region": region, "unique_asins": len(asins)}
        for (day, region), asins in sorted(daily_asins.items())
        if len(asins) < 100
    ]
    return {
        "rows": len(data_rows),
        "physical_last_row": physical_last_row,
        "blank_rows_within_range": max(0, physical_last_row - 1 - len(data_rows)),
        "newest_date": max((str(row[0]) for row in data_rows if row and str(row[0]).strip()), default=""),
        "latest_by_region": by_region,
        "duplicate_keys": duplicate_keys,
        "blank_row_numbers_sample": blank_rows[:50],
        "date_region_cohorts": len(daily_asins),
        "incomplete_date_region_cohorts": len(incomplete),
        "incomplete_date_region_samples": incomplete[:50],
    }


def _parse_stamp(value: str) -> datetime:
    return datetime.strptime(value.replace(" KST", ""), "%Y-%m-%d %H:%M")


def _send_alert(message: str) -> None:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from run_job import _send_email, _send_telegram

    _send_telegram(message)
    _send_email(f"[Amazon Beauty] watchdog alert {time.strftime('%Y-%m-%d %H:%M KST')}", message)


def _should_alert(signature: str, cooldown_hours: float = 6.0) -> bool:
    state_path = REPO_ROOT / ".agent" / "state" / "watchdog" / "last_alert.json"
    now = time.time()
    previous: dict = {}
    try:
        previous = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        pass
    if previous.get("signature") == signature and now - float(previous.get("sent_at", 0)) < cooldown_hours * 3600:
        return False
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps({"signature": signature, "sent_at": now}), encoding="utf-8")
    return True


def main() -> int:
    _load_env()
    if not os.environ.get("AMZ_BS_ROOT_BACKEND"):
        os.environ["AMZ_BS_ROOT_BACKEND"] = "sa" if os.environ.get("GDRIVE_CREDS") else "gws"
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-age-hours", type=float, default=30.0)
    parser.add_argument("--alert", action="store_true")
    args = parser.parse_args()

    now = datetime.now()
    stale: list[str] = []
    ok: list[str] = []
    for region in REGIONS:
        rows = _gws_values(f"[{region}] Top 100!A1:C1")
        stamp = rows[0][0] if rows and rows[0] else ""
        try:
            stamped_at = _parse_stamp(stamp)
        except ValueError:
            stale.append(f"{region}: invalid stamp `{stamp}`")
            continue
        age = (now - stamped_at).total_seconds() / 3600
        line = f"{region}: {stamp} age={age:.1f}h"
        if age > args.max_age_hours:
            stale.append(line)
        else:
            ok.append(line)

    history_payload = _gws_value_payload("root_rank_history!A:I")
    history_metrics = _history_metrics(history_payload)
    history_count = int(history_metrics["rows"])
    newest_history = str(history_metrics["newest_date"])

    payload = {
        "ok": not stale,
        "checked_at": time.strftime("%Y-%m-%d %H:%M %Z"),
        "sheet": SHEET3_ID,
        "ok_regions": ok,
        "stale_regions": stale,
        "root_rank_history_rows": history_count,
        "root_rank_history_physical_last_row": history_metrics["physical_last_row"],
        "root_rank_history_blank_rows_within_range": history_metrics["blank_rows_within_range"],
        "root_rank_history_newest_date": newest_history,
        "root_rank_history_latest_by_region": history_metrics["latest_by_region"],
        "root_rank_history_duplicate_keys": history_metrics["duplicate_keys"],
        "root_rank_history_blank_row_numbers_sample": history_metrics["blank_row_numbers_sample"],
        "root_rank_history_date_region_cohorts": history_metrics["date_region_cohorts"],
        "root_rank_history_incomplete_date_region_cohorts": history_metrics["incomplete_date_region_cohorts"],
        "root_rank_history_incomplete_date_region_samples": history_metrics["incomplete_date_region_samples"],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

    if stale and args.alert and _should_alert("stale:" + "|".join(stale)):
        message = "\n".join([
            "⚠️ Amazon Beauty Sheet watchdog alert",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            f"checked_at: {payload['checked_at']}",
            f"Sheet3: https://docs.google.com/spreadsheets/d/{SHEET3_ID}/edit",
            "",
            "stale:",
            *stale,
            "",
            f"root_rank_history rows: {history_count}",
            f"root_rank_history newest date: {newest_history}",
        ])
        _send_alert(message)
    return 1 if stale else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        checked_at = time.strftime("%Y-%m-%d %H:%M %Z")
        error = f"{type(exc).__name__}: {exc}"
        print(json.dumps({
            "ok": False,
            "checked_at": checked_at,
            "sheet": SHEET3_ID,
            "error": error,
        }, ensure_ascii=False, indent=2), file=sys.stderr)
        if "--alert" in sys.argv and _should_alert("error:" + error[:300]):
            _load_env()
            _send_alert("\n".join([
                "ALERT: Amazon Beauty Sheet watchdog failed",
                f"checked_at: {checked_at}",
                "The Sheet could not be verified; this includes OAuth/token failures.",
                f"error: {error[-600:]}",
                f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET3_ID}/edit",
            ]))
        sys.exit(2)
