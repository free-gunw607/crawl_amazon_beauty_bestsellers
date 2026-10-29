from __future__ import annotations

"""Compare append-only Sheet history with local SQLite; optionally append missing local keys."""

import argparse
import fcntl
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
HISTORY_RANGE = "'root_rank_history'!A2:E"


def _api_retry(method: str, url: str, token: str, *, params: dict | None = None, body: dict | None = None) -> dict:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from crawl_amazon_beauty_bestsellers.mr_publish import _api

    for attempt in range(6):
        try:
            return _api(method, url, token, params=params, body=body)
        except Exception as exc:
            retryable = any(code in str(exc) for code in ("429", "500", "503", "504"))
            if not retryable or attempt == 5:
                raise
            time.sleep(min(60, 2 ** (attempt + 1)))
    raise RuntimeError("unreachable retry state")


def _history_keys(rows: list[list[str]]) -> set[tuple[str, str, str, str]]:
    return {
        tuple(str(row[idx]).strip() for idx in range(4))
        for row in rows
        if len(row) >= 4 and all(str(row[idx]).strip() for idx in range(4))
    }


def _summarize_missing(rows: list[list[str]]) -> dict[str, object]:
    by_region_date = Counter((row[1], row[0]) for row in rows)
    return {
        "missing_rows": len(rows),
        "missing_by_region_date": [
            {"region": region, "date": day, "rows": count}
            for (region, day), count in sorted(by_region_date.items())
        ],
        "sample": [
            {"date": row[0], "region": row[1], "asin": row[2], "rank": row[3]}
            for row in rows[:50]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Append missing local keys without changing existing Sheet rows.")
    args = parser.parse_args()

    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))
    os.environ.setdefault("AMZ_BS_ROOT_SHEETS_ID", SHEET_ID)

    sys.path.insert(0, str(REPO_ROOT / "src"))
    from crawl_amazon_beauty_bestsellers.config import load_settings
    from crawl_amazon_beauty_bestsellers.root_publish import _service_account_access_token, root_history_rows
    from crawl_amazon_beauty_bestsellers.storage.store import Store

    if os.environ.get("AMZ_BS_ROOT_BACKEND", "sa").lower() != "sa":
        raise SystemExit("This repair tool requires AMZ_BS_ROOT_BACKEND=sa to keep the auth path explicit.")
    token = _service_account_access_token()
    settings = load_settings(REPO_ROOT)
    store = Store(settings)
    try:
        local_rows = [row for region in ("us", "de", "uk", "fr", "es") for row in root_history_rows(store, settings, region)]
    finally:
        store.close()

    existing_payload = _api_retry(
        "GET",
        f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{HISTORY_RANGE}",
        token,
        params={"majorDimension": "ROWS"},
    )
    existing_rows = existing_payload.get("values", [])
    existing_keys = _history_keys(existing_rows)
    local_keys = _history_keys(local_rows)
    missing_rows = [row for row in local_rows if tuple(row[:4]) not in existing_keys]
    report = {
        "mode": "apply" if args.apply else "dry_run",
        "spreadsheet": f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
        "local_history_rows": len(local_rows),
        "sheet_history_keys": len(existing_keys),
        "sheet_only_keys_preserved": len(existing_keys - local_keys),
        **_summarize_missing(missing_rows),
        "appended_rows": 0,
    }

    if args.apply and missing_rows:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from run_job import acquire_lock, release_lock

        lock_path = REPO_ROOT / ".agent" / "locks" / "daily_pipeline.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        pipeline_lock = lock_path.open("a+")
        try:
            fcntl.flock(pipeline_lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            pipeline_lock.close()
            raise SystemExit("Daily pipeline lock is held; refusing concurrent history append.")
        holder = acquire_lock()
        if holder is not None:
            fcntl.flock(pipeline_lock.fileno(), fcntl.LOCK_UN)
            pipeline_lock.close()
            raise SystemExit(f"Amazon runner lock is held by PID {holder}; refusing concurrent history append.")
        try:
            for start in range(0, len(missing_rows), 250):
                _api_retry(
                    "POST",
                    f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/'root_rank_history'!A1:append",
                    token,
                    params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                    body={"values": missing_rows[start:start + 250]},
                )
            report["appended_rows"] = len(missing_rows)
        finally:
            release_lock()
            fcntl.flock(pipeline_lock.fileno(), fcntl.LOCK_UN)
            pipeline_lock.close()

        verified_payload = _api_retry(
            "GET",
            f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/{HISTORY_RANGE}",
            token,
            params={"majorDimension": "ROWS"},
        )
        verified_keys = _history_keys(verified_payload.get("values", []))
        report["missing_after"] = len(local_keys - verified_keys)
        if report["missing_after"]:
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 1

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
