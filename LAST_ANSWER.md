# LAST ANSWER

## Current state (2026-08-31)
- v0.11: **Block-style pipeline** — B0 auto-join + B1 captcha recovery
- Sheet 3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- **Title 100%** all 5 regions (US/DE/UK/FR/ES)
- **Rating 100%** all 5 regions
- **Price**: US 100%, DE 97%, FR 92%, UK 38%, ES 25%
- **Total time**: ~11 min all 5 regions from 0-base
- **Remaining price gap**: Amazon geo-restriction on Korean IP (UK/ES structural)

## Session summary (2026-08-31)
1. **B0 auto-join**: `latest_snapshot()` joins with `product_details` to fill empty titles. Fixed GROUP BY NULL-title bug with `AND title IS NOT NULL AND title != ''` filter.
2. **B1 captcha recovery**: `crawl_details()` now uses `continue` + new client instead of `break` on captcha. Individual ASIN fetch, not batch-stop.
3. **5-region 0-base test**: All regions tested B0+B1 pipeline. Title 100%, Rating 100%, Price varies by geo-restriction.
4. **Code changes**: `pipeline.py` (captcha recovery), `storage/store.py` (auto-join + NULL filter)

## Key discovery
UK Amazon returns prices as `USD5.36` text (not `$5.36` symbol). The `_price_from_raw()` function only matched `$` symbol, causing 100% price extraction failure on amazon.co.uk. Adding one regex pattern fixed 51 UK noprice ASINs instantly.

## Remaining gaps (22 noprice)
Amazon geo-restriction on Korean IP hides prices for ~4% of products. Without proxy/VPN to each target region, cannot reach 100%.

## Git commits
- `ede0103` R6: bootstrap auto-call + noprice fallback
- `b473def` R5: USD switch + enrichment priority
- prior: R1-R4 (rank extraction, captcha, URLs, fill-gaps)

## How to operate
- fill-gaps: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli fill-gaps --region all`
- publish: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli publish-root --region <mp>`
- run full stack: `./repo root-cycle --region <mp>` (list + publish + detail + sheet update)
- tests: `PYTHONPATH=src python -m pytest tests/ -q` (19/19 passing)

## Resume pointer
- everything durable in git + `.agent/`; restart-from-nothing = clone repo + read STATUS.md
