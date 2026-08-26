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
v0.7 FULL-RANK 1..100 + SHEET3 PRIMARY (2026-08-26)
- **Rank gap FIXED for all regions/sheets**: zgbs pages embed the complete ranked list in `data-client-recs-list` JSON (p1=1..50, p2=51..100; verified US/UK/DE/FR/ES). `parse_list_page` now merges DOM rows (rich fields) with recs-list skeleton (`metadata_only` warning on unrendered rows) → nodes yield exactly 100 ranked items, zero gaps.
- **detail_top raised 50→100** (settings.yml + default): midnight detail passes now enrich every ranked item.
- **SHEET 3 = future primary**: `beauty_personal_care_top100_live` (id `1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80`) — per-country ROOT Beauty & Personal Care list only: `[XX] Top 100` snapshots + append-only `root_rank_history` + `trend_14d` (prev/delta). Root stored in SQLite as synthetic keys (`ROOT`, `<mp>:ROOT`, status cataloged — excluded from 2h rotation, crawled once daily inside `root-cycle` at each region's local midnight via ExecStartPost on all 5 mr units + legacy ET unit).
  - **CLOSURE DECISION (owner, 2026-08-26)**: once sheet3 burn-in looks good, sheets 1 & 2 will be CLOSED; sheet3 is the keeper. Sheets 1&2 keep updating automatically until owner gives the close order.
- Legacy lane (sheet1): unchanged behavior + full-rank fix. MR lane (sheet2): unchanged + full-rank fix.
- Politeness note 2026-08-26 evening: amazon.de served a soft block after a heavy manual day; stop-on-block honored (cooldown ≥55min), DE root snapshot will land via its 07:00 KST timer.

## Prior phase notes
v0.6 MULTIREGION DUAL-SHEET OPERATIONS (2026-08-26)
- **Legacy sheet** (untouched): US-only lane as before — lists every 2h; detail pass moved from 4x daily to **ET-midnight once** (`crawl-amazon-bs-details.timer` OnCalendar `*-*-* 00:00:00 America/New_York`); publishes via token backend.
- **NEW MR sheet** `crawl_amazon_beauty_bestsellers_multiregion_live` (id `1A9PVMIrsTAEXROBLS8RPmF3SrFQXsHPVCIiOLeV_cHk`): 5 marketplaces **US/UK/DE/FR/ES**, tabs `[XX] Category` + append-only **`rank_history`** (date|region|category|asin|rank|price_krw|...) + `trend_14d` with **prev_rank/delta** columns; per-region local-midnight units `amzbs-mr-{us,uk,de,fr,es}.timer` (KST: de/es/fr 07:00, uk 08:00, us 13:00; DST auto).
- Prices standardized **KRW** across all regions via `i18n-prefs=KRW` cookie (no delivery pinning needed for MR lane; legacy USD pinning unchanged).
- Registry: 28 production_approved = 8 legacy US + 20 MR (5 themes x 4 new markets), all validated live (60/60 items, ~100% price/rating coverage). Composite keys `<mp>:<node>`; US keys stay unprefixed to protect legacy sheet.
- EU URL scheme `/gp/bestsellers/beauty/<node>` vs UK/US zgbs-style — handled by profile `url_style`.

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
