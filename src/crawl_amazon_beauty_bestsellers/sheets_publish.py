from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

from .config import Settings
from .storage.store import Store

DEFAULT_SPREADSHEET_ID = "1UlvJ5T-oA3qr7TkG8KIG_Jw1R6xUiEa5dszrjN6X2HU"
CURATED_SPEC_COLUMNS = [
    "Item Form", "Skin Type", "Item Weight", "Unit Count", "Active Ingredients",
    "Material Type Free", "Sun Protection Factor", "Age Range Description",
    "Country as Labeled", "Country of Origin",
    "Recommended Uses For Product", "Product Benefits",
]


class SheetsPublishError(RuntimeError):
    pass


def _norm(value) -> str:
    if value is None:
        return ""
    return str(value)


def _parse_specs(raw: str) -> dict:
    try:
        parsed = json.loads(raw or "")
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def _flatten(row: dict) -> dict:
    flat = dict(row)
    try:
        bsr_other = json.loads(row.get("bsr_other") or "[]")
    except (json.JSONDecodeError, TypeError):
        bsr_other = []
    for idx in range(2):
        item = bsr_other[idx] if idx < len(bsr_other) else {}
        flat[f"bsr_sub_{idx + 1}_rank"] = item.get("rank")
        flat[f"bsr_sub_{idx + 1}_category"] = item.get("category")
    try:
        histogram = json.loads(row.get("ratings_histogram") or "{}")
    except (json.JSONDecodeError, TypeError):
        histogram = {}
    flat["ratings_histogram"] = " ".join(
        f"{star}:{pct}%" for star, pct in sorted(histogram.items(), reverse=True)
    )
    return flat


def _panel_title(node_id: str, name_map: dict[str, str]) -> str:
    base = name_map.get(str(node_id)) or f"node_{node_id}"
    for ch in "[]:*?/\\,":
        base = base.replace(ch, " ")
    return base[:90]


def build_tab_payloads(
    store: Store,
    date_str: str | None,
    name_map: dict[str, str],
    lanes: str,
) -> dict[str, list[list[str]]]:
    date_str = date_str or time.strftime("%Y-%m-%d")
    tabs: dict[str, list[list[str]]] = {}

    if lanes in ("ci", "all"):
        per_node = store.day_latest_rows(date_str)
        for node_id, rows in sorted(per_node.items()):
            title = _panel_title(node_id, name_map)
            grid: list[list[str]] = [[
                "Amazon Best Sellers", "", "", "", "", "", "", "",
                f"https://www.amazon.com/Best-Sellers/zgbs/beauty/{node_id}",
            ]]
            grid.append(["rank", "asin", "title", "rating", "ratings_count", "price", "currency", "offers_text", "url"])
            for row in rows:
                grid.append([
                    _norm(row.get("rank")), _norm(row.get("asin")), _norm(row.get("title")),
                    _norm(row.get("rating")), _norm(row.get("ratings_count")),
                    _norm(row.get("price_amount")), _norm(row.get("price_currency")),
                    _norm(row.get("offers_text")), _norm(row.get("url")),
                ])
            tabs[title] = grid

    if lanes in ("local", "all"):
        details = store.detail_day_rows(date_str)
        if details:
            parsed = [(row, _parse_specs(row.get("specs") or "")) for row in details]
            keys = [
                "asin", "brand", "manufacturer", "model_number", "seller_name",
                "buy_box_price", "buy_box_currency", "list_price_amount",
                "bsr_main_rank", "bsr_main_category",
                "bsr_sub_1_rank", "bsr_sub_1_category", "bsr_sub_2_rank", "bsr_sub_2_category",
                "ratings_histogram", "date_first_available",
                "availability", "price_source", "variants_count",
            ]
            header_cols: list[str] = []
            for column in CURATED_SPEC_COLUMNS:
                if column not in header_cols:
                    header_cols.append(column)
            grid = [["fetched_at"] + keys + header_cols + ["specs_json"]]
            for row, specs in parsed:
                row = _flatten(row)
                curated = [specs.get(column, "") for column in header_cols]
                specs_pretty = json.dumps(specs, ensure_ascii=False)[:3000]
                grid.append(
                    [_norm(row.get("fetched_at"))] + [_norm(row.get(k)) for k in keys]
                    + [_norm(v) for v in curated] + [specs_pretty]
                )
            tabs["details"] = grid

            grid = [["asin", "brand", "spec_key", "spec_value"]]
            for row, specs in parsed:
                for key, value in sorted(specs.items()):
                    grid.append([_norm(row.get("asin")), _norm(row.get("brand")), key, str(value)[:500]])
            tabs["specs_long"] = grid

        trend = store.trend_rows(days=14)
        if trend:
            grid = [["day", "node_id", "asin", "best_rank", "snapshots", "max_ratings"]]
            for row in trend:
                grid.append([_norm(v) for v in row.values()])
            tabs["trend_14d"] = grid

    return tabs


def _gws(args: list[str], params: dict, body: dict | None = None) -> dict:
    cmd = ["gws", *args, "--params", json.dumps(params)]
    if body is not None:
        cmd += ["--json", json.dumps(body)]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise SheetsPublishError(f"gws {' '.join(args)} failed: {(proc.stderr or proc.stdout).strip()[-300:]}")
    stdout = proc.stdout
    return json.loads(stdout[stdout.index("{"):]) if "{" in stdout else {}


def _existing_titles_gws(spreadsheet_id: str) -> set[str]:
    meta = _gws(["sheets", "spreadsheets", "get"], {"spreadsheetId": spreadsheet_id, "fields": "sheets.properties.title"})
    return {s["properties"]["title"] for s in meta.get("sheets", [])}


def _transport():
    import google.auth.transport.requests

    return google.auth.transport.requests.Request()


def _existing_titles_sa(spreadsheet_id: str, token: str) -> set[str]:
    import requests

    resp = requests.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
        params={"fields": "sheets.properties.title"},
        headers={"Authorization": f"Bearer {token}"}, timeout=60,
    )
    resp.raise_for_status()
    return {s["properties"]["title"] for s in resp.json().get("sheets", [])}


def _chunk_rows(grid: list[list[str]], max_bytes: int = 100_000, max_rows: int = 2000) -> list[list[list[str]]]:
    chunks: list[list[list[str]]] = []
    current: list[list[str]] = []
    size = 0
    for row in grid:
        row_size = len(json.dumps(row, ensure_ascii=False))
        if current and (size + row_size > max_bytes or len(current) >= max_rows):
            chunks.append(current)
            current, size = [], 0
        current.append(row)
        size += row_size
    if current:
        chunks.append(current)
    return chunks


def publish(spreadsheet_id: str, tabs: dict[str, list[list[str]]], backend: str) -> dict:
    if backend == "gws":
        existing = _existing_titles_gws(spreadsheet_id)
        missing = [{"addSheet": {"properties": {"title": t}}} for t in tabs if t not in existing]
        if missing:
            _gws(["sheets", "spreadsheets", "batchUpdate"], {"spreadsheetId": spreadsheet_id}, {"requests": missing})
        for title, grid in tabs.items():
            _gws(
                ["sheets", "spreadsheets", "values", "clear"],
                {"spreadsheetId": spreadsheet_id, "range": f"'{title}'"},
                {},
            )
            for chunk in _chunk_rows(grid):
                _gws(
                    ["sheets", "spreadsheets", "values", "batchUpdate"],
                    {"spreadsheetId": spreadsheet_id},
                    {
                        "valueInputOption": "RAW",
                        "data": [{"range": f"'{title}'!A1", "values": chunk}],
                    },
                )
        return {"backend": backend, "tabs": len(tabs), "rows": sum(len(g) for g in tabs.values())}

    creds_env = os.environ.get("GDRIVE_CREDS", "")
    if not creds_env:
        raise SheetsPublishError("GDRIVE_CREDS not configured for SA backend")
    info = json.loads(Path(creds_env).read_text(encoding="utf-8")) if Path(creds_env).exists() else json.loads(creds_env)
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    creds.refresh(_transport())
    token = creds.token

    import requests

    existing = _existing_titles_sa(spreadsheet_id, token)
    missing = [{"addSheet": {"properties": {"title": t}}} for t in tabs if t not in existing]
    if missing:
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            json={"requests": missing}, headers={"Authorization": f"Bearer {token}"}, timeout=120,
        ).raise_for_status()
    for title, grid in tabs.items():
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/'{title}'!A1:ZZ1000000:clear",
            headers={"Authorization": f"Bearer {token}"}, timeout=120,
        )
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate",
            params={"valueInputOption": "RAW"},
            json={"valueInputOption": "RAW", "data": [{"range": f"'{title}'!A1", "values": grid}]},
            headers={"Authorization": f"Bearer {token}"}, timeout=300,
        ).raise_for_status()
    return {"backend": "sa", "tabs": len(tabs), "rows": sum(len(g) for g in tabs.values())}
