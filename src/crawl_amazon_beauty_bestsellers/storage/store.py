from __future__ import annotations

import csv
import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any

from ..config import Settings
from ..models import ListEntry, ProductDetail, dumps

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    status TEXT NOT NULL,
    trigger TEXT DEFAULT 'manual',
    categories_attempted INTEGER DEFAULT 0,
    ok_count INTEGER DEFAULT 0,
    fail_count INTEGER DEFAULT 0,
    error TEXT
);
CREATE TABLE IF NOT EXISTS list_entries (
    run_id TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    node_id TEXT NOT NULL,
    node_path TEXT,
    page INTEGER,
    rank INTEGER NOT NULL,
    asin TEXT NOT NULL,
    title TEXT,
    url TEXT,
    image_url TEXT,
    rating REAL,
    ratings_count INTEGER,
    price_amount REAL,
    price_currency TEXT,
    price_raw TEXT,
    offers_text TEXT,
    parse_warnings TEXT,
    PRIMARY KEY (run_id, node_id, asin)
);
CREATE INDEX IF NOT EXISTS idx_list_node_time ON list_entries (node_id, fetched_at);
CREATE INDEX IF NOT EXISTS idx_list_asin ON list_entries (asin);
CREATE TABLE IF NOT EXISTS product_details (
    asin TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    run_id TEXT,
    title TEXT,
    brand TEXT,
    manufacturer TEXT,
    model_number TEXT,
    seller_name TEXT,
    ships_from TEXT,
    buy_box_price REAL,
    buy_box_currency TEXT,
    buy_box_raw TEXT,
    list_price_amount REAL,
    list_price_raw TEXT,
    availability TEXT,
    date_first_available TEXT,
    bsr_main_rank INTEGER,
    bsr_main_category TEXT,
    bsr_other TEXT,
    rating REAL,
    ratings_count INTEGER,
    ratings_histogram TEXT,
    overview TEXT,
    specs TEXT,
    features TEXT,
    ingredients TEXT,
    safety_info TEXT,
    directions TEXT,
    description_head TEXT,
    image_urls TEXT,
    variants TEXT,
    variants_count INTEGER DEFAULT 0,
    price_source TEXT,
    parse_warnings TEXT,
    PRIMARY KEY (asin, fetched_at)
);
CREATE INDEX IF NOT EXISTS idx_details_asin ON product_details (asin, fetched_at);
CREATE TABLE IF NOT EXISTS categories (
    node_id TEXT PRIMARY KEY,
    path TEXT,
    name TEXT,
    status TEXT,
    last_crawled_at TEXT
);
CREATE TABLE IF NOT EXISTS health_checks (
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    list_type TEXT,
    checked_at TEXT NOT NULL,
    kind TEXT NOT NULL,
    sample_size INTEGER,
    price_ratio REAL,
    rating_ratio REAL,
    bsr_ratio REAL,
    seller_ratio REAL,
    title_ratio REAL
);
CREATE INDEX IF NOT EXISTS idx_health_node ON health_checks (node_id, checked_at);
"""


class Store:
    def __init__(self, settings: Settings):
        self.settings = settings
        db_path = settings.resolve(settings.storage.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self.lock:
            self.conn.executescript(SCHEMA)
            try:
                self.conn.execute("ALTER TABLE product_details ADD COLUMN ratings_histogram TEXT")
            except sqlite3.OperationalError:
                pass
            try:
                self.conn.execute("ALTER TABLE product_details ADD COLUMN marketplace TEXT DEFAULT 'us'")
            except sqlite3.OperationalError:
                pass
            self.conn.commit()

    def close(self):
        with self.lock:
            self.conn.close()

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        with self.lock:
            return self.conn.execute(sql, params).fetchall()

    def _execute(self, sql: str, params: tuple = (), commit: bool = False):
        with self.lock:
            cursor = self.conn.execute(sql, params)
            if commit:
                self.conn.commit()
            return cursor

    def begin_run(self, run_id: str, trigger: str, categories_attempted: int):
        self._execute(
            "INSERT OR REPLACE INTO runs (run_id, started_at, status, trigger, categories_attempted) VALUES (?, ?, 'running', ?, ?)",
            (run_id, time.strftime("%Y-%m-%dT%H:%M:%S%z"), trigger, categories_attempted),
            commit=True,
        )

    def finish_run(self, run_id: str, status: str, ok: int, failed: int, error: str | None = None):
        self._execute(
            "UPDATE runs SET finished_at=?, status=?, ok_count=?, fail_count=?, error=? WHERE run_id=?",
            (time.strftime("%Y-%m-%dT%H:%M:%S%z"), status, ok, failed, error, run_id),
            commit=True,
        )

    def insert_list_entries(self, entries: list[ListEntry]):
        rows = [
            (
                e.run_id, e.fetched_at, e.node_id, e.node_path, e.page, e.rank, e.asin,
                e.title, e.url, e.image_url, e.rating, e.ratings_count,
                e.price_amount, e.price_currency, e.price_raw, e.offers_text,
                json.dumps(e.parse_warnings),
            )
            for e in entries
        ]
        if not rows:
            return
        with self.lock:
            self.conn.executemany(
                "INSERT OR REPLACE INTO list_entries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                rows,
            )
            self.conn.commit()

    def insert_detail(self, d: ProductDetail):
        self._execute(
            """INSERT OR REPLACE INTO product_details
            (asin, fetched_at, run_id, marketplace, title, brand, manufacturer, model_number, seller_name,
             ships_from, buy_box_price, buy_box_currency, buy_box_raw, list_price_amount, list_price_raw,
             availability, date_first_available, bsr_main_rank, bsr_main_category, bsr_other, rating,
             ratings_count, ratings_histogram, overview, specs, features, ingredients, safety_info, directions,
             description_head, image_urls, variants, variants_count, price_source, parse_warnings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d.asin, d.fetched_at, d.run_id, d.marketplace, d.title, d.brand, d.manufacturer, d.model_number,
                d.seller_name, d.ships_from, d.buy_box_price, d.buy_box_currency, d.buy_box_raw,
                d.list_price_amount, d.list_price_raw, d.availability, d.date_first_available,
                d.bsr_main_rank, d.bsr_main_category, json.dumps(d.bsr_other), d.rating,
                d.ratings_count, json.dumps(d.ratings_histogram), json.dumps(d.overview), json.dumps(d.specs),
                json.dumps(d.features), d.ingredients, d.safety_info, d.directions,
                d.description_head, json.dumps(d.image_urls), json.dumps(d.variants),
                d.variants_count, d.price_source, json.dumps(d.parse_warnings),
            ),
            commit=True,
        )

    def upsert_category(self, node_id: str, path: str, name: str, status: str):
        existing = self._query("SELECT node_id FROM categories WHERE node_id=?", (node_id,))
        if not existing:
            self._execute(
                "INSERT INTO categories (node_id, path, name, status) VALUES (?, ?, ?, ?)",
                (node_id, path, name, status),
                commit=True,
            )
        else:
            self._execute(
                "UPDATE categories SET path=?, name=? WHERE node_id=?",
                (path, name, node_id),
                commit=True,
            )

    def latest_snapshot(self, node_id: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT run_id FROM list_entries WHERE node_id=? ORDER BY fetched_at DESC LIMIT 1",
            (str(node_id),),
        )
        if not rows:
            return []
        cursor_rows = self._query(
            "SELECT * FROM list_entries WHERE node_id=? AND run_id=? ORDER BY rank",
            (str(node_id), rows[0]["run_id"]),
        )
        results = [dict(r) for r in cursor_rows]
        empty_asins = [r["asin"] for r in results if r.get("asin") and not r.get("title")]
        if not empty_asins:
            return results
        placeholders = ",".join("?" * len(empty_asins))
        detail_rows = self._query(
            f"SELECT asin, title, rating, ratings_count, buy_box_price, buy_box_currency, list_price_amount "
            f"FROM product_details WHERE asin IN ({placeholders}) "
            f"AND title IS NOT NULL AND title != '' "
            f"GROUP BY asin",
            empty_asins,
        )
        detail_map = {r["asin"]: dict(r) for r in detail_rows}
        for r in results:
            if not r.get("title") and r["asin"] in detail_map:
                d = detail_map[r["asin"]]
                if d.get("title"):
                    r["title"] = d["title"]
                if not r.get("rating") and d.get("rating"):
                    r["rating"] = d["rating"]
                if not r.get("ratings_count") and d.get("ratings_count"):
                    r["ratings_count"] = d["ratings_count"]
                if not r.get("price_amount") and d.get("buy_box_price"):
                    r["price_amount"] = d["buy_box_price"]
                elif not r.get("price_amount") and d.get("list_price_amount"):
                    r["price_amount"] = d["list_price_amount"]
        return results

    def missing_detail_asins(self, node_id: str) -> list[dict[str, Any]]:
        """ASINs in latest snapshot with no product_details row at all."""
        rows = self._query(
            "SELECT l.asin, l.rank, l.title "
            "FROM list_entries l "
            "WHERE l.node_id = ? "
            "AND l.run_id = ("
            "  SELECT run_id FROM list_entries WHERE node_id = ? "
            "  ORDER BY fetched_at DESC LIMIT 1"
            ") "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM product_details d WHERE d.asin = l.asin"
            ") "
            "ORDER BY l.rank",
            (node_id, node_id),
        )
        return [dict(r) for r in rows]

    def cross_node_titles(self, asins: list[str]) -> dict[str, str]:
        """Look up titles for ASINs from ANY list_entries in the DB."""
        if not asins:
            return {}
        placeholders = ",".join("?" * len(asins))
        rows = self._query(
            f"SELECT asin, title FROM list_entries "
            f"WHERE asin IN ({placeholders}) AND title IS NOT NULL AND title != '' "
            f"GROUP BY asin ORDER BY fetched_at DESC",
            asins,
        )
        return {r["asin"]: r["title"] for r in rows}

    def stale_detail_asins(self, node_id: str) -> list[dict[str, Any]]:
        """ASINs in latest snapshot whose latest detail has empty title."""
        rows = self._query(
            "SELECT l.asin, l.rank, l.title "
            "FROM list_entries l "
            "JOIN product_details d ON l.asin = d.asin "
            "WHERE l.node_id = ? "
            "AND l.run_id = ("
            "  SELECT run_id FROM list_entries WHERE node_id = ? "
            "  ORDER BY fetched_at DESC LIMIT 1"
            ") "
            "AND (d.title IS NULL OR d.title = '') "
            "GROUP BY l.asin "
            "ORDER BY l.rank",
            (node_id, node_id),
        )
        return [dict(r) for r in rows]

    def noprice_detail_asins(self, node_id: str) -> list[dict[str, Any]]:
        """ASINs in latest snapshot with detail but no price (buy_box + list_price both null)."""
        rows = self._query(
            "SELECT l.asin, l.rank, l.title "
            "FROM list_entries l "
            "JOIN product_details d ON l.asin = d.asin "
            "WHERE l.node_id = ? "
            "AND l.run_id = ("
            "  SELECT run_id FROM list_entries WHERE node_id = ? "
            "  ORDER BY fetched_at DESC LIMIT 1"
            ") "
            "AND d.title IS NOT NULL AND d.title != '' "
            "AND d.buy_box_price IS NULL AND d.list_price_amount IS NULL "
            "GROUP BY l.asin "
            "ORDER BY l.rank",
            (node_id, node_id),
        )
        return [dict(r) for r in rows]

    def history_for_asin(self, asin: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT fetched_at, node_id, rank, price_amount, price_currency, rating, ratings_count "
            "FROM list_entries WHERE asin=? ORDER BY fetched_at",
            (asin,),
        )
        return [dict(r) for r in rows]

    def day_latest_rows(self, date_str: str) -> dict[str, list[dict[str, Any]]]:
        result: dict[str, list[dict[str, Any]]] = {}
        nodes = self._query(
            "SELECT DISTINCT node_id FROM list_entries WHERE substr(fetched_at,1,10)=?", (date_str,)
        )
        for node_row in nodes:
            node_id = node_row["node_id"]
            latest = self._query(
                "SELECT run_id FROM list_entries WHERE node_id=? AND substr(fetched_at,1,10)=? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (node_id, date_str),
            )
            if latest:
                rows = self._query(
                    "SELECT * FROM list_entries WHERE node_id=? AND run_id=? ORDER BY rank",
                    (node_id, latest[0]["run_id"]),
                )
                result[node_id] = [dict(r) for r in rows]
        return result

    def trend_rows(self, days: int = 14) -> list[dict[str, Any]]:
        rows = self._query(
            """SELECT substr(fetched_at,1,10) AS day, node_id, asin, MIN(rank) AS best_rank,
                      COUNT(*) AS snapshots, MAX(ratings_count) AS max_ratings
               FROM list_entries
               WHERE fetched_at >= date('now', ?)
               GROUP BY day, node_id, asin
               ORDER BY day DESC, node_id, best_rank""",
            (f"-{days} days",),
        )
        return [dict(r) for r in rows]

    def region_daily_best(self, region: str, days: int = 400) -> list[dict[str, Any]]:
        """Per-node daily best rows for one marketplace region (raw timestamps included).

        US is the legacy lane: its node keys carry no prefix. Other regions use "xx:" prefixed keys.
        """
        if region == "us":
            where, params = "node_id NOT LIKE '%:%'", ()
        else:
            where, params = "node_id LIKE ?", (f"{region}:%",)
        rows = self._query(
            f"""SELECT node_id, asin, fetched_at, MIN(rank) AS best_rank,
                      COUNT(*) AS snapshots, MAX(ratings_count) AS max_ratings
               FROM list_entries
               WHERE {where}
               GROUP BY node_id, asin, substr(fetched_at, 1, 13)
               ORDER BY node_id, asin, fetched_at""",
            params,
        )
        return [dict(r) for r in rows]

    def latest_data_day(self) -> str | None:
        row = self._query("SELECT MAX(substr(fetched_at,1,10)) AS d FROM list_entries")
        return row[0]["d"] if row and row[0]["d"] else None

    def day_asin_categories(self, date_str: str) -> dict[str, list[str]]:
        """Map asin -> node_ids it ranked under on `date_str` (ordered by best rank)."""
        rows = self._query(
            "SELECT asin, node_id, MIN(rank) AS best_rank FROM list_entries "
            "WHERE substr(fetched_at,1,10)=? GROUP BY asin, node_id ORDER BY asin, best_rank",
            (date_str,),
        )
        mapping: dict[str, list[str]] = {}
        for row in rows:
            mapping.setdefault(row["asin"], []).append(str(row["node_id"]))
        return mapping

    def detail_day_rows(self, date_str: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM product_details WHERE substr(fetched_at,1,10)=? ORDER BY asin",
            (date_str,),
        )
        return [dict(r) for r in rows]

    def record_health(
        self,
        run_id: str,
        node_id: str,
        list_type: str,
        kind: str,
        sample_size: int,
        price_ratio: float | None = None,
        rating_ratio: float | None = None,
        bsr_ratio: float | None = None,
        seller_ratio: float | None = None,
        title_ratio: float | None = None,
    ):
        self._execute(
            "INSERT INTO health_checks VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, node_id, list_type, time.strftime("%Y-%m-%dT%H:%M:%S%z"), kind,
                sample_size, price_ratio, rating_ratio, bsr_ratio, seller_ratio, title_ratio,
            ),
            commit=True,
        )

    def recent_health(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM health_checks ORDER BY checked_at DESC LIMIT ?", (limit,)
        )
        return [dict(r) for r in rows]

    def last_completed_run(self) -> dict[str, Any] | None:
        rows = self._query(
            "SELECT run_id, finished_at, status FROM runs WHERE status='completed' ORDER BY started_at DESC LIMIT 1"
        )
        return dict(rows[0]) if rows else None

    def stats(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        out["list_entry_count"] = self._query("SELECT COUNT(*) c FROM list_entries")[0]["c"]
        out["detail_count"] = self._query("SELECT COUNT(*) c FROM product_details")[0]["c"]
        out["distinct_asins"] = self._query("SELECT COUNT(DISTINCT asin) c FROM list_entries")[0]["c"]
        out["runs"] = self._query("SELECT COUNT(*) c FROM runs")[0]["c"]
        out["nodes"] = [
            dict(r)
            for r in self._query("SELECT node_id, name, status, last_crawled_at FROM categories")
        ]
        return out


def write_snapshot_files(
    settings: Settings,
    entries: list[ListEntry],
) -> tuple[Path, Path]:
    stamp_dir = settings.resolve(settings.storage.snapshots_dir) / entries[0].node_id / time.strftime("%Y%m%d_%H%M%S")
    stamp_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = stamp_dir / "list.jsonl"
    csv_path = stamp_dir / "list.csv"
    with jsonl_path.open("w", encoding="utf-8") as fh:
        for entry in entries:
            fh.write(dumps(entry.to_dict()) + "\n")
    fieldnames = [
        "rank", "asin", "title", "rating", "ratings_count",
        "price_amount", "price_currency", "price_raw", "offers_text", "url",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for entry in entries:
            d = entry.to_dict()
            writer.writerow({k: d.get(k, "") for k in fieldnames})
    return jsonl_path, csv_path


def write_details_file(settings: Settings, details: list[ProductDetail]) -> Path | None:
    if not details:
        return None
    out_dir = settings.resolve(settings.storage.details_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{details[0].fetched_at.replace(':', '').replace('-', '')[:15]}.jsonl"
    with path.open("w", encoding="utf-8") as fh:
        for detail in details:
            fh.write(dumps(detail.to_dict()) + "\n")
    return path
