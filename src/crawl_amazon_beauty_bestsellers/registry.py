from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

STATUSES = ("available", "cataloged", "accessible", "production_approved", "disabled")


class Registry:
    def __init__(self, path: Path):
        self.path = path
        self.data: dict[str, Any] = {"categories": []}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))
        if "categories" not in self.data:
            self.data["categories"] = []

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _find(self, node_id: str) -> dict[str, Any] | None:
        for entry in self.data["categories"]:
            if str(entry.get("node_id")) == str(node_id):
                return entry
        return None

    def upsert_discovered(self, node_id: str, name: str, path: str, root_slug: str = "beauty") -> dict[str, Any]:
        existing = self._find(node_id)
        if existing is not None:
            if name:
                existing["name"] = name
            if path and len(path) >= len(str(existing.get("path", ""))):
                existing["path"] = path
            existing.setdefault("root_slug", root_slug)
            return existing
        entry = {
            "node_id": node_id,
            "name": name,
            "path": path,
            "root_slug": root_slug,
            "status": "available",
            "discovered_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "approved_at": None,
            "last_crawled_at": None,
        }
        self.data["categories"].append(entry)
        return entry

    def approve(self, node_id: str) -> bool:
        entry = self._find(node_id)
        if entry is None:
            return False
        entry["status"] = "production_approved"
        entry["approved_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        return True

    def disable(self, node_id: str) -> bool:
        entry = self._find(node_id)
        if entry is None:
            return False
        entry["status"] = "disabled"
        return True

    def mark_crawled(self, node_id: str):
        entry = self._find(node_id)
        if entry is not None:
            entry["last_crawled_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")

    def active_nodes(self) -> list[dict[str, Any]]:
        return [e for e in self.data["categories"] if e.get("status") == "production_approved"]

    def all_entries(self) -> list[dict[str, Any]]:
        return list(self.data["categories"])
