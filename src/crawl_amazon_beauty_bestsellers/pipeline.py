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


LIST_TYPE_PATHS = {
    "bestsellers": "/Best-Sellers/zgbs",
    "new_releases": "/gp/new-releases",
    "movers_and_shakers": "/gp/movers-and-shakers",
    "most_wished_for": "/gp/most-wished-for",
}


def build_list_url(base_url: str, root_slug: str, node_id: str, list_type: str = "bestsellers", page: int = 1) -> str:
    if list_type not in LIST_TYPE_PATHS:
        raise ValueError(f"unknown list_type: {list_type}")
    url = f"{base_url}{LIST_TYPE_PATHS[list_type]}/{root_slug}/{node_id}"
    if page > 1:
        url += f"?pg={page}"
    return url


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
        self.clients: dict[str, AmazonClient] = {}

    def _client(self, marketplace=None) -> AmazonClient:
        key = marketplace.code if marketplace is not None else "_legacy"
        if key not in self.clients:
            self.clients[key] = AmazonClient(self.settings, marketplace=marketplace)
        return self.clients[key]

    def close(self):
        for client in self.clients.values():
            client.close()
        self.store.close()

    @staticmethod
    def _split_key(node_key: str) -> tuple[str | None, str]:
        text = str(node_key)
        if ":" in text:
            mp, raw = text.split(":", 1)
            return mp.lower(), raw
        return None, text

    def _marketplace_profile(self, node_key: str):
        mp_code, _ = self._split_key(node_key)
        if mp_code is None:
            return None, None
        profile = self.settings.marketplace(mp_code)
        return (mp_code, profile) if profile else (mp_code, None)

    def _resolve_node(self, node_id: str, root_slug: str | None) -> tuple[str, str]:
        entry = self.registry._find(node_id)
        if entry is None:
            _, raw = self._split_key(node_id)
            return (root_slug or "beauty"), ""
        path = str(entry.get("path", ""))
        slug = root_slug or entry.get("root_slug") or "beauty"
        return slug, path

    def crawl_list(
        self,
        node_id: str,
        pages: int | None = None,
        run_id: str | None = None,
        trigger: str = "manual",
        list_type: str = "bestsellers",
        root_slug: str | None = None,
    ) -> list[ListEntry]:
        run_id = run_id or time.strftime("%Y%m%d_%H%M") + "_" + uuid.uuid4().hex[:6]
        pages = pages or self.settings.crawler.list_pages
        slug, node_path = self._resolve_node(node_id, root_slug)
        mp_code, profile = self._marketplace_profile(node_id)
        base_url = profile.base_url if profile else self.settings.amazon.base_url
        client = self._client(profile)
        _, raw_node = self._split_key(node_id)
        all_entries: list[ListEntry] = []
        for page in range(1, pages + 1):
            url = build_list_url(base_url, slug, raw_node, list_type, page)
            result = client.get(url)
            client.save_raw(result.text, f"list_{list_type}", f"{node_id}_p{page}")
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
        expand_variants: bool = False,
        marketplace: str | None = None,
    ) -> tuple[list[ProductDetail], list[dict[str, str]]]:
        run_id = run_id or time.strftime("%Y%m%d_%H%M") + "_" + uuid.uuid4().hex[:6]
        mp_code, profile = (self._marketplace_profile(marketplace) if marketplace else (None, None))
        base_url = profile.base_url if profile else self.settings.amazon.base_url
        client = self._client(profile)
        details: list[ProductDetail] = []
        failures: list[dict[str, str]] = []

        def _fetch(batch_asins: list[str], label_prefix: str) -> int:
            top = min(len(batch_asins), self.settings.crawler.detail_top)
            fetched = 0
            for index, asin in enumerate(batch_asins[:top], start=1):
                url = f"{base_url}/dp/{asin}"
                try:
                    result = client.get(url)
                    client.save_raw(result.text, "detail", asin)
                    detail = parse_product_detail(result.text, asin, _now(), run_id)
                    detail.marketplace = mp_code or "us"
                    details.append(detail)
                    self.store.insert_detail(detail)
                    fetched += 1
                except CaptchaBlocked as exc:
                    failures.append({"asin": asin, "error": str(exc)})
                    break
                except Exception as exc:
                    failures.append({"asin": asin, "error": str(exc)})
                print(f"  {label_prefix} {index}/{top}: {asin}")
            return fetched

        _fetch(asins, "detail")
        if expand_variants:
            variant_budget = 25
            per_parent = 5
            queued: list[str] = []
            seen = set(asins)
            for detail in details:
                for variant in detail.variants[:per_parent]:
                    vasin = str(variant.get("asin", ""))
                    if vasin and vasin not in seen and len(queued) < variant_budget:
                        seen.add(vasin)
                        queued.append(vasin)
            if queued:
                print(f"  variants: fetching {len(queued)} bounded variant ASINs")
                _fetch(queued, "variant")
        return details, failures

    def run_node(
        self,
        node_id: str,
        include_details: bool = True,
        trigger: str = "manual",
        list_type: str = "bestsellers",
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
                "list_type": list_type,
                "include_details": include_details,
            },
        )
        summary: dict[str, Any] = {"run_id": run_id, "node_id": node_id, "list_type": list_type}
        try:
            entries = self.crawl_list(node_id, run_id=run_id, trigger=trigger, list_type=list_type)
            if entries:
                self.store.record_health(
                    run_id, node_id, list_type, "list", len(entries),
                    price_ratio=sum(1 for e in entries if e.price_amount is not None) / len(entries),
                    rating_ratio=sum(1 for e in entries if e.rating is not None) / len(entries),
                    title_ratio=sum(1 for e in entries if e.title) / len(entries),
                )
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
                details, failures = self.crawl_details(
                    ordered, run_id=run_id, expand_variants=True, marketplace=str(node_id)
                )
                write_details_file(self.settings, details)
            summary["detail_count"] = len(details)
            summary["detail_failures"] = failures
            if details:
                self.store.record_health(
                    run_id, node_id, list_type, "detail", len(details),
                    price_ratio=sum(1 for d in details if d.buy_box_price is not None or d.list_price_amount is not None) / len(details),
                    bsr_ratio=sum(1 for d in details if d.bsr_main_rank is not None) / len(details),
                    seller_ratio=sum(1 for d in details if d.seller_name) / len(details),
                    title_ratio=sum(1 for d in details if d.title) / len(details),
                )
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

    def discover_categories(self, root_node: str, max_depth: int = 2, root_slug: str | None = None) -> list[dict[str, str]]:
        slug, _ = self._resolve_node(root_node, root_slug)
        mp_code, profile = self._marketplace_profile(root_node)
        base_url = profile.base_url if profile else self.settings.amazon.base_url
        client = self._client(profile)
        _, raw_root = self._split_key(root_node)
        queue: list[tuple[str, int]] = [(raw_root, 0)]
        seen: set[str] = set()
        discovered: list[dict[str, str]] = []
        while queue:
            node_id, depth = queue.pop(0)
            if node_id in seen or depth > max_depth:
                continue
            seen.add(node_id)
            url = build_list_url(base_url, slug, node_id)
            result = client.get(url)
            links = extract_category_links(result.text)
            for link in links:
                key = f"{mp_code}:{link.node_id}" if mp_code else link.node_id
                entry = self.registry.upsert_discovered(key, link.name, link.path, root_slug=slug)
                if mp_code:
                    entry["marketplace"] = mp_code
                self.store.upsert_category(key, link.path, link.name, entry["status"])
                discovered.append({"node_id": key, "name": link.name, "path": link.path})
                if link.node_id not in seen and depth < max_depth:
                    queue.append((link.node_id, depth + 1))
        self.registry.save()
        return discovered

    def active_summary(self) -> dict[str, Any]:
        return dumps(self.store.stats())
