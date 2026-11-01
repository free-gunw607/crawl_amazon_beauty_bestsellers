# LAST ANSWER

## 2026-11-01 — Workbench launch and runtime fixes (Sites v29–v31)
- Added Workbench as a distinct sidebar tab, separate from Overview. It provides archive-driven dashboards, date/market/brand/product filters, line/bar/heatmap/table visualizations, draggable field shelves, multiple local dashboards, save/share/import/export controls, and archive coverage/fingerprint export.
- Live QA found two release defects in sequence: missing `state.workbench` initialization, then undefined `isRank` in the default rank-bar chart. Both are fixed in current v31.
- Browser verified the canonical URL loads the 2026-11-01 snapshot, Workbench canvas and four default cards render, Add visualization opens the field-shelf editor, and no error banner or JavaScript errors remain.
- Current source `efbdce50f01ec76f7d63622fcadd2f789c44466a`; saved version `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_51a571e18ae88191b1b386ff059bc5a9`; deployment `appgdep_6ae6b2429acc8191b753f8904b1057b2` succeeded at https://liambeautyindex.dpdns.org. Rollback target: v28 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_c7c0fbd89fb081919dae1b28a0c063ca`.
- Dashboard layout is saved per browser in localStorage; share URL carries dashboard configuration, not data. Google Sheet and fallback XLSX are untouched.


## 2026-11-01 — Custom comparison periods and inline Brands panel, v22.5.1 (Sites v28)
- Added free day-count comparison windows to Trends and Brand profile Trend; baselines use the nearest archived capture on or before the target date.
- Moved Compare brands into an expandable panel inside Brands → Brand directory. It retains up to three brands, share history, and the five-market table.
- Added the requested small gray Trends note: counts compare listings present at both endpoints; current listings absent from the baseline are called out separately.
- Published v28 at https://liambeautyindex.dpdns.org. Build, artifact validation, and deployment succeeded; browser interaction QA is pending. Source `0e1b789ea0bf6fc911384d6894e452fe45666875`; saved version `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_c7c0fbd89fb081919dae1b28a0c063ca`; deployment `appgdep_6ae6a4f8fbd0819193a979ad6b24fc6f`. Rollback: v22.4 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_7f2c4cdc941081918dfc0e429365f885`.
- Website-only release; Google Sheet and fallback XLSX untouched.
## 2026-11-01 — Brands comparison and logo upgrade, v22.4 (Sites v26)
- Added a Compare brands tab in Brands. Select up to three brands, compare 7/30/60-day Top 100 listing share in the selected market, and compare share/average rank/best rank across the five markets.
- Repaired Trends Brand Share point labels: the tooltip now identifies the actual brand, exact date, share, and snapshot context instead of displaying `Series 1`.
- Added 11 bundled brand marks: CeraVe, Garnier, Maybelline, medicube, The Ordinary, Revlon, eos, ANUA, Native, Nizoral, and PanOxyl. Remaining brands use their complete name as a typographic fallback, never initials. Asset sources/provenance are in the Site source `assets/brand-logos/README.md`.
- The first remote favicon approach failed visual review; v22.1 onward uses self-contained logo assets. Current production is Sites version 26. Live browser QA on https://liambeautyindex.dpdns.org verified all 11 logo mappings, the Compare brands chart/table, and no blank views. The previous full QA verified exact Brand Share tooltip labels (brand/date/value), and the final deploy smoke-checked that Compare brands still renders.
- Site source commit `eac0147f661a9cc40da0f0131e90e2a4e2abcf4a`; saved v26 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_7f2c4cdc941081918dfc0e429365f885`; deployment `appgdep_6ae67476f0848191b03bf9d0061f1de0` succeeded. Rollback: v21 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_fadd5592c7788191816eb63df13cf865`.
- Google Sheet and fallback XLSX were untouched. Full version trail: `BEAUTY_INDEX_VERSIONS.md`.

## 2026-11-01 — Brand Directory and chart interaction repair, Site v21
- The Brands navigation now opens a distinct searchable/sortable Brand Directory. Its cards use brand monograms, not representative product photos; Brand detail opens a searchable monogram picker. Brand profile Overview/Products/Trend and Back navigation were live-verified.
- Hover behavior is scoped by chart size: sparklines at 200px or less draw only the trend line and do not open markers, tooltips, or product previews. Larger charts have visible modest markers and exact date/value tooltips.
- Browser QA on the canonical URL confirmed Brand tabs, medicube search/profile and return flows, no Overview content leaking into Brands, and no runtime errors. Trends brand share and product rank/price charts showed exact hover data; small trend sparklines remained static.
- Site source `4f5e3040fe6698aa0612e4f189238583055254e0`; saved v21 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_fadd5592c7788191816eb63df13cf865`; deployment `appgdep_6ae66d3d3a6c8191bb6bd48b7d9d21af` succeeded. Rollback: v20 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_85fa538ac5888191b996cdf26ec74d5d`.
- Google Sheet and fallback XLSX are unchanged. Release ledger: BEAUTY_INDEX_VERSIONS.md.

## 2026-11-01 — v19 blank-screen/layout and chart hotfix shipped as Site v20
- Root cause: v19 placed the date context as an extra flex child in the header and left page HTML cacheable for five minutes. The malformed header could push/overflow controls on narrower windows, while browser cache could keep displaying the prior response after deployment. Chart points were all shown continuously, which made dense sparklines look like thick dot bands.
- Fix: move the date context inside the market/date control block, use a responsive two-column selector grid, set the HTML response to `no-store`, hide chart dots until an individual point is hovered/focused/tapped, and size hit targets according to point density.
- Verified on the canonical URL with no query string: full Overview loaded, nav/date controls stayed in view, no page-level horizontal overflow, sparkline strokes remained clear, and only the active point highlighted with its date/rank tooltip. Browser found no blank state or runtime errors.
- Site source `3cb75994e3de4faed5b20b82f52b5afa84f83ca9`; saved Site version 20 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_85fa538ac5888191b996cdf26ec74d5d`; deployment `appgdep_6ae66abf161c8191a523d91ed2839cce` succeeded.
- Canonical address remains https://liambeautyindex.dpdns.org. Rollback to v19 if needed: `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ea09fb9fee70819184683c638ff5dabd`.
- Build/artifact checks passed. Google Sheet and fallback XLSX unchanged. Release ledger: BEAUTY_INDEX_VERSIONS.md.

## 2026-11-01 — Beauty Index v19 shipped
- Published v19 to https://liambeautyindex.dpdns.org. The header now explains KST latest-capture dates versus marketplace-local archive dates; changing markets preserves the selected date when possible.
- Added exact date/value/metric chart tooltips for hover, keyboard focus, and touch across large charts and sparklines; coverage labels distinguish dates without snapshots from captured dates where a product was outside Top 100 or had no price.
- Overview now surfaces cross-market gainers/drops. Product Finder builds and caches its archive index by selected date and displays current/last-captured and first-seen dates with market ranks.
- Live browser QA verified Overview, historical date and market switching, Trends, brand trends, medicube search and product detail/rank/price charts. No blank views, dead controls, clipping, or browser runtime errors reported; chart points displayed exact date and value tooltips.
- Build proof: `node --check worker/index.js`, `bash scripts/build.sh`, `node scripts/validate-artifact.mjs`, and `git diff --check` passed. This was a website-only change; Google Sheet and fallback XLSX schemas/data were not modified.
- Site source `aa2a9e3f2151ea611daa113cb723d873be9bf799`; saved v19 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_ea09fb9fee70819184683c638ff5dabd`; deployment `appgdep_6ae6687075fc81918de5021006d94a65` succeeded.
- Rollback: v18 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_fa0d7c1803dc8191ae7076ba454867ff`.
- Version and rollback ledger: BEAUTY_INDEX_VERSIONS.md.
## 2026-10-31 Beauty Index v16 — Product Finder image and UX repair
- Rebuilt Product Finder around archive search: title/brand/ASIN search, five-market filter, brand filter, full-archive vs selected-date Top 100 scope, four sort orders, reset, and 48-item pagination. Result cards show photo, brand/title/ASIN, market ranks, market breadth, and last capture date; responsive grid layout opens the existing direct product detail route.
- Image root cause: normalized `root_rank_history` rows intentionally omit image URLs, while photos are stored separately in the ASIN-keyed `products` metadata and latest market snapshots. Finder originally passed history rows directly to the image renderer. v15 joined the product metadata and added a canonical ASIN image fallback; live QA found one ASIN with neither metadata photo nor fallback success. v16 also joins photo/brand from selected-date market snapshots by ASIN before rendering.
- Live browser verification: ASIN B09V7Z4TJG now shows its actual medicube photo; CeraVe search showed real photos on the first 8 cards. Confirmed archive/current Top 100 scopes, market and brand filters, sorting, reset, paging, and product-detail click-through. No clipping or runtime errors reported.
- v16 Site version `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_7ec3d937aa6081918661991aefd9e290`; deployment `appgdep_6ae5ffc6d6248191b69dc4e75c19375b` succeeded; source `0365675578ddc28e73b5c8796324ffdc129808b2`.
- v15 remains saved; v14 remains the prior feature-complete rollback. No macro-facing Google Sheet, public feed schema, or fallback XLSX structure was changed.

## 2026-10-31 Beauty Index v14 shipped and verified
- Published v14 to https://liambeautyindex.dpdns.org. Date changes now drive the Daily Market Pulse, overview metrics, and brand footprint; the pulse shows `AS OF` and distinguishes unchanged rankings from missing snapshots.
- Brands now contains Brand directory and Brand detail subtabs; brand profiles retain their own Overview/Products/Trend tabs. Added Products archive search across title, brand, and ASIN, leading to direct product pages. Chart points show captured date and rank/value on hover.
- Live browser QA passed: historical date Oct 15; all five market cards; unchanged Oct 31 comparison; Brands subtabs and profile tabs; Products search/detail tabs; rank chart hover.
- Site v14 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_79792b3c682c8191b6b9bfe58a679dd0`; deployment `appgdep_6ae5f9525b808191837eb4b160489a97`; source `66a2a459e50a1d7e24ed5f703da378f8ea318be0`.
- Rollback: v13 available; v12 remains previous known-good. Macro-facing Google Sheet and fallback XLSX were untouched.
- Follow-up candidates: synchronized date context across views, richer item entry/exit and capture-gap labels, and catalog market/rank/first-seen filters.


## 2026-10-30 scheduler duplication repair
- Removed the stale LIAM3 `PRIMARY` cron block after backing up the full crontab with mode 0600; all unrelated cron tasks were preserved.
- The sole LIAM3 primary is now the enabled 05:00 KST systemd timer. Its hourly catch-up and watchdog timers remain active. The crontab has no Amazon Beauty entries; user lingering is enabled and Windows WSL keepalive tasks are present.
- Fixed `scripts/install_schedule.sh`: it now recognizes legacy, PRIMARY, and SECONDARY block markers when replacing/removing schedules, and status no longer exits when GWS is absent. Deployed the updated script to LIAM3.
- Verified the installer status lists three active timers and no cron block; cleared the previous duplicate-run failure state. `bash -n` and `git diff --check` passed.
- LIAM2 remains the 05:30 secondary takeover, configured for Service Account Sheets access. Its latest catch-up log reports the regional tabs current; older OAuth `invalid_grant` messages are retained in the cumulative log and do not establish a current failure.
- The only remaining proof is tomorrow's unattended LIAM3 systemd-only run. No existing Google Sheet or fallback workbook structure/data was changed.

## 2026-10-29 Beauty Index dashboard
- Implemented a read-only web dashboard with regional Top 100 tables, daily snapshot history, movers/new/dropped comparisons, five-market freshness, and ASIN rank/price/rating charts.
- Current rankings and complete `root_rank_history` data come from Google Sheets through the existing Service Account's read-only scope, cached for 10 minutes. SQLite fills brand labels and provides a fallback. Start locally with `python3 scripts/serve_dashboard.py --port 8781`.
- Deployed the dashboard to LIAM3 as an enabled user systemd service. Live API returned 100 current rows for each of US/DE/UK/FR/ES dated 2026-10-29; `root_rank_history` loaded from Google Sheets with 64 dates and 1,282 ASINs, no warning. Local URL on LIAM3: `http://127.0.0.1:8781`.
- Private Tailnet publishing is the only pending piece. Tailscale reports Serve is disabled for the tailnet and supplied the owner enablement URL; after it is enabled, `tailscale serve --bg 8781` can provide the private HTTPS endpoint. Public Funnel was not enabled.
- Refinement is deployed to LIAM3: clearer typography/spacing, brand-aware product search, exact brand filtering, and a brand directory with Top 100 counts, avg/best rank, ratings and reviews. Added “Powered by GunWoo · For NohMin”. Live check returned 47 US brands and five CeraVe products with complete current fields.
- Image feasibility only (no fallback or existing Sheet layout was changed): saved SQLite image URLs cover 487/500 current regional slots (US 96, UK 97, DE/FR/ES 98 each). Of 13 gaps, the conventional Amazon ASIN image URL resolves to JPEG for 7 and a 43-byte placeholder GIF for 6. A separate ASIN-to-image mapping workbook is feasible and would keep macro-facing tabs intact.

## 2026-10-29 Recovery update
- Additional Drive hardening: bounded retries for transient GWS errors; never blindly retry non-idempotent file creation; verify remote ID, MIME type, size, MD5, target folder, and non-trashed status after upload; recheck the existing Drive file during hourly catch-up and repair missing/mismatched delivery. Local XLSX/mail fallback remains independent. Tests: 61 passed. Deployed to LIAM2/LIAM3 and passed `py_compile` on both.
- LIAM3 live Drive update at 15:42 KST succeeded in place on existing file ID `1P1V92U9cCkeMXZfKekSLbhB3rIlZVu3R`; remote readback matched local size/checksum and expected folder. The subsequent LIAM3 catch-up systemd audit exited 0.
- Fixed and deployed stale aggregate-tab recovery to LIAM2/LIAM3. Catch-up detects stale shared views and rebuilds them from SQLite through `--shared-views-only`, without Amazon recrawl or history append. It rechecks stamps after publishing and alerts/retries if any remain stale. Tests: 58 passed.
- LIAM3 live shared-only publish passed at 15:24 KST. All five shared tabs updated; all 15 monitored tabs fresh; regional tabs stayed unchanged; root history remained 33,631 rows with latest cohorts 100 each, 0 duplicate keys, 0 internal blanks. LIAM3 catch-up service exited 0 after the refresh.
- Final verification: UK-only recovery published 100 rows and appended 100 history rows; title recovery filled one Top100 title and 65 latest-history titles. All five current tabs audit at 100/100 titles.
- Sheets write-quota recovery is deployed: gws batches stay below 90KB, quota responses retry after 65 seconds, and each tab stamp is written only after all its data chunks complete. Partial run reports scope to the markets in the run. Full suite: 53 passed.
- Aggregate refresh completed at 14:44. At 14:45 the live audit showed all 15 workbook tabs fresh, 33,631 history rows, five latest cohorts at 100 unique keys, 0 duplicates, and 0 internal blank rows. The corrected read-only audit generated four report emails accepted for both recipients, with fallback XLSX attached to the final email; Telegram send was invoked.
- LIAM3 next primary: 10/30 05:00 KST; hourly catch-up :55 and watchdog :00 are enabled.
- The 14:55 timer had exited in `flock` before Python started. Moved the lock to Linux-native WSL storage and added a wrapper that logs overlap skips as success but preserves actual task failures. Deployed to LIAM3 systemd and LIAM2's 05:30 takeover cron. The LIAM3 systemd catch-up service then ran at 14:57 and completed a no-op verification with exit 0.

## 2026-10-28 Closeout
- Pipeline completion: the 05:00 primary collected/published 500/500; `root_rank_history` appended 245 rows (US 100, DE 38, UK 29, FR 34, ES 44); the live title audit confirmed 100/100 in all five regions; fallback XLSX was created and uploaded to Drive. The first run was flagged because whole-history title repair hit Sheets write quota after 354 of 389 repairs. That noncritical historical repair is now excluded from the daily write-quota path; daily rank append remains enabled.
- Reused today's existing artifacts with `run_daily_pipeline.py --report-existing` (no recrawl and no duplicate Drive upload). The live title audit passed, and the three phase emails plus final report were each accepted by SMTP for the two configured recipients; the final report includes the existing fallback XLSX.
- Fixed final status logic so Drive upload failure cannot be labeled COMPLETED; added history append counts and tested report-only recovery. Full repository suite: `23 passed`; LIAM2 and LIAM3 deployed scripts compile. Their live Sheet watchdogs and SA catch-up no-op checks passed.
- The 05:30 LIAM2 `invalid_grant` log predates the Service Account switch. Re-running the installed catch-up path with the current SA configuration returned “all regional tabs already have today's stamp.” LIAM1 is the current WSL host; it is not the production scheduler, and its local cron remains stopped.
- Mail recheck: this shell is LIAM1's Ubuntu WSL (`DESKTOP-RO042LL`). SMTP authentication passed and the actual Amazon `run_job._send_email` function delivered a clearly labeled verification email to both repository-configured recipients. SMTP auth and delivery also passed from LIAM2 and LIAM3; all three deployed sender files passed syntax compilation, and the repository suite passed (`19 passed`).
- LIAM1 WSL cron is stopped and its `crontab -l` is permission-denied. This is not the production scheduler: LIAM3's primary 05:00 + catch-up + hourly watchdog crontab and LIAM2's 05:30 takeover crontab are installed. LIAM1 SSH still times out. Scheduled production mail on an actual crawler run was not triggered by this transport test.
- Drive contains exactly one fallback workbook for each date 2026-10-23 through 2026-10-28. Files for 10/24–27 were recovered to Drive; the 10/28 workbook is [here](https://drive.google.com/file/d/1ucaU3XON8ZVl6dRiarfc4jHD8TznxMVv/view).
- The 10/28 live Sheet refresh published all five regions. The first title pass hit Sheets write quota; its retry finished at 100/100 for US, DE, UK, FR, ES.
- Historical title repair filled 354 rows from existing mappings, then fetched and filled the remaining 35 title cells across 21 region-ASIN groups. A read-only recheck found no blank history titles. History row keys were preserved.
- LIAM3 primary cron (05:00 + hourly recovery/watchdog) and LIAM2 secondary cron (05:30 takeover) now use their local Service Account key with mode 600. Both nodes passed Sheets watchdog checks using that identity; LIAM2 also safely ran catch-up and title-history no-op checks.
- LIAM3 local SQLite comparison found zero expected history keys missing from the Sheet for 10/23–27. 104 existing sheet-only keys were left intact. Drive inventory found one fallback XLSX for each date 10/23–28.
- The 10/24–27 scheduled publication failures were caused by expired/revoked user OAuth. 10/28’s 05:00 run predates the Service Account switch; 10/29 05:00 is the first full scheduled run under the new primary configuration.
- Historical note (superseded 2026-10-28): Gmail OAuth previously blocked mail. Operational mail now uses the shared SMTP profile; Google OAuth/Service Account remains separate for Drive/Sheets.
- Code paths updated: `scripts/enrich_titles_until_complete.py` now uses Service Account Sheets reads/writes with transient/quota retry; `scripts/backfill_history_titles_from_marketplaces.py` performs polite, title-cell-only recovery and stops on block signals; `scripts/run_job.py` resolves notification config paths per node home.

## Current State
- Date checked: 2026-10-16 KST.
- Local repo is now fast-forwarded to latest `origin/main`:
  - before: `9850d18`, 48 commits behind
  - after: `d98edaf`
- Primary live Sheet is `beauty_personal_care_top100_live`:
  - spreadsheet id: `1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80`
  - URL: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit

## 2026-10-16 Proof
- Historical note (superseded 2026-10-28): Gmail API was previously used for mail alerts. Operational mail now uses the shared SMTP transport.
- The corrected automatic completion code was run once as an end-to-end validation. Live Sheet result: all five Top 100 tabs have all 99 data rows titled (`99/99`).
- Verified live stamps: US `09:12`, DE `09:23`, UK `09:38`, FR `09:49`, ES `10:00 KST`.
- The same hourly watchdog that cron runs returned `ok=true` at `10:03 KST`, with no stale regions and `root_rank_history` newest date `2026-10-16`.
- Installed cron behavior is now: a single `05:00` pipeline runs five-region root upload, exact-blank title completion, then a local-data XLSX fallback with email+Telegram reporting; hourly `:17` watchdog sends email+Telegram alerts for stale data or OAuth/Sheet verification failure.
- Final audit fixed an off-by-one verifier range and confirms all six Top tabs (five regions plus `[ALL]`) at `100/100` titled. `[ALL] Top 100`, previously stale since 2026-08-31, is now regenerated from current regional snapshots.
- After root upload and title completion, `export_fallback_workbook.py --email` builds an equivalent recovery XLSX directly from local SQLite rather than exporting Google Sheets, uploads it to Drive, and emails the attachment. This remains usable if Sheets read/write is unavailable; its live Drive upload and attachment email both succeeded on 2026-10-16 (Drive file id `1MOde3GPApRCUDcGphsIik-hFj3Bgn_AG`).

## What Was Fixed
- Added `AMZ_BS_ROOT_BACKEND=gws` support to `src/crawl_amazon_beauty_bestsellers/root_publish.py`.
- This lets the latest Sheet 3 publisher use the canonical workspace Google Workspace CLI OAuth config:
  - `/home/liam/agent-coding/agent-system/A3-runtime-standards/local-config/gws`
- This avoids the broken/missing `~/.config/gsheet-sync/refresh_token.json` path that blocked latest `publish-root`.
- Installed an active cron fallback because user systemd timers are unavailable in this environment:
- daily `05:00 KST`: `scripts/run_daily_pipeline.py`
  - hourly `:17`: `scripts/watchdog_sheet.py --max-age-hours 30 --alert`
- Cron now carries the required `gws` PATH/config envs.
- Added stale-sheet watchdog checks for `[US/DE/UK/FR/ES] Top 100` and `root_rank_history`.
- Historical note (superseded 2026-10-28): this version used Gmail API via `gws` with SMTP fallback. The current operational path uses shared SMTP only.
- Telegram now accepts `TG_*`, `TELEGRAM_*`, and common `BOT_TOKEN`/`CHAT_ID` env names, and falls back to the gitignored WH env files used by `build_ops_powerhouse` / `capture_finance_pdf_news`.
- `scripts/run_job.py` now times out long subprocesses and releases locks even on fatal interruption.
- `--no-detail` now means root-cycle only; daily cron no longer runs `fill-titles` or `fill-gaps`.
- Added `scripts/enrich_titles_until_complete.py` for bounded title completion after the fast Sheet publish.

## 2026-10-13 Manual Run / Sheet Proof
The full manual job started and root publishing completed before `fill-gaps` hung; then a cron-equivalent `--no-detail` run was executed. Direct watchdog verification via `gws` showed:

| Region | Crawl | Publish | Verified Sheet Stamp |
|---|---:|---:|---|
| US | 100 | 100 | `2026-10-13 06:54 KST` |
| DE | 100 | 100 | `2026-10-13 06:39 KST` |
| UK | 100 | 100 | `2026-10-13 06:43 KST` |
| FR | 100 | 100 | `2026-10-13 06:34 KST` |
| ES | 100 | 100 | `2026-10-13 06:34 KST` |

`root_rank_history` is present with `10921` rows and newest date `2026-10-12`. History dates are marketplace/day aggregation, not the KST wall-clock run timestamp.

## 2026-10-13 Schedule Test / Google Upload Proof
After removing `fill-titles` from the daily `--no-detail` lane, the exact scheduled runner completed successfully:

- command: `scripts/run_job.py --no-detail`
- started: `2026-10-13 09:36 KST`
- completed: `2026-10-13 09:38 KST`
- result: `rc=0`
- log: `.agent/logs/run_job_20261013_093629_af7737.log`

The run published 100 rows for every region to the primary Google Sheet. Final watchdog verification:

| Region | Verified Sheet Stamp |
|---|---|
| US | `2026-10-13 09:36 KST` |
| DE | `2026-10-13 09:37 KST` |
| UK | `2026-10-13 09:37 KST` |
| FR | `2026-10-13 09:37 KST` |
| ES | `2026-10-13 09:37 KST` |

`root_rank_history` now has `11352` rows and newest date `2026-10-13`.

Telegram alerting was corrected to reuse the WH gitignored env files and verify Telegram API responses. A Telegram smoke message returned success on 2026-10-13 KST. The earlier 06:54 run did not send Telegram because this repo had no local `.env` and the old code only checked `TG_BOT_TOKEN/TG_CHAT_ID`.

## 2026-10-13 Title Completion Proof
The root bestseller page gives 100 ASIN/rank rows, but the rendered DOM only carries about 60 titles. The embedded recs list has no title metadata, so the correct recovery path is bounded `/dp/ASIN` title enrichment plus fallback marketplace lookup.

Live Sheet title completion was raised to 100%:

| Region | Final Title Completion |
|---|---:|
| US | `100/100` |
| DE | `100/100` |
| UK | `100/100` |
| FR | `100/100` |
| ES | `100/100` |

The last stalled ES ASIN `B08B981F4X` was filled from DE/UK marketplace fallback title lookup.

`root_rank_history` title backfill was implemented in the same enrichment script. It now fills blank history-title cells after title enrichment, without appending duplicate history rows.

Historical title-gap audit:

- before backfill: `1972/11352` `root_rank_history` rows had blank titles (`17.37%`)
- after current Top100 + DB/product-details backfill: `693/11352` rows still blank (`6.10%`)
- 2026-10-13 rows: `400/400` titled

The remaining `693` blanks are older ASIN rows not recoverable from current Top100 tabs or local DB title history without doing additional live marketplace lookups.

Active cron now includes:

```cron
20 5 * * * cd /home/liam/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers && /usr/bin/python3 scripts/enrich_titles_until_complete.py --regions us de uk fr es --batch-size 10 --max-rounds 0 --timeout-sec 420 --sleep-sec 15 --alert >> .agent/logs/cron_title_enrichment.log 2>&1
```

## Why Today 05:00 Did Not Run
1. At failure time, active crontab did not contain this repo's scheduled job.
2. User systemd scheduling was not available here: `systemctl --user` failed with `Failed to connect to bus: No such file or directory`.
3. `.agent/logs/` had no 2026-10-13 05:00 run log for this repo.
4. Even if old cron had existed, cron needed an explicit Node/gws PATH; `gws` lives under `/home/liam/.nvm/versions/node/v20.20.1/bin/gws`, which is now included.
5. Full enrichment can block the core sheet update; therefore the daily auto lane now runs `--no-detail`, and detail enrichment should be separated/throttled.

## Remaining Runtime Issues Seen Today
- `scripts/run_job.py --no-detail` returned nonzero after the sheet core update because:
  - `DE/UK/FR` hit transient DNS resolution failures;
  - `ES` hit a captcha/block signal;
  - `fill-titles --region us` timed out after 240s.
- Historical note (superseded 2026-10-28): Gmail API alert delivery was used here. Current operational mail uses shared SMTP only.

## Earlier Failure Causes
1. The local checkout was stale and 48 commits behind `origin/main`. The latest code was already pushed; I should have fetched/pulled first.
2. The active crontab no longer contains this repo's old local lane. Backup exists at `.agent/crontab_backup_20260826.txt`, but it is not active.
3. The interim scheduler was not durable. `.agent/logs/scheduler_loop.log` stops at 2026-08-25 23:18 KST.
4. Old cron-era Sheets publish failed because `gws` was not available/configured in that cron environment.
5. Latest Sheet 3 code used token backend by default and expected `~/.config/gsheet-sync/client_secret.json` plus `refresh_token.json`; this machine's working Google auth is actually the workspace-local `gws` config.
6. Service-account upload path can reach Google, but Drive upload failed on My Drive quota. Owner OAuth via `gws` is the working path.
7. Sandbox network blocks live Amazon crawling; escalated network execution is required here.
8. Amazon captcha/block signals still occur when pressure rises. The repo policy correctly stops/cools down rather than retry-storming.
9. Full `scripts/run_job.py` spent a long time in `fill-titles`; urgent recovery used `root-cycle` per region to update core Top100 tabs first.

## liam1-3 / Repo Location Notes
- Local WSL repo: `/home/liam/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- `liam2` and `liam3` SSH aliases reached their machines during the check.
- `liam1` SSH failed from this environment with `socket: Operation not permitted`.
- The latest pushed source of truth is currently `origin/main`; no evidence yet that `liam3` had newer unpushed code for this repo.
- SSH/Tailscale stabilization remains pending.

## Active Schedule Now
```cron
0 5 * * * cd /home/liam/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers && /usr/bin/flock -n .agent/locks/daily_pipeline.lock /usr/bin/python3 scripts/run_daily_pipeline.py >> .agent/logs/cron_daily_pipeline.log 2>&1
17 * * * * cd /home/liam/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers && /usr/bin/python3 scripts/watchdog_sheet.py --max-age-hours 30 --alert >> .agent/logs/cron_watchdog.log 2>&1
```
# 2026-10-28 — Shared A4 mail transport repair

## 2026-10-29 — Active root-run recovery repair

- Confirmed today's original 05:00 production pass had all five regions. A second run fired at 13:39 because the newly enabled 05:00 systemd timer used `Persistent=true`; this was an install-time missed-run catch-up.
- That extra run succeeded for US/DE/FR/ES and was blocked by Amazon on UK (`0/0`, `fail=1`). The old summary incorrectly said `completed` because `run_job.py` did not propagate its rc=4 region failure to the process exit code and the parent checked only the summary status.
- Code now requires 100+ crawled and published rows and zero failures per selected region, propagates rc=4 as failure, and has catch-up retry only failed/stale regions after the 55-minute block cooldown. Daily timer persistence is disabled to prevent another install-time recrawl.
- Validation: `PYTHONPATH=src pytest -q` -> 37 passed; Python compilation, `bash -n`, and `git diff --check` passed. Full `systemd-analyze verify` is pending on LIAM3 because this LIAM1 checkout has no `.venv/bin/python` at the unit's configured path.
- Deployed the current recovery code to LIAM3 and LIAM2. LIAM3's 13:52 manual check correctly deferred the blocked UK retry; LIAM2's 13:53 check confirmed all five tabs/titles current and did not recrawl. Partial-region success now refreshes shared aggregate tabs from local SQLite without crawling ES. Cross-node newer Sheet stamps suppress retries for failures already repaired elsewhere.
- Committed and pushed as `82d4012`. Remaining proof: UK retry after 14:35 KST cooldown, live Sheet/history verification, and corrected SMTP/Telegram report. LIAM2's Drive OAuth, abnormal Git worktree, and LIAM1/LIAM4 fleet checks are not yet complete.
- At 14:04 the live audit confirmed 33,531 history data rows, zero duplicate keys, and no local-DB keys missing from the Sheet (28,669 rows locally expected; 4,862 existing Sheet-only rows preserved). The 251-row difference is unused trailing sheet capacity, not internal holes. Ten older date/region cohorts have fewer than 100 distinct ASINs; those are source-history gaps, not upload failures, and need other historical data before any safe repair.
- The 10 old partial cohorts sum to 402 absent slots to 100: eight cohorts were collected as 50 rows and two FR cohorts as 99. LIAM3's archived `list.jsonl` snapshots confirm those partial source runs, so no existing full 100-row source exists to restore their exact historical ranks. The daily data validator will now flag and retry any new Top100 tab with a missing/duplicate rank or ASIN.
- Daily title recovery now repairs history title cells only for each region's latest history date after all five live Top100 titles are complete. Existing history keys and older dates are untouched; the expensive full-history scan remains out of the daily path.

- Removed Gmail OAuth/Gmail API from the Amazon operational email sender. SMTP failure is reported directly; the sender does not switch transports after an ambiguous delivery.
- If Amazon mail has no recipient or SMTP delivery fails, `run_job.py` now sends a failure alert through Telegram when configured.
- Added a shared loader at `A3-runtime-standards/ops-scripts/shared_mailer.py`; repository recipients and explicit SMTP overrides remain local.
- Moved SMTP credentials from the workspace path to `~/.config/a4-mailer/smtp.env` with directory mode `0700` and file mode `0600`. LIAM3's workspace path was Windows-mounted and appeared `0777` inside WSL; the old copies were removed after private-profile authentication passed.
- SMTP auth check passed on local Liam, LIAM2, and LIAM3. No additional email was sent during this final verification; the earlier Amazon smoke email had been accepted by SMTP.
- LIAM3 installed A4 sender code was updated with backups under `/tmp/a4-mail-rollout-backup`. LIAM2 received the updated Amazon sender and common module.
- LIAM1 SSH remains unavailable; LIAM4 SSH is also unavailable. Neither node is verified.
- No commit or push was made.
- Watchdog hardening: it now audits update stamps across all 15 Top100/history/analytics tabs, instead of only the five Top100 tabs. Missing or stale tabs trigger the existing email/Telegram alert path. Verification: `PYTHONPATH=src pytest -q` -> 46 passed; py_compile and `git diff --check` also passed.

## 2026-10-31 — Public Beauty Index shipped

- Public dashboard: https://liambeautyindex.dpdns.org
- Replaced the blocked Worker upload endpoint with a dedicated public Google Drive JSON mirror. The dashboard reads this feed and refreshes every five minutes.
- The JSON is separate from the macro workbook and fallback XLSX. Owner OAuth created it under the upgraded user's Drive quota; LIAM3's existing service account can update only this file. The publisher refuses to create a replacement if its saved ID is lost.
- LIAM3 daily 05:00 pipeline publishes after the local fallback XLSX is generated; hourly catch-up compares the five Sheet timestamps and skips unchanged snapshots.
- Verified production feed: 2026-10-31, five marketplaces each 100/100, 34,376 historical rows, 1,311 ASIN metadata records. LIAM3's second `--if-stale` run returned `current`.
- Site version 2 deployed successfully. Build/artifact validation and Worker syntax check passed. Main A4 repo changes are uncommitted; no main-repo push was made.

## 2026-10-31 Beauty Index controls repair
- Root cause: the served inline browser script had invalid JavaScript syntax. The image `onerror` fallback string was nested inside the Worker HTML template literal; escaping was consumed, so browsers failed parsing the entire script before `/api/data` or any handlers ran.
- Replaced the inline image error attribute with a bound DOM error handler; removed `For NohMin` from the public page.
- Site source pushed as `1542ecdcdad52a0077757983b28275d576f08449`; version 4 deployment succeeded.
- Live custom-domain HTML has valid JavaScript syntax and no NohMin text. Live `/api/data` returns 2026-10-31 with 100 rows for each of five markets, 34,376 history rows, and 1,311 products. Existing public URL: https://liambeautyindex.dpdns.org
- Main A4 repository changes remain uncommitted; Site code is maintained in its separate Sites source repository.

## 2026-10-31 Beauty Index interaction and image repair
- Root cause for missing images: CSP allowed only `m.media-amazon.com`, while 1,073 of 1,232 available image URLs used `images-eu.ssl-images-amazon.com` or `images-na.ssl-images-amazon.com`. Added both exact hosts; browser QA observed 95+ of 100 current US images loaded, with 3 visible records using the no-image fallback.
- Reworked event handling with delegated listeners so re-rendered nav, market, date, filter, brand, and product controls remain active. Search, date selector (64+ historical days), all five market selectors, Rankings, Movements filters, Brands search, and brand-to-rankings navigation passed live browser checks.
- Product title/image links are locale-specific Amazon links; clicking elsewhere on a product row opens that marketplace in a new tab. Added a dedicated History button per row; product rank-history dialog opens and closes with dated rows.
- `FOR NOHMIN` is hidden on Overview and shown under the descriptions on Rankings, Movements, and Brands; all four visibility states passed live browser checks.
- Final Site source commit `69b4a20d7b0136ed299741de2f72c0ca111aadbf`; version 7 deployment succeeded at https://liambeautyindex.dpdns.org. Worker syntax, build, artifact validation, live API, and browser interactions verified.
- Final follow-up found and fixed a Brands runtime exception: the brand-card builder discarded aggregate fields (`avg`, `count`, `best`) before rendering, so `avg.toFixed()` threw and the tab remained on its previous view. It now filters the intact brand aggregates; redundant per-render handlers were removed in favor of the delegated handler.
- Version 8 source commit `9375071df1953af2b474df097abb673be85f6325` deployed successfully. Live browser confirmed 48 brand cards, `eos` search → 1 brand card (3 products, average rank #34.7), and selecting it opens Rankings prefiltered to 3 eos rows. The complete local interaction harness also passes Rankings/search, Movements filters, Brands/search/navigation, market-specific links, product navigation, History modal, snapshot options, and credit visibility.
- Public snapshot file: https://drive.google.com/file/d/1pAVxxxbr8x2S3eKVoPspCBnElwv69FtB/view

## 2026-10-31 — Beauty Index v9 trends and brand intelligence
- v9 is live at https://liambeautyindex.dpdns.org (Sites deployment `appgdep_6ae5e975c6b48191b80b3c66b2f410e4`); source commit `9a9a5c206b856c73e1b8411a06e95117b359ff37`.
- Expanded Brands with each brand's leading product image (click opens Amazon), Top 100 share, average/best rank, average rating, 30-day brand rank path/direction, search, and sorting by shelf share, average rank, best position, or 30-day momentum. “View brand products” opens Rankings filtered to that brand.
- Version 8 remains independently saved and deployable as rollback. Existing Sheet tabs and fallback XLSX schemas were not changed.
- Worker syntax, build, artifact validation, and local UI harness passed. The harness checked all 322 market/date selections: rankings have 100 ordered slots; duplicate rows are resolved for display and real archive gaps remain explicit.
- Live browser QA confirmed brand images, all four sorting modes, search, brand-filtered navigation, and date switching; the selected historical date rendered ranks 1–100 in order. Local all-date interaction validation also passed.
- Data-only updates continue through the existing LIAM3 publisher to the same public JSON Drive mirror. The page polls every five minutes. Since v9 retains feed schema v1, morning data updates need no site redeploy; a feed schema change would require coordinated publisher/UI updates.
- A4 repository changes, operational docs, and the date-stamped XLSX exports intended by the GitHub Actions commit-back workflow were committed as `82a9dfb` and pushed to `origin/main`. Local crontab backups and detailed per-run JSONL files remain excluded.

## 2026-10-31 — Beauty Index v10 chart clarity
- Fixed the Overview Top 10 chart's missing CSS class; its line now renders light green on the dark green panel. Added an in-page note that the y-scale fits the observed range and lower-number ranks plot higher.
- Clarified that Overview follows today's Top 10 cohort backward and averages only products found in each archived snapshot; the point sample may be fewer than ten.
- Brands now explains its sort definitions: shelf share = count out of 100; average rank = mean position, lower is better; best position = the brand's highest-ranked product; 30-day momentum = change in brand mean rank, with upward movement meaning stronger placement.
- Brand momentum now rounds to at most one decimal. Brand sparklines represent the brand's mean product rank across archived dates, not one product's rank.
- Site version 10 deployed successfully at https://liambeautyindex.dpdns.org (source `75a296d7a685d14b61aef26df3b5166c2a014aa9`, deployment `appgdep_6ae5ed9e1d088191bc04e94913e2c38c`). Live browser check confirmed the green line, definitions, and rounded values. Local UI harness passed, including all 322 market/date rank-slot checks.
# Beauty Index v11 — 2026-10-31

**Status: deployed successfully.** Public site: https://liambeautyindex.dpdns.org

- A product image/title/rank row now opens a product-specific internal page with a stable `#product/<ASIN>/<tab>` URL. Each product page has Overview, Rank & price, and Markets tabs, with rank/price observations, a 90-day rank chart, five-market rank/price/rating/coverage comparison, product photo, and Amazon link.
- Overview now shows the database's five-market brand footprint (Top 100 share and average rank per market) and separate 30-day paths for today's Top 10 products. Trends includes Top 5 brand share history. Missing dates/items are shown as chart gaps.
- Build, JS syntax, and deployment artifact validation passed. Sites reports production deployment `succeeded`. Browser click-through QA was unavailable here, so interaction behavior is source- and build-verified, not live-browser-verified.
- Current deployed Site version: **v11**, ID `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_83b58445fb148191aa7049a902d6aeb3`; source commit `9a304db634820d7f929e2c845e47423465d0f8b0`.
- Rollback remains available: **v10** `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_632612bb2390819182be40d0d3a6244b`; earlier baseline **v8** `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_b335a1c259f48191bcd85884ad10314a`.

The underlying data endpoint and Google Sheet/fallback workbook schema were not changed by this site-only release. The production site continues to load the published ranking JSON and refresh it on its existing cadence.

---

## 2026-10-31 — v11 blank-screen hotfix (v12)

v11 failed because I checked the Worker source syntax but not the JavaScript embedded in the generated page. The route regex used escaped slash characters inside the Worker's outer HTML template literal; those escapes disappeared in the browser output, making the client script syntactically invalid. The browser never ran `refresh()` or registered click handlers. The Worker and public data endpoint were healthy.

Fixed the route parser, added generated inline-script parsing to the artifact validator, and deployed **v12**. The live browser check confirmed the archive loaded (500 current rank positions, 34,376 history rows), navigation worked, a product opened, and all three detail tabs switched with populated content.

- v12: `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_c997ad637d9081918267286791e664c0`
- Deployment: `appgdep_6ae5f47c467c81918167ff57e045d7cc` (succeeded)
- Source commit: `08aca5593890f936998f129a7198e744574d50bf`
- Last known good rollback: v10 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_632612bb2390819182be40d0d3a6244b`. v11 is preserved but defective.

## 2026-10-31 — Overview and Brand Detail redesign (v13)

- Overview now opens with a polished intro and four useful KPIs, then a five-market pulse with each market's largest gainer, biggest drop, and new-entry count. Top 10 product paths follow; brand share/footprint is lower on the page.
- Added a separate **Brand Detail** navigation tab and searchable brand picker. Each brand opens a shareable direct route such as `https://liambeautyindex.dpdns.org/#brand/CeraVe/overview` with Overview, Products, and Trend tabs. Profiles show five-market share/average/best rank, the selected-market product roster, and brand share/rank trends. Product links open product detail and return to the brand profile.
- Production browser verification passed for Overview layout, all brand tabs, CeraVe product links and back navigation. Direct URL reload rendered the profile and five-market table without visiting the directory first.
- Site v13 `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_73f4afd3d6a48191b78b9870adc50dee`; deployment `appgdep_6ae5f6d568a0819193023109cf25f099` succeeded; source commit `1334c7bcf6f9cf3aeccff09119b64fa4aec8a909`.
- v12 rollback remains available at `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_c997ad637d9081918267286791e664c0`. Google Sheet and fallback XLSX schemas were left unchanged.
