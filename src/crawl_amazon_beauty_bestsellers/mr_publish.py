"""Multi-region accumulation publisher.

Writes to a dedicated spreadsheet ("crawl_amazon_beauty_bestsellers_multiregion_live"):
  - "[XX] Category" snapshot tabs (overwritten per publish)
  - "rank_history" append-only daily rows (the time-series source of truth view)
  - "trend_14d" rolling window with prev_rank/delta columns

Auth: token backend only (shared OAuth store). Legacy sheet is never touched.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .sheets_publish import (
    SheetsPublishError,
    _chunk_rows,
    _grid_resize_requests,
    _sheet_meta_sa,
    oauth_access_token,
)

MR_TITLE = "crawl_amazon_beauty_bestsellers_multiregion_live"
STATE_REL = ".agent/state/mr_sheet_id.json"
HISTORY_TAB = "rank_history"
HISTORY_HEADER = [
    "date", "region", "category", "node_id", "asin", "rank",
    "price_krw", "currency", "rating", "ratings_count", "title",
]
TREND_HEADER = ["day", "region", "category", "node_id", "asin", "best_rank", "prev_rank", "delta", "snapshots", "max_ratings"]


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M %Z")


def _api(method: str, url: str, token: str, params: dict | None = None, body: dict | None = None) -> dict:
    import requests

    resp = requests.request(
        method, url,
        params=params, json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=300,
    )
    if resp.status_code >= 300:
        raise SheetsPublishError(f"{method} {url.split('?')[0]} failed: {resp.status_code} {resp.text[:200]}")
    return resp.json() if resp.text else {}


def ensure_spreadsheet(settings: Settings, token: str) -> str:
    state_path = settings.resolve(STATE_REL)
    if state_path.exists():
        existing = state_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    env_id = os.environ.get("AMZ_BS_MR_SHEETS_ID", "")
    if env_id:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(env_id, encoding="utf-8")
        return env_id
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            created = _api("POST", "https://sheets.googleapis.com/v4/spreadsheets", token, body={
                "properties": {"title": MR_TITLE},
            })
            sheet_id = created["spreadsheetId"]
            break
        except SheetsPublishError as exc:
            last_error = exc
            if "503" not in str(exc) and "429" not in str(exc) and "500" not in str(exc):
                raise
            time.sleep(5 * (attempt + 1))
    else:
        raise last_error or SheetsPublishError("spreadsheet create failed")
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(sheet_id, encoding="utf-8")
    return sheet_id


def region_nodes(registry, region: str) -> list[dict]:
    if region == "us":
        return [
            e for e in registry.active_nodes()
            if ":" not in str(e.get("node_id"))
        ]
    prefix = f"{region}:"
    return [
        e for e in registry.active_nodes()
        if str(e.get("node_id")).startswith(prefix)
    ]


def _local_day(fetched_at: str, tz: ZoneInfo) -> str:
    try:
        dt = datetime.fromisoformat(fetched_at)
    except ValueError:
        dt = datetime.strptime(fetched_at[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.astimezone(tz).date().isoformat()


def history_rows(store, settings: Settings, registry, region: str) -> list[list[str]]:
    profile = settings.marketplace(region)
    tz = ZoneInfo(profile.timezone if profile else "UTC")
    name_map = {str(e["node_id"]): e.get("name") or "" for e in registry.all_entries()}
    meta_cache: dict[str, dict] = {}
    rows_by_key: dict[tuple[str, str], dict] = {}
    for row in store.region_daily_best(region):
        day = _local_day(row["fetched_at"], tz)
        key = (row["node_id"], row["asin"], day)
        if key not in rows_by_key or row["best_rank"] < rows_by_key[key]["best_rank"]:
            rows_by_key[key] = {**row, "day": day}
    out: list[list[str]] = []
    for (node_key, asin, day), row in sorted(rows_by_key.items(), key=lambda kv: (kv[0][2], kv[0][0], kv[1]["best_rank"])):
        if node_key not in meta_cache:
            snap = store.latest_snapshot(node_key)
            meta_cache[node_key] = {r.get("asin"): r for r in snap}
        meta = meta_cache[node_key].get(asin, {})
        out.append([
            day, region.upper(), name_map.get(node_key, ""), node_key, asin,
            str(row["best_rank"]),
            str(meta.get("price_amount") or ""), str(meta.get("price_currency") or "KRW"),
            str(meta.get("rating") or ""), str(row.get("max_ratings") or ""),
            str(meta.get("title") or "")[:120],
        ])
    return out


def trend_rows_with_delta(store, settings: Settings, registry, region: str, days: int = 14) -> list[list[str]]:
    profile = settings.marketplace(region)
    tz = ZoneInfo(profile.timezone if profile else "UTC")
    name_map = {str(e["node_id"]): e.get("name") or "" for e in registry.all_entries()}

    daily_best: dict[tuple[str, str], dict[str, int]] = {}
    daily_snap: dict[tuple[str, str], dict[str, list[int]]] = {}
    for row in store.region_daily_best(region):
        day = _local_day(row["fetched_at"], tz)
        key = (row["node_id"], row["asin"])
        best = daily_best.setdefault(key, {})
        if day not in best or row["best_rank"] < best[day]:
            best[day] = row["best_rank"]
        snap = daily_snap.setdefault(key, {}).setdefault(day, [0, 0])
        snap[0] += row["snapshots"]
        snap[1] = max(snap[1], row["max_ratings"] or 0)

    all_days = sorted({d for best in daily_best.values() for d in best})
    recent = set(all_days[-days:])
    grid: list[list[str]] = [TREND_HEADER]
    ordered_keys = sorted(daily_best.keys())
    for day in reversed(all_days[-days:]):
        rows_for_day = [
            (key, best[day]) for key, best in daily_best.items()
            if day in best and key in [(k, a) for k, a in ordered_keys]
        ]
        rows_for_day.sort(key=lambda t: (t[0][0], t[1]))
        for (node_key, asin), rank in rows_for_day:
            chain = sorted(daily_best[(node_key, asin)].items())
            idx = next(i for i, c in enumerate(chain) if c[0] == day)
            prev_rank = chain[idx - 1][1] if idx > 0 else None
            delta = (prev_rank - rank) if prev_rank is not None else ""
            snaps, maxr = daily_snap[(node_key, asin)].get(day, [0, 0])
            grid.append([
                day, region.upper(), name_map.get(node_key, ""), node_key, asin,
                str(rank), str(prev_rank or ""), str(delta),
                str(snaps), str(maxr),
            ])
    return grid


def panel_tab_grid(store, registry, settings: Settings, region: str) -> dict[str, list[list[str]]]:
    profile = settings.marketplace(region)
    tabs: dict[str, list[list[str]]] = {}
    for entry in region_nodes(registry, region):
        node_key = str(entry["node_id"])
        title = f"[{region.upper()}] {entry.get('name') or node_key}"
        snapshot = store.latest_snapshot(node_key)
        if not snapshot:
            continue
        base_url = profile.base_url if profile else "https://www.amazon.com"
        raw_node = node_key.split(":", 1)[-1]
        grid = [["rank", "asin", "title", "rating", "ratings_count", "price_krw", "url"]]
        for row in snapshot:
            grid.append([
                str(row.get("rank") or ""), str(row.get("asin") or ""),
                str(row.get("title") or "")[:140],
                str(row.get("rating") or ""), str(row.get("ratings_count") or ""),
                str(row.get("price_amount") or ""), str(row.get("url") or ""),
            ])
        grid.insert(1, [f"{base_url}/gp/bestsellers/beauty/{raw_node}", "", "", "", "", "", ""])
        tabs[title] = grid
    return tabs


def publish_region(settings: Settings, registry, store, region: str, backend_token: str | None = None) -> dict:
    token = backend_token or oauth_access_token()
    sheet_id = ensure_spreadsheet(settings, token)
    meta = _sheet_meta_sa(sheet_id, token)
    tabs = panel_tab_grid(store, registry, settings, region)
    tabs["trend_14d"] = trend_rows_with_delta(store, settings, registry, region)
    tabs.setdefault(HISTORY_TAB, [HISTORY_HEADER])

    changes: list[dict] = []
    for title, grid in tabs.items():
        changes += _grid_resize_requests(title, meta.get(title), rows=len(grid) + 200, cols=max(11, max(len(r) for r in grid)))
    if changes:
        _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}:batchUpdate", token,
             body={"requests": changes})
        meta = _sheet_meta_sa(sheet_id, token)

    stamp_row = [_now(), f"region={region.upper()}", "auto"]
    for title, grid in tabs.items():
        if title == HISTORY_TAB:
            continue
        payload = {"valueInputOption": "USER_ENTERED", "data": [{"range": f"'{title}'!A1", "values": [stamp_row] + grid}]}
        _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchUpdate", token,
             params={"valueInputOption": "USER_ENTERED"}, body=payload)

    history_new = history_rows(store, settings, registry, region)
    appended = len(history_new)
    if appended:
        known = set()
        existing = _api("GET", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/'{HISTORY_TAB}'!A2:E", token,
                        params={"majorDimension": "ROWS"})
        for row in existing.get("values", []):
            if len(row) >= 5:
                known.add((row[0], row[3], row[4]))
        fresh = [r for r in history_new if (r[0], r[3], r[4]) not in known]
        appended = len(fresh)
        for chunk in _chunk_rows(fresh):
            _api("POST", f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/'{HISTORY_TAB}'!A1:append",
                 token, params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                 body={"values": chunk})
    return {
        "backend": "token",
        "sheet": sheet_id,
        "region": region.upper(),
        "tabs": len(tabs),
        "history_appended": appended,
    }
