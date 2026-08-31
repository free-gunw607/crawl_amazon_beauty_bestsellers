# LAST ANSWER

## Current state (2026-08-31)
- v0.10: **Sheet 3 live** with 5-region Beauty & Personal Care Top 100
- Sheet 3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- **UK parser fix**: `USD\s?(\d.+)` regex recovers 51 UK noprice ASINs
- **Region-aware bootstrap**: marketplace-specific base_url + delivery zip
- **Final coverage**: US 100%, UK 94% price, DE 85% price, FR 81% price, ES 56% price
- **Remaining noprice (22)**: Amazon geo-restriction on Korean IP

## Session summary (2026-08-31)
1. **R7-1**: UK parser fix — `_price_from_raw()` now handles `USD5.36` text format (not just `$5.36` symbol)
2. **R7-2**: Region-aware bootstrap — `bootstrap_us_location()` uses marketplace-specific base_url and delivery zip (US:10001, UK:EC1A 1BB, DE:10115, FR:75001, ES:28001)
3. **R7-3**: fill-gaps local fallback — CLI now tries local marketplace when US fetch returns no price (not just empty title)
4. **All fill-gaps + publish** for 5 regions

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
