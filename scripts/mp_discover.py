#!/usr/bin/env python3
"""Discover beauty bestseller categories for a gp-style marketplace.

Usage:
  PYTHONPATH=src python3 scripts/mp_discover.py --marketplace de
Registers entries as "<mp>:<node_id>" (status=available) in the shared registry.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bs4 import BeautifulSoup

from crawl_amazon_beauty_bestsellers.config import load_settings
from crawl_amazon_beauty_bestsellers.http_client import AmazonClient
from crawl_amazon_beauty_bestsellers.registry import Registry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--marketplace", required=True)
    parser.add_argument("--depth-links", type=int, default=60)
    args = parser.parse_args()

    settings = load_settings()
    profile = settings.marketplace(args.marketplace)
    if profile is None or profile.code == "us":
        print(f"unsupported marketplace for discovery: {args.marketplace}")
        return 2

    client = AmazonClient(settings, marketplace=profile)
    registry = Registry(settings.resolve("config/category_registry.json"))

    result = client.get(profile.base_url + "/gp/bestsellers/beauty/")
    soup = BeautifulSoup(result.text, "lxml")
    seen: dict[str, str] = {}
    anchors = soup.select("a[href*='/gp/bestsellers/beauty/']")
    if not anchors:
        anchors = soup.select("a[href*='/zgbs/beauty/']")
    for anchor in anchors:
        href = anchor.get("href") or ""
        digits = ""
        for token in (href.split("/beauty/") + [""])[1:]:
            if token[:1].isdigit():
                digits = token.split("?")[0].split("/")[0]
                break
        if not digits.isdigit():
            continue
        name = anchor.get_text(" ", strip=True)
        if not name and anchor.find("img") is not None:
            name = str(anchor.find("img").get("alt") or "")
        if not name:
            continue
        seen.setdefault(digits, name)

    registered = []
    for node_id, name in list(seen.items())[: args.depth_links]:
        key = f"{profile.code}:{node_id}"
        entry = registry.upsert_discovered(key, name, f"beauty > {name}", root_slug="beauty")
        entry["marketplace"] = profile.code
        registered.append((key, name))
    registry.save()
    for key, name in registered:
        print(f"{key}\t{name}")
    print(f"registered: {len(registered)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
