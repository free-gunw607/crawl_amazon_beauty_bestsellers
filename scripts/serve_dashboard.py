#!/usr/bin/env python3
"""Read-only web dashboard for the Amazon Beauty & Personal Care rank history."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
WEB_ROOT = ROOT / "web"
DEFAULT_DB = ROOT / "artifacts/db/bestsellers.sqlite"
sys.path.insert(0, str(ROOT / "src"))
from crawl_amazon_beauty_bestsellers.config import load_settings
from crawl_amazon_beauty_bestsellers.marketplaces import MARKETPLACE_CODES, MARKETPLACE_META

_SETTINGS = load_settings(ROOT)
REGIONS = {code: ("ROOT" if code == "us" else f"{code}:ROOT") for code in MARKETPLACE_CODES}
DISPLAY_CURRENCIES = {"us": "USD", "uk": "GBP", "de": "EUR", "fr": "EUR", "es": "EUR", "it": "EUR"}


def _profile(region: str):
    return _SETTINGS.marketplace(region)


class DashboardData:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._sheet_rows: list[dict] = []
        self._sheet_snapshots: dict[str, dict] = {}
        self._sheet_loaded_at = 0.0
        self._sheet_error: str | None = None
        self._sheet_lock = threading.Lock()

    def sheet_history(self) -> list[dict]:
        """Read current Top100 tabs and the append-only history using one short-lived cache."""
        sheet_id = os.environ.get("AMZ_BS_ROOT_SHEETS_ID", "")
        creds_path = os.environ.get("GDRIVE_CREDS", "")
        if not sheet_id or not creds_path:
            return []
        if time.time() - self._sheet_loaded_at < 600:
            return self._sheet_rows
        with self._sheet_lock:
            if time.time() - self._sheet_loaded_at < 600:
                return self._sheet_rows
            try:
                from google.auth.transport.requests import Request
                from google.oauth2 import service_account
                import requests

                credentials = service_account.Credentials.from_service_account_file(
                    creds_path, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
                )
                credentials.refresh(Request())
                # Keep the established feed readable before Italy's first
                # publish creates its tabs. A missing optional tab must never
                # break the five-market public dashboard.
                ranges = ["'root_rank_history'!A1:I"] + [
                    f"'[{region.upper()}] Top 100'!A1:G104"
                    for region in REGIONS if region != "it"
                ]
                response = requests.get(
                    f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet",
                    params=[("ranges", item) for item in ranges],
                    headers={"Authorization": f"Bearer {credentials.token}"}, timeout=90,
                )
                response.raise_for_status()
                value_ranges = response.json().get("valueRanges", [])
                if "it" in REGIONS:
                    try:
                        optional_ranges = ["'[IT] Top 100'!A1:G104", "'IT Rank History'!A1:I"]
                        optional_response = requests.get(
                            f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values:batchGet",
                            params=[("ranges", item) for item in optional_ranges],
                            headers={"Authorization": f"Bearer {credentials.token}"},
                            timeout=30,
                        )
                        optional_response.raise_for_status()
                        value_ranges.extend(optional_response.json().get("valueRanges", []))
                    except Exception:
                        # Italy is an additive market; first-run or temporary
                        # Italy tab issues leave the existing markets online.
                        pass
                values = value_ranges[0].get("values", []) if value_ranges else []
                # Row 1 is the schema header: date, region, asin, rank, price, currency, rating, reviews, title.
                rows = []
                for cells in values[1:]:
                    if len(cells) < 4:
                        continue
                    try:
                        rows.append({
                            "day": str(cells[0]), "region": str(cells[1]).lower(), "asin": str(cells[2]).upper(),
                            "rank": int(float(cells[3])), "price_amount": _number(cells[4] if len(cells) > 4 else ""),
                            "price_currency": str(cells[5]) if len(cells) > 5 else "",
                            "rating": _number(cells[6] if len(cells) > 6 else ""),
                            "ratings_count": _number(cells[7] if len(cells) > 7 else ""),
                            "title": str(cells[8]) if len(cells) > 8 else "",
                        })
                    except (TypeError, ValueError):
                        continue
                self._sheet_rows = rows
                # Italy keeps its raw append-only history in a dedicated tab;
                # merge it in memory so the macro-facing root history is unchanged.
                legacy_value_count = len(REGIONS)  # root history + five markets
                if "it" in REGIONS and len(value_ranges) > legacy_value_count + 1:
                    it_grid = value_ranges[legacy_value_count + 1].get("values", [])
                    for cells in it_grid[2:]:  # row 1 stamp, row 2 schema header
                        if len(cells) < 4:
                            continue
                        try:
                            rows.append({
                                "day": str(cells[0]), "region": "it", "asin": str(cells[2]).upper(),
                                "rank": int(float(cells[3])),
                                "price_amount": _number(cells[4] if len(cells) > 4 else ""),
                                "price_currency": str(cells[5]) if len(cells) > 5 else "EUR",
                                "rating": _number(cells[6] if len(cells) > 6 else ""),
                                "ratings_count": _number(cells[7] if len(cells) > 7 else ""),
                                "title": str(cells[8]) if len(cells) > 8 else "",
                            })
                        except (TypeError, ValueError):
                            continue
                snapshots = {}
                currencies = {code: DISPLAY_CURRENCIES.get(code, "") for code in REGIONS}
                legacy_regions = [code for code in REGIONS if code != "it"]
                for region, value_range in zip(legacy_regions, value_ranges[1:legacy_value_count]):
                    grid = value_range.get("values", [])
                    if not grid:
                        continue
                    stamp = str((grid[0] or [""])[0])
                    snapshot_day = stamp[:10]
                    if len(snapshot_day) != 10 or snapshot_day[4] != "-":
                        continue
                    entries = []
                    # Rows 1-4 contain the freshness marker, source URL and column header.
                    for cells in grid[4:]:
                        if len(cells) < 2 or not str(cells[1]).strip():
                            continue
                        try:
                            entries.append({
                                "rank": int(float(cells[0])), "asin": str(cells[1]).upper(),
                                "title": str(cells[2]) if len(cells) > 2 else "",
                                "rating": _number(cells[3] if len(cells) > 3 else ""),
                                "ratings_count": _number(cells[4] if len(cells) > 4 else ""),
                                "price_amount": _number(cells[5] if len(cells) > 5 else ""),
                            "price_currency": currencies.get(region, ""),
                                "url": str(cells[6]) if len(cells) > 6 else "",
                                "image_url": "", "fetched_at": stamp, "brand": "",
                            })
                        except (TypeError, ValueError):
                            continue
                    if entries:
                        self._enrich_brands(entries)
                        self._enrich_images(entries)
                        snapshots[region] = {"day": snapshot_day, "entries": entries, "stamp": stamp}
                if "it" in REGIONS and len(value_ranges) > legacy_value_count:
                    grid = value_ranges[legacy_value_count].get("values", [])
                    if grid:
                        stamp = str((grid[0] or [""])[0])
                        snapshot_day = stamp[:10]
                        if len(snapshot_day) == 10 and snapshot_day[4] == "-":
                            entries = []
                            for cells in grid[4:]:
                                if len(cells) < 2 or not str(cells[1]).strip():
                                    continue
                                try:
                                    entries.append({
                                        "rank": int(float(cells[0])), "asin": str(cells[1]).upper(),
                                        "title": str(cells[2]) if len(cells) > 2 else "",
                                        "rating": _number(cells[3] if len(cells) > 3 else ""),
                                        "ratings_count": _number(cells[4] if len(cells) > 4 else ""),
                                        "price_amount": _number(cells[5] if len(cells) > 5 else ""),
                                        "price_currency": "EUR",
                                        "url": str(cells[6]) if len(cells) > 6 else "",
                                        "image_url": "", "fetched_at": stamp, "brand": "",
                                    })
                                except (TypeError, ValueError):
                                    continue
                            if entries:
                                self._enrich_brands(entries)
                                self._enrich_images(entries)
                                snapshots["it"] = {"day": snapshot_day, "entries": entries, "stamp": stamp}
                self._sheet_snapshots = snapshots
                self._sheet_error = None
            except Exception as exc:
                self._sheet_error = str(exc)[:240]
            self._sheet_loaded_at = time.time()
        return self._sheet_rows

    def query(self, sql: str, params: tuple = ()) -> list[dict]:
        uri = f"file:{self.db_path.resolve()}?mode=ro"
        with sqlite3.connect(uri, uri=True, timeout=10) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(sql, params).fetchall()]

    @staticmethod
    def node(region: str) -> str:
        if region not in REGIONS:
            raise ValueError("region must be one of " + ", ".join(REGIONS))
        return REGIONS[region]

    def dates(self, region: str) -> list[str]:
        node = self.node(region)
        sheet_rows = self.sheet_history()
        if sheet_rows:
            available = {r["day"] for r in sheet_rows if r["region"] == region}
            if region in self._sheet_snapshots:
                available.add(self._sheet_snapshots[region]["day"])
            return sorted(available, reverse=True)
        rows = self.query(
            "SELECT DISTINCT substr(fetched_at,1,10) AS day FROM list_entries "
            "WHERE node_id=? ORDER BY day DESC", (node,)
        )
        return [r["day"] for r in rows]

    def snapshot(self, region: str, day: str | None = None) -> tuple[str | None, list[dict]]:
        node = self.node(region)
        sheet_rows = self.sheet_history()
        latest_sheet = self._sheet_snapshots.get(region)
        if not day and latest_sheet:
            day = latest_sheet["day"]
        if day and latest_sheet and latest_sheet["day"] == day:
            entries = [dict(r) for r in latest_sheet["entries"]]
            self._enrich_brands(entries)
            return day, entries
        if day and sheet_rows:
            history = [r for r in sheet_rows if r["region"] == region and r["day"] == day]
            if history:
                currency = DISPLAY_CURRENCIES.get(region, "")
                profile = _profile(region)
                base_url = profile.base_url if profile else "https://www.amazon.com"
                entries = [{"day": r["day"], "rank": r["rank"], "asin": r["asin"], "title": r["title"],
                            "url": f"{base_url}/dp/{r['asin']}",
                            "image_url": "", "rating": r["rating"], "ratings_count": r["ratings_count"],
                            "price_amount": r["price_amount"], "price_currency": r["price_currency"] or currency,
                            "fetched_at": r["day"], "brand": "", "image_url": ""} for r in history]
                self._enrich_brands(entries)
                self._enrich_images(entries)
                entries.sort(key=lambda r: r["rank"])
                return day, entries
        if day is None:
            found = self.query("SELECT MAX(substr(fetched_at,1,10)) AS day FROM list_entries WHERE node_id=?", (node,))
            day = found[0]["day"] if found else None
        if not day:
            return None, []
        runs = self.query(
            "SELECT run_id, MAX(fetched_at) AS fetched_at FROM list_entries "
            "WHERE node_id=? AND substr(fetched_at,1,10)=? GROUP BY run_id ORDER BY fetched_at DESC LIMIT 1",
            (node, day),
        )
        if not runs:
            return day, []
        rows = self.query(
            "SELECT rank, asin, title, url, image_url, rating, ratings_count, price_amount, "
            "price_currency, fetched_at FROM list_entries WHERE node_id=? AND run_id=? ORDER BY rank",
            (node, runs[0]["run_id"]),
        )
        self._enrich_brands(rows)
        self._enrich_images(rows)
        return day, rows

    def _enrich_brands(self, rows: list[dict]) -> None:
        if not rows:
            return
        placeholders = ",".join("?" for _ in rows)
        details = self.query(
            "SELECT asin, brand FROM product_details WHERE asin IN (" + placeholders + ") "
            "AND brand IS NOT NULL AND trim(brand)!='' ORDER BY fetched_at DESC", tuple(r["asin"] for r in rows)
        )
        brands = {}
        for detail in details:
            brands.setdefault(detail["asin"], detail["brand"])
        for row in rows:
            row["brand"] = brands.get(row["asin"], row.get("brand", ""))

    def _enrich_images(self, rows: list[dict]) -> None:
        """Fill missing Google Sheet image cells from saved list/detail records by ASIN."""
        missing = [r for r in rows if not r.get("image_url")]
        if not missing:
            return
        placeholders = ",".join("?" for _ in missing)
        asins = tuple(r["asin"] for r in missing)
        image_by_asin = {}
        for item in self.query(
            "SELECT asin,image_url FROM list_entries WHERE asin IN (" + placeholders + ") "
            "AND image_url IS NOT NULL AND length(image_url)>0 ORDER BY fetched_at DESC", asins
        ):
            image_by_asin.setdefault(item["asin"], item["image_url"])
        still_missing = [asin for asin in asins if asin not in image_by_asin]
        if still_missing:
            detail_placeholders = ",".join("?" for _ in still_missing)
            detail_rows = self.query(
                "SELECT asin,image_urls FROM product_details WHERE asin IN (" + detail_placeholders + ") "
                "AND image_urls IS NOT NULL AND length(image_urls)>2 ORDER BY fetched_at DESC", tuple(still_missing)
            )
            for detail in detail_rows:
                if detail["asin"] in image_by_asin:
                    continue
                try:
                    urls = json.loads(detail["image_urls"])
                except (TypeError, json.JSONDecodeError):
                    continue
                if isinstance(urls, list):
                    image = next((str(url) for url in urls if isinstance(url, str) and url.startswith("https://")), "")
                    if image:
                        image_by_asin[detail["asin"]] = image
        for row in missing:
            row["image_url"] = image_by_asin.get(row["asin"], "")

    def _enrich_image_candidates(self, rows: list[dict]) -> None:
        """Attach all previously captured ASIN image URLs as ordered fallbacks."""
        asins = tuple(dict.fromkeys(str(row.get("asin", "")).upper() for row in rows if row.get("asin")))
        if not asins:
            return
        placeholders = ",".join("?" for _ in asins)
        candidates: dict[str, list[str]] = {asin: [] for asin in asins}

        def add(asin: str, url: object) -> None:
            value = str(url or "").strip()
            if value.startswith("https://") and value not in candidates.get(asin, []):
                candidates.setdefault(asin, []).append(value)

        for row in rows:
            add(str(row.get("asin", "")).upper(), row.get("image_url"))
        for item in self.query(
            "SELECT asin,image_url FROM list_entries WHERE asin IN (" + placeholders + ") "
            "AND image_url IS NOT NULL AND length(image_url)>0 ORDER BY fetched_at DESC", asins
        ):
            add(str(item["asin"]).upper(), item.get("image_url"))
        for detail in self.query(
            "SELECT asin,image_urls FROM product_details WHERE asin IN (" + placeholders + ") "
            "AND image_urls IS NOT NULL AND length(image_urls)>2 ORDER BY fetched_at DESC", asins
        ):
            try:
                urls = json.loads(detail.get("image_urls") or "[]")
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(urls, list):
                for url in urls:
                    add(str(detail["asin"]).upper(), url)
        for row in rows:
            asin = str(row.get("asin", "")).upper()
            row["image_urls"] = candidates.get(asin, [])
            if not row.get("image_url") and row["image_urls"]:
                row["image_url"] = row["image_urls"][0]

    def summary(self) -> dict:
        sheet_history = self.sheet_history()
        out = {"regions": [], "db_updated": None, "history_days": 0, "asin_count": 0,
               "history_source": "Google Sheet" if sheet_history else "local SQLite",
               "history_warning": self._sheet_error}
        for region, node in REGIONS.items():
            rows = self.query(
                "SELECT substr(fetched_at,1,10) AS day, fetched_at, products FROM ("
                "SELECT run_id, MAX(fetched_at) AS fetched_at, COUNT(DISTINCT asin) AS products "
                "FROM list_entries WHERE node_id=? GROUP BY run_id ORDER BY MAX(fetched_at) DESC LIMIT 1"
                ")", (node,)
            )
            days = self.query("SELECT COUNT(DISTINCT substr(fetched_at,1,10)) AS n FROM list_entries WHERE node_id=?", (node,))
            latest = rows[0] if rows else {"day": None, "fetched_at": None, "products": 0}
            out["regions"].append({"region": region, **latest, "history_days": days[0]["n"] if days else 0})
            if latest["fetched_at"] and (not out["db_updated"] or latest["fetched_at"] > out["db_updated"]):
                out["db_updated"] = latest["fetched_at"]
            out["history_days"] = max(out["history_days"], days[0]["n"] if days else 0)
        count = self.query("SELECT COUNT(DISTINCT asin) AS n FROM list_entries")
        out["asin_count"] = count[0]["n"] if count else 0
        if sheet_history:
            out["history_days"] = len({r["day"] for r in sheet_history})
            out["history_asins"] = len({r["asin"] for r in sheet_history})
            out["asin_count"] = out["history_asins"]
            for region_row in out["regions"]:
                region_row["history_days"] = len({r["day"] for r in sheet_history if r["region"] == region_row["region"]})
        else:
            out["history_asins"] = out["asin_count"]
        out["today"] = date.today().isoformat()
        return out

    def rankings(self, region: str, day: str | None, search: str = "", brand: str = "") -> dict:
        chosen, rows = self.snapshot(region, day)
        if search:
            needle = search.casefold()
            rows = [r for r in rows if any(needle in str(r.get(key) or "").casefold() for key in ("asin", "title", "brand"))]
        if brand:
            rows = [r for r in rows if str(r.get("brand") or "").casefold() == brand.casefold()]
        prev_days = [d for d in self.dates(region) if chosen and d < chosen]
        prev_map = {}
        if prev_days:
            _, previous = self.snapshot(region, prev_days[0])
            prev_map = {r["asin"]: r["rank"] for r in previous}
        for row in rows:
            prev = prev_map.get(row["asin"])
            row["prev_rank"] = prev
            row["rank_delta"] = (prev - row["rank"]) if prev is not None else None
            row["movement"] = "NEW" if prev is None else ("UP" if row["rank"] < prev else "DOWN" if row["rank"] > prev else "SAME")
        return {"region": region, "day": chosen, "previous_day": prev_days[0] if prev_days else None,
                "count": len(rows), "entries": rows}

    def brands(self, region: str, day: str | None) -> dict:
        chosen, rows = self.snapshot(region, day)
        groups: dict[str, list[dict]] = {}
        for row in rows:
            name = str(row.get("brand") or "").strip()
            if name:
                groups.setdefault(name, []).append(row)
        result = []
        for name, items in groups.items():
            ratings = [float(r["rating"]) for r in items if r.get("rating") is not None]
            reviews = [int(r["ratings_count"]) for r in items if r.get("ratings_count") is not None]
            result.append({"brand": name, "products": len(items), "avg_rank": round(sum(r["rank"] for r in items) / len(items), 1),
                           "best_rank": min(r["rank"] for r in items), "avg_rating": round(sum(ratings) / len(ratings), 2) if ratings else None,
                           "reviews": sum(reviews), "asins": [r["asin"] for r in items]})
        result.sort(key=lambda r: (-r["products"], r["avg_rank"], r["brand"].casefold()))
        return {"region": region, "day": chosen, "count": len(result), "brands": result}

    def movements(self, region: str, day: str | None) -> dict:
        result = self.rankings(region, day)
        chosen = result["day"]
        previous_day = result["previous_day"]
        _, current_rows = self.snapshot(region, chosen)
        current = {r["asin"]: r for r in current_rows}
        _, previous_rows = self.snapshot(region, previous_day) if previous_day else (None, [])
        previous = {r["asin"]: r for r in previous_rows}
        changes = []
        for asin, row in current.items():
            old = previous.get(asin)
            old_rank = old["rank"] if old else None
            movement = "NEW" if old is None else "UP" if row["rank"] < old_rank else "DOWN" if row["rank"] > old_rank else "SAME"
            changes.append({**row, "prev_rank": old_rank, "rank_delta": old_rank - row["rank"] if old_rank is not None else None,
                            "movement": movement})
        for asin, row in previous.items():
            if asin not in current:
                changes.append({**row, "rank": None, "prev_rank": row["rank"], "rank_delta": None, "movement": "DROPPED"})
        order = {"NEW": 0, "UP": 1, "DOWN": 2, "DROPPED": 3, "SAME": 4}
        changes.sort(key=lambda r: (order[r["movement"]], -(r["rank_delta"] or 0), r["rank"] or r["prev_rank"] or 999))
        counts = {key: sum(1 for row in changes if row["movement"] == key) for key in order}
        return {"region": region, "day": chosen, "previous_day": previous_day, "counts": counts, "changes": changes}

    def product(self, asin: str) -> dict:
        sheet_rows = self.sheet_history()
        brands = self.query("SELECT brand FROM product_details WHERE upper(asin)=upper(?) AND brand IS NOT NULL AND trim(brand)!='' ORDER BY fetched_at DESC LIMIT 1", (asin.strip(),))
        brand = brands[0]["brand"] if brands else ""
        if sheet_rows:
            history = [
                {"day": row["day"], "node_id": REGIONS.get(row["region"], ""), "region": row["region"],
                 "rank": row["rank"], "title": row["title"], "price_amount": row["price_amount"],
                 "price_currency": row["price_currency"], "rating": row["rating"], "ratings_count": row["ratings_count"]}
                for row in sheet_rows if row["asin"] == asin.strip().upper()
            ]
            history.sort(key=lambda row: (row["day"], row["region"]))
            return {"asin": asin.upper(), "brand": brand, "history": history, "history_source": "Google Sheet"}
        rows = self.query(
            "SELECT substr(fetched_at,1,10) AS day, node_id, MIN(rank) AS rank, "
            "MAX(title) AS title, MAX(price_amount) AS price_amount, MAX(price_currency) AS price_currency, "
            "MAX(rating) AS rating, MAX(ratings_count) AS ratings_count "
            "FROM list_entries WHERE upper(asin)=upper(?) "
            "GROUP BY day,node_id ORDER BY day", (asin.strip(),)
        )
        history = []
        for row in rows:
            region = next((code for code, node in REGIONS.items() if node == row["node_id"]), None)
            if region:
                history.append({**row, "region": region})
        return {"asin": asin.upper(), "brand": brand, "history": history, "history_source": "local SQLite"}


def _number(value):
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return None


def make_handler(data: DashboardData):
    class Handler(BaseHTTPRequestHandler):
        def send_bytes(self, body: bytes, content_type: str, status: int = 200):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_json(self, payload, status: int = 200):
            self.send_bytes(json.dumps(payload, ensure_ascii=False).encode(), "application/json; charset=utf-8", status)

        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/summary":
                    self.send_json(data.summary())
                elif parsed.path == "/api/dates":
                    self.send_json({"dates": data.dates((params.get("region") or ["us"])[0])})
                elif parsed.path == "/api/rankings":
                    self.send_json(data.rankings((params.get("region") or ["us"])[0], (params.get("date") or [None])[0], (params.get("q") or [""])[0], (params.get("brand") or [""])[0]))
                elif parsed.path == "/api/brands":
                    self.send_json(data.brands((params.get("region") or ["us"])[0], (params.get("date") or [None])[0]))
                elif parsed.path == "/api/movements":
                    self.send_json(data.movements((params.get("region") or ["us"])[0], (params.get("date") or [None])[0]))
                elif parsed.path == "/api/product":
                    asin = (params.get("asin") or [""])[0]
                    if not asin:
                        self.send_json({"error": "asin is required"}, 400)
                    else:
                        self.send_json(data.product(asin))
                elif parsed.path == "/api/health":
                    self.send_json({"ok": True, "db": str(data.db_path)})
                elif parsed.path == "/" or parsed.path == "/index.html":
                    self.send_bytes((WEB_ROOT / "index.html").read_bytes(), "text/html; charset=utf-8")
                elif parsed.path == "/app.css":
                    self.send_bytes((WEB_ROOT / "app.css").read_bytes(), "text/css; charset=utf-8")
                elif parsed.path == "/ux.css":
                    self.send_bytes((WEB_ROOT / "ux.css").read_bytes(), "text/css; charset=utf-8")
                elif parsed.path == "/app.js":
                    self.send_bytes((WEB_ROOT / "app.js").read_bytes(), "text/javascript; charset=utf-8")
                else:
                    self.send_json({"error": "not found"}, 404)
            except (ValueError, sqlite3.Error, OSError) as exc:
                self.send_json({"error": str(exc)}, 400)

        def log_message(self, fmt, *args):
            print("[dashboard] " + fmt % args)

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(os.environ.get("AMZ_BS_DB_PATH", DEFAULT_DB)))
    parser.add_argument("--host", default="127.0.0.1", help="Use 127.0.0.1 by default; bind a private interface for remote viewing")
    parser.add_argument("--port", type=int, default=8781)
    args = parser.parse_args()
    if not args.db.is_file():
        parser.error(f"SQLite database not found: {args.db}")
    server = ThreadingHTTPServer((args.host, args.port), make_handler(DashboardData(args.db)))
    print(f"Amazon Beauty rank dashboard: http://{args.host}:{args.port} (read-only DB: {args.db})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
