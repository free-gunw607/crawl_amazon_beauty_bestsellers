# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers` — **PUBLIC**: https://github.com/free-gunw607/crawl_amazon_beauty_bestsellers
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon.com beauty bestseller lists + product/vendor intelligence on a 6h cycle; publish a public time-series dataset via commit-back and rich workbooks to Drive

## Live Google Sheet
https://docs.google.com/spreadsheets/d/1UlvJ5T-oA3qr7TkG8KIG_Jw1R6xUiEa5dszrjN6X2HU/edit
- CI lane writes panel list tabs (SA cell-writes are quota-free — verified from runner)
- local lane owns details/specs_long/trend tabs (fires with cron daemon)
- xlsx sheets renamed to category names; each panel sheet links to its Amazon Best Sellers page
- every tab carries a freshness stamp row (마지막 갱신 시각 + 라인) so cloud/local drift is visible
- publisher writes chunked with row-offset ranges + auto grid resize (full specs_long lands intact)

## Current phase
v0.11 BLOCK-STYLE PIPELINE: B0 AUTO-JOIN + B1 CAPTCHA RECOVERY (2026-08-31)
- **B0 (latest_snapshot auto-join)**: `latest_snapshot()` now auto-fills empty titles/ratings/prices from `product_details` table. Added `AND title IS NOT NULL AND title != ''` filter to prevent NULL-title records from winning GROUP BY. Result: 84%→93% title without any re-crawl.
- **B1 (captcha recovery)**: `crawl_details()` now replaces `break` with `continue` + new client on captcha. ASINs are fetched individually, not batch-stopped. On captcha, new `AmazonClient` is created with fresh location bootstrap.
- **5-region 0-base results**: Title 100% (all 5), Rating 100% (all 5), Price: US 100%, DE 97%, FR 92%, UK 38%, ES 25%.
- **Total time**: US 36s, DE 44s, UK 122s, FR 232s, ES 246s (~11 min total).
- **Price gap root cause**: Amazon geo-restriction on Korean IP for non-US/DE regions. UK 38% and ES 25% are structural limitations without proxy/VPN.
- Tests: 19/19 passing.
- **UK parser fix**: Added `USD\s?([\d.,]+)` regex pattern to `_price_from_raw()` in `bestseller_list.py`. Amazon UK returns prices as `USD5.36` text (not `$5.36` symbol). This single fix recovered 51 UK noprice ASINs.
- **Region-aware bootstrap**: `bootstrap_us_location()` now uses marketplace-specific base_url and delivery zip codes (US: 10001, UK: EC1A 1BB, DE: 10115, FR: 75001, ES: 28001). Previously all marketplaces posted to amazon.com regardless of target region.
- **fill-gaps local fallback**: Modified CLI to try local marketplace when US fetch returns no price (not just when US fetch fails). Previously only empty-title failures triggered local fallback.
- **Sheet 3 state**: US 100%, UK 94% price, DE 85% price, FR 81% price, ES 56% price.
- **Remaining noprice (22)**: Amazon geo-restriction on Korean IP. Without proxy/VPN to each region, ~4% of products remain price-hidden.
- Tests: 19/19 passing.

## Prior phase notes
v0.9 USD PRICE SWITCH + BOOTSTRAP AUTO-PIN (2026-08-30)
- **bootstrap_us_location()** now auto-called in `_client()` on every new AmazonClient — pins delivery to NY 10001 (New York) via `glow-address-change` form POST. This resolves the core issue where Amazon hid `buy_box_price` for items it deemed "not shippable to delivery location" (Korean IP geolocation).
- **Currency switched KRW → USD** for all marketplaces. Sheet 3 column header: `price_usd`.
- **noprice 2-step fallback**: for ASINs with detail records but no price, `fill-gaps` deletes stale records and re-fetches from US (amazon.com), then falls back to local marketplace for failures.
- **Enrichment query** now prefers detail records WITH prices: `ORDER BY (buy_box_price IS NOT NULL OR list_price_amount IS NOT NULL) DESC, fetched_at DESC`.
- **Sheet 3 final state**: Title 481/500 (96%), URL 500/500 (100%), **Price 421/500 (84%)**, Rating 481/500 (96%).
- **Remaining 79 price-less ASINs**: Amazon's geo-based shipping restriction policy. Even with NY delivery pin, Amazon still hides prices for ~16% of products on its own platform when accessed from Korean IP. Requires proxy/VPN to each target region for 100% coverage.
- **Remaining 19 title gaps**: list_entries crawled with empty titles (parser gap on certain page layouts); detail records also missing/empty → enrichment can't fill.

## Prior phase notes
v0.8 CAPTCHA RECOVERY + SHEET3 ENRICHMENT (2026-08-30)
- `break` → `continue` on captcha detection; marketplace auto-detect; UA pool 3→10.
- `root_panel_grid` DB-join enrichment: title/rating/ratings_count/price filled from `product_details` when list entry is sparse.
- `list_price_amount` fallback when `buy_box_price` is null.
- 5 regional midnight timers + legacy ET-midnight; list 2h timer.

v0.7 FULL-RANK 1..100 + SHEET3 PRIMARY (2026-08-26)
- Rank gap FIXED: zgbs pages embed complete ranked list in `data-client-recs-list` JSON. `parse_list_page` merges DOM rows with recs-list skeleton → 100 ranked items, zero gaps.
- SHEET 3 = future primary: `beauty_personal_care_top100_live` (`1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80`)

## Proven architecture (empirically validated 2026-08-25)
| lane | runs | covers | status |
|---|---|---|---|
| GitHub Actions (`collect.yml`) | 6h at :47 UTC + manual | list snapshots all 8 panels → commit-back (public dataset) + workbook export | LIVE, verified 3 dispatches (ok:8/failed:0) |
| Local crontab (home IP) | 6h at :17 KST (02/08/14/20) | detail/vendor pass (/dp/ works only from residential IP) | registered; fires once cron daemon starts (owner sudo) |
| Manual | anytime | `./repo run --node <id>` etc. | proven |

Key empirical finding: Azure runner IPs get served zgbs list pages fine but are captcha-blocked on /dp/ detail pages on first hit; pipeline's stop-on-block policy degrades gracefully to list-only per node.

## Production panels (8, registry `production_approved`)
Skin Care 11060451 · Face 11060711 · Body 11060521 · Eyes 11061941 · Moisturizers 11060661 · Sunscreens 11062651 · Body Washes 11056291 · Face Serums 7792528011 (recovered after double block) — plus 59 categories registered `available`

## Drive publishing
- CI: `GCP_SA_JSON` secret path wired in workflow (auto-skips until secret registered)
- Local: `./repo upload-drive` via gws OAuth — verified end-to-end (file `11qQcoXJc5cisiTug7a_HIY3res7G3UUi`)
- folder `crawl_amazon_beauty_bestsellers`: `1xns4GiMLt1ZPa8me9At4IpgWDyB-SOgp`

## Data policy (public repo)
- git history includes collected data through 2026-08-25 (owner-approved public dataset)
- from now: SQLite is local-only (`.gitignore`); commit-back = per-node `list.csv/jsonl` snapshots + daily xlsx via `github-actions[bot]`
- CI DB accumulation persists across runs via `actions/cache`

## Block event log (2026-08-25, all recovered/handled)
1. local hard block on Serums detail → cooldown recovery ✓
2. local soft block (50 empty parses) → junk purge + cooldown + clean retry ✓
3. runner /dp/ captcha → structural answer: split lanes (cloud lists / local details) ✓

## Pending owner actions
1. GCP service account JSON (console steps provided) → I register `GCP_SA_JSON` secret → CI Drive publish activates
2. optional: `sudo apt install -y jq unzip sqlite3` on liam3 (CLI conveniences; crawler itself unaffected — python sqlite3 module works)
3. note: `gws` CLI absent on liam3 → local `upload-drive` unavailable there until gws is ported; CI/Drive path unaffected
4. RESOLVED 2026-08-26: local-tab refresh live via token backend (no SA JSON needed for Sheets lane; SA JSON still wanted for CI Drive workbook upload)
5. optional: port `gws` from liam2 (Hanseong, sole node holding it) if other gws-dependent workflows are ever needed on liam3

## Progress snapshot
- overall progress: 95% — both lanes built & proven; remaining = owner-side credentials/daemon start
- confidence: high for cloud lists; high for local details (proven); watch item = runner IP reputation over time

## Next actions
1. owner: SA JSON → secret registration → verify CI Drive step turns green-with-upload
2. owner: cron daemon start → verify `.agent/logs/cron_local.log` after next :17 KST window
3. after several clean days: next registry batch (registry-first lifecycle)

## Wisdomhouse — PROMOTED (owner-approved 2026-08-26)
Episode `EP-AMZBS-DUALOPS-20260826-01`, canonical doc A2 `Wisdomhouse/by-repo/crawl_amazon_beauty_bestsellers.md`:
- `WH-CRAWL-AMZBS-001` soft-block telemetry (purge+cooldown protocol)
- `WH-CRAWL-AMZBS-002` cloud-lists/local-details lane split
- `WH-RUNTIME-AMZBS-001` privilege-free scheduler loop, crontab takeover
- `WH-DATA-AMZBS-001` SA file-upload quota vs Sheets cell-writes; formula-driven derived tabs
