# LAST ANSWER

## Current state (2026-09-01)
- v1.0: **Method 1 confirmed** — production-ready block pipeline
- Sheet 3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- **Title 100%** all 5 regions — VERIFIED FROM SCRATCH
- **Rating 100%** all 5 regions
- **Price 93.2%** avg (US 100%, DE 97%, UK 99%, FR 89%, ES 80%)
- **Total time: ~22 min** all 5 regions from 0-base with polite delays
- **Scheduler**: 1 timer, daily 5AM KST (was 7 timers with complex timezone logic)

## Method 1 Architecture
- **B0**: List crawl (2 pages) → 30 with title + 20 without
- **B1**: Detail crawl for empty-title ASINs → auto-recovery on bot detection
- **Recovery**: reset_session() on small response, 30s cooldown on captcha
- **Politeness**: 1.5-4s between requests + 1s detail delay

## Scheduler (v1.0 simplified)
- **Before**: 7 timers (2h list, 5x MR detail+publish, US detail)
- **After**: 1 timer `amzbs-beauty.timer` at daily 5AM KST (UTC 20:00)
- **Workflow**: `run_job.py` (list + detail all 5 regions) → `publish-sheets --tabs local`
- **Install**: `scripts/install_schedule.sh install`

## Session summary (2026-08-31 → 09-01)
1. **reset_session()**: Clears cookies without full client rebuild (FR bot fix)
2. **detail_delay_seconds**: Configurable delay between detail requests
3. **_parse_rank_safe()**: Handles decimal/suffix ranks (FR 99→100)
4. **has_fresh_detail()**: Incremental update support
5. **0-base verification**: All 5 regions 100% title from scratch
6. **Scheduler simplification**: 7 timers → 1 timer at 5AM KST

## Key discovery
UK Amazon returns prices as `USD5.36` text (not `$5.36` symbol). The `_price_from_raw()` function only matched `$` symbol, causing 100% price extraction failure on amazon.co.uk. Adding one regex pattern fixed 51 UK noprice ASINs instantly.

## Remaining gaps (22 noprice)
Amazon geo-restriction on Korean IP hides prices for ~4% of products. Without proxy/VPN to each target region, cannot reach 100%.

## Git commits
- `8236d99` docs: v1.0 method1 production-ready pipeline
- `a766860` method1: fix all 5 weaknesses for production-ready pipeline
- `c9542de` v0.12 FR bot detection fix
- `0ee9c48` v0.11 block-style pipeline

## How to operate
- fill-gaps: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli fill-gaps --region all`
- publish: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli publish-root --region <mp>`
- run full stack: `./repo root-cycle --region <mp>` (list + publish + detail + sheet update)
- tests: `PYTHONPATH=src python -m pytest tests/ -q` (19/19 passing)
- scheduler: `scripts/install_schedule.sh install|uninstall|status`

## Resume pointer
- everything durable in git + `.agent/`; restart-from-nothing = clone repo + read STATUS.md
