from __future__ import annotations

"""Recover blank root-rank-history titles from the matching Amazon marketplaces.

Only the existing title cells in root_rank_history are updated. No rows are
inserted, removed, or rewritten. A CAPTCHA/block signal stops all lookups.
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
REGIONS = ("us", "de", "uk", "fr", "es")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-items", type=int, default=100)
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()

    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from enrich_titles_until_complete import (
        DEFAULT_FALLBACK_MARKETS,
        _batch_update_values,
        _env,
        _gws_values,
        _title_overrides,
    )
    from crawl_amazon_beauty_bestsellers.config import load_settings
    from crawl_amazon_beauty_bestsellers.http_client import AmazonClient, CaptchaBlocked

    env = _env()
    rows = _gws_values("root_rank_history!A:I", env)
    missing: dict[tuple[str, str], list[int]] = defaultdict(list)
    for row_num, row in enumerate(rows[1:], start=2):
        if len(row) < 4:
            continue
        day, region, asin = (str(row[i]).strip() if len(row) > i else "" for i in (0, 1, 2))
        title = str(row[8]).strip() if len(row) > 8 else ""
        region = region.lower()
        if day and region in REGIONS and asin and not title:
            missing[(region, asin)].append(row_num)

    settings = load_settings(REPO_ROOT)
    overrides = _title_overrides()
    clients: dict[str, AmazonClient] = {}
    updates: list[dict[str, object]] = []
    recovered: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    stopped_on_block = False
    try:
        for (region, asin), row_numbers in list(missing.items())[: max(0, args.max_items)]:
            title = overrides.get(f"{region}:{asin}".lower(), "") or overrides.get(asin.lower(), "")
            source = "override" if title else ""
            ordered_markets = list(dict.fromkeys([region, *DEFAULT_FALLBACK_MARKETS]))
            for market in ordered_markets if not title else []:
                profile = settings.marketplace(market)
                if profile is None:
                    continue
                client = clients.get(market)
                if client is None:
                    client = AmazonClient(settings, marketplace=profile)
                    clients[market] = client
                try:
                    response = client.get(f"{profile.base_url}/dp/{asin}")
                except CaptchaBlocked:
                    stopped_on_block = True
                    break
                except Exception:
                    continue
                soup = BeautifulSoup(response.text, "html.parser")
                node = soup.select_one("#productTitle")
                title = node.get_text(" ", strip=True).strip() if node else ""
                if title:
                    source = market
                    break
            if title:
                for row_num in row_numbers:
                    updates.append({"range": f"'root_rank_history'!I{row_num}", "values": [[title[:140]]]})
                recovered.append({"region": region.upper(), "asin": asin, "source": source, "title": title[:140]})
            else:
                unresolved.append({"region": region.upper(), "asin": asin})
            if stopped_on_block:
                break
    finally:
        for client in clients.values():
            client.close()

    if updates:
        _batch_update_values(updates, env, chunk_size=100)
    result = {
        "missing_groups": len(missing),
        "updated_history_cells": len(updates),
        "recovered_asins": recovered,
        "unresolved": unresolved,
        "stopped_on_block": stopped_on_block,
        "checked_at": time.strftime("%Y-%m-%d %H:%M %Z"),
    }
    print(json.dumps(result, ensure_ascii=False))
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
