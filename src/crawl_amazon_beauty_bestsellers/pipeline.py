from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from .config import Settings
from .http_client import AmazonClient, CaptchaBlocked
from .models import ListEntry, ProductDetail, dumps
from .parsers import extract_category_links, parse_list_page, parse_product_detail
from .registry import Registry
from .storage.store import Store, write_details_file, write_snapshot_files


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _atomic_write_json(path: Path, payload: dict[str, Any]):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _manifest_path(settings: Settings, run_id: str) -> Path:
    return settings.resolve(settings.storage.runs_dir) / f"run_{run_id}.json"


class Pipeline:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()
        self.store = Store(self.settings)
        self.registry = Registry(self.settings.resolve("config/category_registry.json"))
        self.client: AmazonClient | None = None

    def _client(self) -> AmazonClient:
        if self.client is None:
            self.client = AmazonClient(self.settings)
        return self.client

    def close(self):
        if self.client is not None:
            self.client.close()
        self.store.close()

    def crawl_list(
        self,
        node_id: str,
        pages: int | None = None,
        run_id: str | None = None,
        trigger: str = "manual",
    ) -> list[ListEntry]:
        run_id = run_id or time.strftime("%Y%m%d_%H%M") + "_" + uuid.uuid4().hex[:6]
        pages = pages or self.settings.crawler.list_pages
        node_path = ""
        entry = self.registry._find(node_id)
        if entry is not None:
            node_path = str(entry.get("path", ""))
        client = self._client()
        all_entries: list[ListEntry] = []
        for page in range(1, pages + 1):
            url = f"{self.settings.amazon.base_url}/Best-Sellers/zgbs/beauty/{node_id}"
            if page > 1:
                url += f"?pg={page}"
            result = client.get(url)
            client.save_raw(result.text, "list", f"{node_id}_p{page}")
            entries = parse_list_page(result.text, node_id, node_path, page, _now(), run_id)
            all_entries.extend(entries)
            if len(entries) == 0 and page > 1:
                break
        self.store.insert_list_entries(all_entries)
        self.registry.mark_crawled(node_id)
        if all_entries:
            write_snapshot_files(self.settings, all_entries)
        return all_entries

    def crawl_details(
        self,
        asins: list[str],
        run_id: str | None = None,
    ) -> tuple[list[ProductDetail], list[dict[str, str]]]:
        run_id = run_id or time.strftime("%Y%m%d_%H%M") + "_" + uuid.uuid4().hex[:6]
        client = self._client()
        details: list[ProductDetail] = []
        failures: list[dict[str, str]] = []
        top = min(len(asins), self.settings.crawler.detail_top)
        for index, asin in enumerate(asins[:top], start=1):
            url = f"{self.settings.amazon.base_url}/dp/{asin}"
            try:
                result = client.get(url)
                client.save_raw(result.text, "detail", asin)
                detail = parse_product_detail(result.text, asin, _now(), run_id)
                details.append(detail)
                self.store.insert_detail(detail)
            except CaptchaBlocked as exc:
                failures.append({"asin": asin, "error": str(exc)})
                break
            except Exception as exc:
                failures.append({"asin": asin, "error": str(exc)})
            print(f"  detail {index}/{top}: {asin}")
        return details, failures

    def run_node(
        self,
        node_id: str,
        include_details: bool = True,
        trigger: str = "manual",
    ) -> dict[str, Any]:
        run_id = time.strftime("%Y%m%d_%H%M") + "_" + uuid.uuid4().hex[:6]
        manifest_path = _manifest_path(self.settings, run_id)
        _atomic_write_json(
            manifest_path,
            {
                "run_id": run_id,
                "started_at": _now(),
                "status": "running",
                "trigger": trigger,
                "node_ids": [node_id],
                "include_details": include_details,
            },
        )
        summary: dict[str, Any] = {"run_id": run_id, "node_id": node_id}
        try:
            entries = self.crawl_list(node_id, run_id=run_id, trigger=trigger)
            summary["list_count"] = len(entries)
            summary["snapshot"] = {
                "min_rank": min((e.rank for e in entries), default=None),
                "with_price": sum(1 for e in entries if e.price_amount is not None),
                "with_rating": sum(1 for e in entries if e.rating is not None),
            }
            details: list[ProductDetail] = []
            failures: list[dict[str, str]] = []
            if include_details and entries:
                ordered = [e.asin for e in sorted(entries, key=lambda x: x.rank)]
                details, failures = self.crawl_details(ordered, run_id=run_id)
                write_details_file(self.settings, details)
            summary["detail_count"] = len(details)
            summary["detail_failures"] = failures
            if details:
                usd = sum(1 for d in details if d.buy_box_currency == "USD")
                with_seller = sum(1 for d in details if d.seller_name)
                with_bsr = sum(1 for d in details if d.bsr_main_rank is not None)
                summary["quality"] = {
                    "usd_price": f"{usd}/{len(details)}",
                    "seller_found": f"{with_seller}/{len(details)}",
                    "bsr_found": f"{with_bsr}/{len(details)}",
                }
            self.store.finish_run(run_id, "completed", ok=len(entries), failed=len(failures))
            _atomic_write_json(
                manifest_path,
                {**summary, "started_at": manifest_path and json.loads(manifest_path.read_text())["started_at"], "status": "completed", "finished_at": _now()},
            )
        except Exception as exc:
            self.store.finish_run(run_id, "failed", ok=0, failed=0, error=str(exc))
            try:
                existing = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
            except json.JSONDecodeError:
                existing = {}
            _atomic_write_json(manifest_path, {**existing, **summary, "status": "failed", "error": str(exc), "finished_at": _now()})
            raise
        return summary

    def discover_categories(self, root_node: str, max_depth: int = 2) -> list[dict[str, str]]:
        client = self._client()
        base = f"{self.settings.amazon.base_url}/Best-Sellers/zgbs/beauty/{root_node}"
        queue: list[tuple[str, int]] = [(root_node, 0)]
        seen: set[str] = set()
        discovered: list[dict[str, str]] = []
        while queue:
            node_id, depth = queue.pop(0)
            if node_id in seen or depth > max_depth:
                continue
            seen.add(node_id)
            url = base if node_id == root_node else f"{self.settings.amazon.base_url}/Best-Sellers/zgbs/beauty/{node_id}"
            result = client.get(url)
            links = extract_category_links(result.text)
            for link in links:
                entry = self.registry.upsert_discovered(link.node_id, link.name, link.path)
                self.store.upsert_category(link.node_id, link.path, link.name, entry["status"])
                discovered.append({"node_id": link.node_id, "name": link.name, "path": link.path})
                if link.node_id not in seen and depth < max_depth:
                    queue.append((link.node_id, depth + 1))
        self.registry.save()
        return discovered

    def active_summary(self) -> dict[str, Any]:
        return dumps(self.store.stats())
