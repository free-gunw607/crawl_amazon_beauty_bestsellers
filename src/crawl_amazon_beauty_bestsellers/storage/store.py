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
            (asin, fetched_at, run_id, title, brand, manufacturer, model_number, seller_name,
             ships_from, buy_box_price, buy_box_currency, buy_box_raw, list_price_amount, list_price_raw,
             availability, date_first_available, bsr_main_rank, bsr_main_category, bsr_other, rating,
             ratings_count, overview, specs, features, ingredients, safety_info, directions,
             description_head, image_urls, variants, variants_count, price_source, parse_warnings)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                d.asin, d.fetched_at, d.run_id, d.title, d.brand, d.manufacturer, d.model_number,
                d.seller_name, d.ships_from, d.buy_box_price, d.buy_box_currency, d.buy_box_raw,
                d.list_price_amount, d.list_price_raw, d.availability, d.date_first_available,
                d.bsr_main_rank, d.bsr_main_category, json.dumps(d.bsr_other), d.rating,
                d.ratings_count, json.dumps(d.overview), json.dumps(d.specs),
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
        return [dict(r) for r in cursor_rows]

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

    def detail_day_rows(self, date_str: str) -> list[dict[str, Any]]:
        rows = self._query(
            "SELECT * FROM product_details WHERE substr(fetched_at,1,10)=? ORDER BY asin",
            (date_str,),
        )
        return [dict(r) for r in rows]

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
