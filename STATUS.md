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
v0.5 SHEETS-LIVE DUAL-LANE OPERATIONS — GitHub Actions collects public list snapshots every 6h; local lane owner = **liam3** since 2026-08-26: systemd-user timers (`crawl-amazon-bs.timer` list every 2h :00+jitter≤10m, `-details.timer` 01/07/13/19:30 KST +jitter, linger on) running from `%h/.../crawl_amazon_beauty_bestsellers/.venv`; detail pass auto-publishes details/specs_long/trend_14d via new **token backend** (shared OAuth store `~/.config/gsheet-sync`; live write verified 2026-08-26 16:56 KST — 3 tabs, 8,280 rows). liam1 amazon crontab lines DISABLED same day (backup `liam1:~.../crawl_amazon_beauty_bestsellers/.agent/crontab_backup_20260826.txt`) after live overlap detected; liam1 SQLite history (8/25–26, 4,860 list + 844 details) merged into liam3 runtime DB. `gws` CLI confirmed absent on BOTH liam1 and liam3 → token backend is canonical local-lane auth.

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
