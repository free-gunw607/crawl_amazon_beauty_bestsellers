# LAST ANSWER

## Current state (2026-08-31)
- v0.12: **Block-style pipeline verified** — 0-base, 5 regions, 100% title
- Sheet 3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- **Title 100%** all 5 regions (US/DE/UK/FR/ES) — VERIFIED FROM SCRATCH
- **Price 94.2%** avg (US 100%, DE 99%, UK 100%, FR 88%, ES 83%)
- **Rating 99.4%** avg
- **Total time: ~18.5 min** all 5 regions from 0-base
- **FR bot detection fixed**: fresh client on small response (<500KB)

## Session summary (2026-08-31)
1. **B0 auto-join**: `latest_snapshot()` fills empty titles from product_details
2. **B1 captcha recovery**: `crawl_details()` continues on captcha with new client
3. **FR bot detection**: Amazon FR sets session-token after 1st request → stripped pages
4. **Fix**: detect small response, create fresh client, retry
5. **0-base verification**: All 5 regions title 100%, 0 failures, ~18.5 min total

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
