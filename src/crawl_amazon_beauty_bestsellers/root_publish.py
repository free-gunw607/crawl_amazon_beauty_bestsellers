"""Sheet 3 publisher: Beauty & Personal Care Top 100 per marketplace.

Dedicated spreadsheet "beauty_personal_care_top100_live":
  - "[XX] Top 100"   current full ranked snapshot (1..100)
  - "root_rank_history"  append-only daily accumulation (time-series source view)
  - "trend_14d"      rolling window with prev_rank/delta

Root snapshots are stored in SQLite under synthetic keys ("ROOT", "<mp>:ROOT")
so local accumulation survives independent of the sheet.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import Settings
from .mr_publish import _api, _chunk_rows
from .sheets_publish import SheetsPublishError, _grid_resize_requests, _sheet_meta_sa, oauth_access_token

ROOT_TITLE = "beauty_personal_care_top100_live"
STATE_REL = ".agent/state/root_sheet_id.json"
HISTORY_TAB = "root_rank_history"
HISTORY_HEADER = ["date", "region", "asin", "rank", "price_krw", "currency", "rating", "ratings_count", "title"]
TREND_HEADER = ["day", "region", "asin", "best_rank", "prev_rank", "delta", "snapshots"]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M %Z")


def ensure_root_spreadsheet(settings: Settings, token: str) -> str:
    state_path = settings.resolve(STATE_REL)
    if state_path.exists():
        existing = state_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    env_id = os.environ.get("AMZ_BS_ROOT_SHEETS_ID", "")
    if env_id:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(env_id, encoding="utf-8")
        return env_id
    last_error: Exception | None = None
    sheet_id = ""
    for attempt in range(4):
        try:
            created = _api("POST", "https://sheets.googleapis.com/v4/spreadsheets", token, body={
                "properties": {"title": ROOT_TITLE},
            })
            sheet_id = created["spreadsheetId"]
            break
        except SheetsPublishError as exc:
            last_error = exc
            if not any(code in str(exc) for code in ("503", "429", "500")):
                raise
            time.sleep(5 * (attempt + 1))
    if not sheet_id:
        raise last_error or SheetsPublishError("root spreadsheet create failed")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(sheet_id, encoding="utf-8")
    return sheet_id


def root_key(region: str) -> str:
    return "ROOT" if region == "us" else f"{region}:ROOT"


def root_panel_grid(store, settings: Settings, region: str) -> list[list[str]]:
    profile = settings.marketplace(region)
    base_url = profile.base_url if profile else "https://www.amazon.com"
    snapshot = store.latest_snapshot(root_key(region))
    grid = [["fetched", "", "", "", "", "", ""],
            [f"{base_url}/gp/bestsellers/beauty/", "", "", "", "", "", ""],
            ["rank", "asin", "title", "rating", "ratings_count", "price_krw", "url"]]
    for row in sorted(snapshot, key=lambda r: r["rank"]):
        grid.append([
            str(row.get("rank") or ""), str(row.get("asin") or ""),
            str(row.get("title") or "")[:150],
            str(row.get("rating") or ""), str(row.get("ratings_count") or ""),
            str(row.get("price_amount") or ""), str(row.get("url") or ""),
        ])
    return grid


def root_history_rows(store, settings: Settings, region: str) -> list[list[str]]:
    profile = settings.marketplace(region)
    tz = ZoneInfo(profile.timezone if profile else "UTC")
    best: dict[tuple[str, str], dict] = {}
    for row in store.region_daily_best(region):
        if row["node_id"] != root_key(region):
            continue
        try:
            day = datetime.fromisoformat(row["fetched_at"]).astimezone(tz).date().isoformat()
        except ValueError:
            day = row["fetched_at"][:10]
        key = (day, row["asin"])
        cur = best.get(key)
        if cur is None or row["best_rank"] < cur["best_rank"]:
            best[key] = {**row, "day": day}
    snap_by_asin = {r.get("asin"): r for r in store.latest_snapshot(root_key(region))}
    out: list[list[str]] = []
    for (day, asin), row in sorted(best.items()):
        meta = snap_by_asin.get(asin, {})
        out.append([
            day, region.upper(), asin, str(row["best_rank"]),
            str(meta.get("price_amount") or ""), str(meta.get("price_currency") or "KRW"),
            str(meta.get("rating") or ""), str(row.get("max_ratings") or ""),
            str(meta.get("title") or "")[:140],
        ])
    return out


def root_trend_grid(store, settings: Settings, region: str, days: int = 14) -> list[list[str]]:
    profile = settings.marketplace(region)
    tz = ZoneInfo(profile.timezone if profile else "UTC")
    daily: dict[str, dict[str, int]] = {}
    snaps: dict[str, dict[str, int]] = {}
    for row in store.region_daily_best(region):
        if row["node_id"] != root_key(region):
            continue
        try:
            day = datetime.fromisoformat(row["fetched_at"]).astimezone(tz).date().isoformat()
        except ValueError:
            day = row["fetched_at"][:10]
        per_day = daily.setdefault(row["asin"], {})
        if day not in per_day or row["best_rank"] < per_day[day]:
            per_day[day] = row["best_rank"]
        s = snaps.setdefault(row["asin"], {}).setdefault(day, 0)
        s += row["snapshots"]
    all_days = sorted({d for per in daily.values() for d in per})
    recent = set(all_days[-days:])
    grid = [TREND_HEADER]
    for asin, per in daily.items():
        chain = sorted(per.items())
        for idx, (day, rank) in enumerate(chain):
            if day not in recent:
                continue
            prev_rank = chain[idx - 1][1] if idx > 0 else None
            delta = (prev_rank - rank) if prev_rank is not None else ""
            grid.append([day, region.upper(), asin, str(rank),
                         str(prev_rank or ""), str(delta), str(snaps[asin].get(day, 0))])
    body = grid[1:]
    body.sort(key=lambda r: (r[0], int(r[3])))
    grid = [grid[0]] + body
    return grid


def publish_root_region(settings: Settings, store, region: str, token: str | None = None) -> dict:
    tok = token or oauth_access_token()
    sheet_id = ensure_root_spreadsheet(settings, tok)
    meta = _sheet_meta_sa(sheet_id, tok)

    tabs = {
        f"[{region.upper()}] Top 100": root_panel_grid(store, settings, region),
        "trend_14d": root_trend_grid(store, settings, region),
        HISTORY_TAB: [HISTORY_HEADER],
    }
    changes: list[dict] = []
    for title, grid in tabs.items():
        changes += _grid_resize_requests(title, meta.get(title), rows=len(grid) + 200, cols=max(9, max(len(r) for r in grid)))
    if changes:
        _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate", tok,
             body={"requests": changes})
        meta = _sheet_meta_sa(sheet_id, tok)

    stamp = [_now(), f"region={region.upper()}", "auto"]
    for title, grid in tabs.items():
        if title == HISTORY_TAB:
            continue
        _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchUpdate", tok,
             params={"valueInputOption": "USER_ENTERED"},
             body={"valueInputOption": "USER_ENTERED",
                   "data": [{"range": f"'{title}'!A1", "values": [stamp + [""] * 6] + grid}]})

    history_new = root_history_rows(store, settings, region)
    appended = len(history_new)
    if appended:
        known = set()
        existing = _api("GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/'{HISTORY_TAB}'!A2:E", tok,
                        params={"majorDimension": "ROWS"})
        for row in existing.get("values", []):
            if len(row) >= 4:
                known.add((row[0], row[1], row[2], row[3]))
        fresh = [r for r in history_new if (r[0], r[1], r[2], r[3]) not in known]
        appended = len(fresh)
        for chunk in _chunk_rows(fresh):
            _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/'{HISTORY_TAB}'!A1:append",
                 tok, params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                 body={"values": chunk})
    return {"backend": "token", "sheet": sheet_id, "region": region.upper(), "history_appended": appended}
