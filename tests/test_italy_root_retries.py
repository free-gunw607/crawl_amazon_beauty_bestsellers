from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers import pipeline as pipeline_module
from crawl_amazon_beauty_bestsellers.config import Settings
from crawl_amazon_beauty_bestsellers.models import ListEntry
from crawl_amazon_beauty_bestsellers.pipeline import IncompleteItalyRootSnapshot, Pipeline


class FakeStore:
    def __init__(self) -> None:
        self.inserted: list[list[ListEntry]] = []

    def insert_list_entries(self, rows: list[ListEntry]) -> None:
        self.inserted.append(rows)


class FakeRegistry:
    def _find(self, _node_id: str):
        return None

    def mark_crawled(self, _node_id: str) -> None:
        pass


class FakeClient:
    def __init__(self) -> None:
        self.calls = 0

    def get(self, url: str):
        self.calls += 1
        return SimpleNamespace(text=f"page-{self.calls}")

    def save_raw(self, *_args) -> None:
        pass


def _rows(page: int, run_id: str, *, duplicate: bool) -> list[ListEntry]:
    result = []
    for rank in range(1 + (page - 1) * 50, 1 + page * 50):
        asin_rank = 50 if duplicate and rank == 51 else rank
        result.append(ListEntry(
            run_id=run_id, fetched_at="2026-11-03T00:00:00+00:00", node_id="it:ROOT",
            node_path="", page=page, rank=rank, asin=f"B0{asin_rank:08d}",
            title=f"item {asin_rank}", url=f"https://www.amazon.it/dp/B0{asin_rank:08d}",
        ))
    return result


def _pipeline(monkeypatch, duplicate_by_attempt: dict[int, bool]) -> tuple[Pipeline, FakeStore, FakeClient]:
    pipe = object.__new__(Pipeline)
    pipe.settings = Settings()
    pipe.settings.crawler.list_pages = 2
    pipe.store = FakeStore()
    pipe.registry = FakeRegistry()
    client = FakeClient()
    pipe._client = lambda _profile: client
    attempts = {"count": 0}

    def parse(_html, _node, _path, page, _fetched, run_id, *, base_url):
        if page == 1:
            attempts["count"] += 1
        return _rows(page, run_id, duplicate=duplicate_by_attempt[attempts["count"]])

    monkeypatch.setattr(pipe, "_resolve_node", lambda *_args: ("beauty", ""))
    monkeypatch.setattr(pipe, "_marketplace_profile", lambda *_args: ("it", pipe.settings.marketplace("it")))
    monkeypatch.setattr(pipeline_module, "parse_list_page", parse)
    monkeypatch.setattr(pipeline_module, "write_snapshot_files", lambda *_args: None)
    return pipe, pipe.store, client


def test_italy_retries_incomplete_pair_and_persists_only_complete_snapshot(monkeypatch) -> None:
    pipe, store, client = _pipeline(monkeypatch, {1: True, 2: False})

    rows = pipe.crawl_list("it:ROOT", run_id="test")

    assert len(rows) == 100
    assert len({row.asin for row in rows}) == 100
    assert len(store.inserted) == 1
    assert store.inserted[0] == rows
    assert client.calls == 4


def test_italy_exhausted_pairs_do_not_persist_partial_snapshot(monkeypatch) -> None:
    pipe, store, client = _pipeline(monkeypatch, {1: True, 2: True, 3: True})

    with pytest.raises(IncompleteItalyRootSnapshot) as caught:
        pipe.crawl_list("it:ROOT", run_id="test")

    assert caught.value.unique_asins == 99
    assert caught.value.attempts == 3
    assert store.inserted == []
    assert client.calls == 6
