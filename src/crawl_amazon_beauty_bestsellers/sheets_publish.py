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
    per_node = store.day_latest_rows(date_str)
    panel_titles = [( _panel_title(nid, name_map), str(nid)) for nid in sorted(per_node)]

    def _q(title: str) -> str:
        return "'" + title.replace("'", "''") + "'"

    def _category_formula(asin_ref: str) -> str:
        parts = ",".join(
            f'IF(COUNTIF({_q(t)}!$B$1:$B$500,{asin_ref}),"{t}","")'
            for t, _nid in panel_titles
        )
        return f'=TEXTJOIN(" | ",TRUE,{parts})'

    if lanes in ("ci", "all"):
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

        index_grid = [["node_id", "category", "bestsellers_url", "listed_rows"]]
        for node_id, _rows in sorted(per_node.items()):
            t = _panel_title(node_id, name_map)
            index_grid.append([
                str(node_id), t,
                f"https://www.amazon.com/Best-Sellers/zgbs/beauty/{node_id}",
                f"=COUNT('{t}'!A:A)",
            ])
        tabs["INDEX"] = index_grid

    if lanes in ("local", "all"):
        details = store.detail_day_rows(date_str)
        if details:
            asin_nodes = store.day_asin_categories(date_str)
            parsed = [(row, _parse_specs(row.get("specs") or "")) for row in details]
            keys = [
                "brand", "manufacturer", "model_number", "seller_name",
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
            grid = [["fetched_at", "asin", "category(자동)", "ranked_node_ids"] + keys + header_cols + ["specs_json"]]
            for row, specs in parsed:
                flat = _flatten(row)
                r = len(grid) + 2
                curated = [specs.get(column, "") for column in header_cols]
                specs_pretty = json.dumps(specs, ensure_ascii=False)[:3000]
                node_ids = ", ".join(asin_nodes.get(str(flat.get("asin")), []))
                grid.append(
                    [_norm(flat.get("fetched_at")), _norm(flat.get("asin")), _category_formula(f"$B{r}"), node_ids]
                    + [_norm(flat.get(k)) for k in keys]
                    + [_norm(v) for v in curated] + [specs_pretty]
                )
            tabs["details"] = grid

            grid = [["asin", "category(자동)", "brand", "spec_key", "spec_value"]]
            for row, specs in parsed:
                for key, value in sorted(specs.items()):
                    r = len(grid) + 2
                    grid.append([
                        _norm(row.get("asin")), _category_formula(f"$A{r}"),
                        _norm(row.get("brand")), key, str(value)[:500],
                    ])
            tabs["specs_long"] = grid

        trend = store.trend_rows(days=14)
        if trend:
            grid = [["day", "node_id", "category(자동)", "asin", "best_rank", "snapshots", "max_ratings"]]
            for row in trend:
                values = [ _norm(v) for v in row.values() ]
                r = len(grid) + 2
                grid.append(values[:2] + [f'=IFERROR(VLOOKUP($B{r},INDEX!$A:$B,2,FALSE),"")'] + values[2:])
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


def _sheet_meta_gws(spreadsheet_id: str) -> dict[str, dict]:
    meta = _gws(
        ["sheets", "spreadsheets", "get"],
        {"spreadsheetId": spreadsheet_id, "fields": "sheets.properties(sheetId,title,gridProperties)"},
    )
    out: dict[str, dict] = {}
    for s in meta.get("sheets", []):
        props = s["properties"]
        grid = props.get("gridProperties", {})
        out[props["title"]] = {"sheet_id": props["sheetId"], "rows": grid.get("rowCount", 1000), "cols": grid.get("columnCount", 26)}
    return out


def _grid_resize_requests(title: str, meta: dict | None, rows: int, cols: int) -> list[dict]:
    need_rows, need_cols = max(rows + 50, 100), max(cols + 5, 26)
    if meta is None:
        return [{"addSheet": {"properties": {"title": title, "gridProperties": {"rowCount": need_rows, "columnCount": need_cols}}}}]
    requests = []
    if meta["rows"] < rows or meta["cols"] < cols:
        requests.append({
            "updateSheetProperties": {
                "properties": {
                    "sheetId": meta["sheet_id"],
                    "gridProperties": {"rowCount": max(need_rows, meta["rows"]), "columnCount": max(need_cols, meta["cols"])},
                },
                "fields": "gridProperties",
            }
        })
    return requests


def _transport():
    import google.auth.transport.requests

    return google.auth.transport.requests.Request()


def _sheet_meta_sa(spreadsheet_id: str, token: str) -> dict[str, dict]:
    import requests

    resp = requests.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}",
        params={"fields": "sheets.properties(sheetId,title,gridProperties)"},
        headers={"Authorization": f"Bearer {token}"}, timeout=60,
    )
    resp.raise_for_status()
    out: dict[str, dict] = {}
    for s in resp.json().get("sheets", []):
        props = s["properties"]
        grid = props.get("gridProperties", {})
        out[props["title"]] = {"sheet_id": props["sheetId"], "rows": grid.get("rowCount", 1000), "cols": grid.get("columnCount", 26)}
    return out


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
    stamp = time.strftime("%Y-%m-%d %H:%M %Z")
    lane = "cloud/actions" if backend == "sa" else "local/home-ip"
    stamped: dict[str, list[list[str]]] = {}
    for title, grid in tabs.items():
        header_row = [f"마지막 갱신: {stamp}", f"라인: {lane}", f"탭: {title}"]
        rest = grid[1:] if grid and grid[0] and str(grid[0][0]).startswith("Amazon Best Sellers") else grid[1:]
        lead = grid[0] if grid else []
        if lead and str(lead[0]).startswith("Amazon Best Sellers"):
            stamped[title] = [header_row, lead] + rest
        else:
            stamped[title] = [header_row] + grid
    tabs = stamped

    if backend == "gws":
        meta = _sheet_meta_gws(spreadsheet_id)
        changes: list[dict] = []
        for title, grid in tabs.items():
            changes += _grid_resize_requests(title, meta.get(title), rows=len(grid), cols=max(len(r) for r in grid))
        if changes:
            _gws(["sheets", "spreadsheets", "batchUpdate"], {"spreadsheetId": spreadsheet_id}, {"requests": changes})
        for title, grid in tabs.items():
            _gws(
                ["sheets", "spreadsheets", "values", "clear"],
                {"spreadsheetId": spreadsheet_id, "range": f"'{title}'"},
                {},
            )
            offset = 1
            for chunk in _chunk_rows(grid):
                _gws(
                    ["sheets", "spreadsheets", "values", "batchUpdate"],
                    {"spreadsheetId": spreadsheet_id},
                    {
                        "valueInputOption": "USER_ENTERED",
                        "data": [{"range": f"'{title}'!A{offset}", "values": chunk}],
                    },
                )
                offset += len(chunk)
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

    meta = _sheet_meta_sa(spreadsheet_id, token)
    changes: list[dict] = []
    for title, grid in tabs.items():
        changes += _grid_resize_requests(title, meta.get(title), rows=len(grid), cols=max(len(r) for r in grid))
    if changes:
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}:batchUpdate",
            json={"requests": changes}, headers={"Authorization": f"Bearer {token}"}, timeout=120,
        ).raise_for_status()
    data_items: list[dict] = []
    for title, grid in tabs.items():
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values/'{title}'!A1:ZZ1000000:clear",
            headers={"Authorization": f"Bearer {token}"}, timeout=120,
        )
        offset = 1
        for chunk in _chunk_rows(grid):
            data_items.append({"range": f"'{title}'!A{offset}", "values": chunk})
            offset += len(chunk)
    batch: list[dict] = []
    batch_bytes = 0
    for item in data_items:
        size = len(json.dumps(item, ensure_ascii=False))
        if batch and batch_bytes + size > 4_000_000:
            requests.post(
                f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate",
                params={"valueInputOption": "USER_ENTERED"},
                json={"valueInputOption": "USER_ENTERED", "data": batch},
                headers={"Authorization": f"Bearer {token}"}, timeout=300,
            ).raise_for_status()
            batch, batch_bytes = [], 0
        batch.append(item)
        batch_bytes += size
    if batch:
        requests.post(
            f"https://sheets.googleapis.com/v4/spreadsheets/{spreadsheet_id}/values:batchUpdate",
            params={"valueInputOption": "USER_ENTERED"},
            json={"valueInputOption": "USER_ENTERED", "data": batch},
            headers={"Authorization": f"Bearer {token}"}, timeout=300,
        ).raise_for_status()
    return {"backend": "sa", "tabs": len(tabs), "rows": sum(len(g) for g in tabs.values())}
