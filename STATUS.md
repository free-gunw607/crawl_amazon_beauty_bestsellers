# STATUS

## 2026-10-29 incomplete-run detection and recovery repair
- The 05:00 KST production run completed the five regional Top 100 publishes. Installing the daily systemd timer after its scheduled time also triggered a second `Persistent=true` catch-up at 13:39. That extra run published US/DE/FR/ES, while UK was blocked (`crawled=0`, `published=0`, `fail=1`). Its summary nevertheless said `status=completed`: `run_job.py` recorded rc=4 as a region failure but did not set the overall exit code, and the enclosing pipeline trusted only the summary status.
- The extra run refreshed today's other four regions. It did not erase historical rows; root history is append-only. UK retained the earlier 05:00 publication. The 14:37 UK-only recovery completed the missing market; the corrected final report was sent after final verification.
- Recovery controls are active: root completion requires every selected region to have at least 100 rows crawled and published with zero failures; rc=4 is an overall failure. Catch-up retries only stale/failed regions and observes the 55-minute marketplace block cooldown. The daily timer is nonpersistent; hourly catch-up handles missed work.
- The recurring title completion still runs bounded polite rounds per invocation and leaves unresolved ASINs for the hourly catch-up loop. It stops on Amazon block signals and resumes after cooldown rather than retrying aggressively.
- Verification: 53 tests pass; changed Python and shell files compile. The LIAM3 catch-up systemd service completed a no-op successfully at 14:57.
- Deployed the corrected runner, catch-up, title recovery, Drive uploader, fallback exporter, watchdog, and timer files to LIAM3. The next daily run is 10/30 05:00 KST; catch-up is hourly at :55.
- Deployed the shared catch-up/pipeline/root-completion code to LIAM2's Ubuntu-24.04 repo as well. Its 13:53 live check saw all five regional tabs current and titles complete and exited without a duplicate crawl. LIAM2's GWS user OAuth for Drive is still a separate known issue; its Service Account Sheet read path passed.
- Partial-region recovery also refreshes shared `[ALL]`, trend, catalog, rank-change, and price-history views from saved SQLite via `publish-root --region es`; this does not crawl ES. Failed-region state is ignored when a newer cross-node Sheet stamp proves another node already repaired it.
- Committed and pushed as `82d4012` (`fix: recover incomplete Amazon daily sheet runs`); origin/main was fetched first and was not ahead. The 13:55 scheduled LIAM3 catch-up completed successfully and deferred UK due to the 55-minute block cooldown. LIAM2/LIAM3 runtime files now contain the pushed implementation; LIAM2's existing Git index/worktree is abnormal (hundreds of staged deletions plus local files), so no pull/reset/restore was attempted there to avoid deleting runtime state.
- Remaining: observe the next unattended 05:00 run. LIAM1/LIAM4 fleet checks and LIAM2 Git-worktree reconciliation remain separate; LIAM2's 05:30 catch-up cron now uses the shared Linux lock wrapper.
- History audit refinement: watchdog now computes the maximum date rather than assuming the last physical row is newest, reports per-region latest-date row/unique-key counts, duplicate keys, internal blank rows, and trailing grid capacity separately. The apparent 251 blank rows are trailing capacity after the last populated row, not 251 holes inside the history data. LIAM3's local-DB comparison found 28,669 expected history rows, zero expected local keys missing from the Sheet, and 4,862 sheet-only keys; all sheet-only/history rows remain preserved. The live Sheet has 33,531 history data rows and zero duplicate keys. Ten older date-region cohorts have fewer than 100 unique ASINs and require source-data investigation; no safe local backfill exists for them yet.
- The 10 historical partial cohorts total 402 missing slots to 100 (eight cohorts had 50 ASINs; two FR cohorts had 99). LIAM3's archived `list.jsonl` snapshots confirm the 50-row collection results for the affected dates/markets; the Sheet uploaded everything present in SQLite, so this is a source-collection gap, not a Drive/Sheets upload omission. Those exact historical ranks cannot be reconstructed from these snapshots or current Amazon pages without inventing data. The new daily gate prevents this from recurring silently: each new recovery requires exactly ranks 1–100 and 100 unique ASINs before it is considered current.
- Daily history-title repair is now scoped to the newest `root_rank_history` date for each region and runs after live Top100 title completion. It updates only blank title cells and never rewrites history keys or old dates. This restores today's history titles without putting the full 33k-row historical repair back in the critical path.
- Watchdog coverage now includes freshness stamps on all 15 published workbook data tabs: five regional Top100 tabs, five regional Rank History tabs, and five aggregate/analytics tabs. Any missing, invalid, or stale tab stamp makes the workbook watchdog report unhealthy and triggers the configured alert. Top100 stale-region tracking remains separately scoped so recovery targets are accurate. Full suite: 46 passed.
- 14:35 KST catch-up exposed a region-case mismatch at two CLI boundaries: the pipeline accepts uppercase region names, while `run_job.py` accepts lowercase names. The first correction changed the wrong boundary; a second guard now explicitly normalizes pipeline region arguments before invoking `run_job.py`. No Amazon request or Sheet write occurred in either rejected invocation. The fallback workbook was regenerated and updated in the same Drive file. Regression tests cover both boundaries; suite now passes 48 tests.
- Corrected UK-only recovery then succeeded: 100/100 rows crawled and published, 100 `root_rank_history` rows appended, and one missing Top100 title filled. The title completion pass audited all five regions at 100/100 and repaired 65 blank title cells on the latest history date. The ~3.14MB fallback XLSX was updated in place under the existing Drive file ID.
- The recovery's aggregate-view refresh hit Google's per-user Sheets write quota because `root_publish` sent one API write for every 30KB history chunk. It wrote stamps before finishing data, so the older watchdog could mistake a partially written view for a complete one. Fix in progress: batch multiple ranges into fewer requests, retry idempotent quota-limited writes after 65 seconds, and write each freshness stamp only after all tab data succeeds. Partial-run resume now evaluates only regions in that run's summary.
- First rollout of the batching fix exposed this host's lower `ARG_MAX`: a 600KB gws argument was rejected locally before submission. Batch payloads are now capped below 90KB and covered by a row-contiguity/size test. Suite: 51 passed. The failed attempt did not mark its incomplete tab fresh; deploy this bounded version and rerun aggregate refresh.

## 2026-10-29 final recovery verification
- The quota retry, <90KB bounded batching, stamp-after-success logic, partial-run region accounting, and Linux-native schedule lock are pushed and deployed to LIAM2/LIAM3. The full repository suite passes 57 tests.
- LIAM3's aggregate publisher succeeded at 14:44. At 14:45, the live audit found all 15 workbook tabs fresh; `root_rank_history` had 33,631 data rows; all five 10/29 date-region cohorts had 100 unique ASINs; duplicate keys and internal blank rows were both 0.
- The corrected read-only report audit found all five live Top100 tabs at 100/100 titles. Four report emails were accepted by SMTP for both configured recipients; the final email included the fallback XLSX, and the report path invoked Telegram delivery.
- Next LIAM3 primary run: 10/30 05:00 KST. Catch-up remains enabled at :55 hourly; watchdog remains enabled at :00 hourly. Daily timer is nonpersistent.

## 2026-10-29 scheduler lock hardening
- The scheduled 14:55 catch-up exited in 5ms with status 1 before Python emitted output. Running the same catch-up directly returned the expected “all regional tabs are current and titles are complete.” This points to `flock -n` failing to acquire the shared lock at that instant; the competing holder had exited before it could be identified.
- Moved the shared lock from the repo on `/mnt/c` to `~/.cache/amzbs/locks/daily_pipeline.lock` on native WSL Linux storage. Added `run_locked_schedule.sh`: lock contention is logged as an intentional skip with exit 0, while child failures preserve their exit code. LIAM3 systemd units were reinstalled; LIAM2's 05:30 secondary cron was updated to use the same native lock and wrapper.
- Verified the LIAM3 systemd catch-up service itself at 14:57: it exited successfully after confirming all regions and titles current. Regression suite: 53 passed; shell syntax checks passed. Next automatic catch-up is 15:55, daily primary is 10/30 05:00 KST.

## 2026-10-29 shared-view automatic recovery
- Catch-up now checks freshness on the five aggregate tabs as well as regional Top100/title gaps. A stale shared tab triggers `publish-root --region es --shared-views-only`, rebuilding `[ALL] Top 100`, `trend_14d`, `Cross-Region Catalog`, `Rank Changes`, and `Price History` from SQLite without recrawling Amazon, rewriting regional Top100 tabs, or appending history.
- The publisher marks each GWS tab `UPDATING` before changing its data and writes a valid timestamp only after all bounded batches succeed. The catch-up rereads all five aggregate stamps after publishing; any failure or stale remainder returns failure, sends the throttled email/Telegram alert, and retries on the next hourly catch-up (45-minute minimum attempt spacing).
- Added regression coverage for stale-tab detection, aggregate-only recovery routing, post-publish verification, and the publisher's no-regional-write/no-history-append contract on both GWS and Service Account backends. Local suite: 58 passed. Deployed to LIAM2/LIAM3; LIAM3 live shared-only publish and post-publish verification succeeded at 15:24 KST.
- Live verification after the shared-only publish: all five aggregate tabs stamped 15:24, all 15 monitored tabs fresh, regional Top100/history stamps unchanged, 33,631 history rows, each latest 10/29 region cohort 100 unique keys, 0 duplicates, 0 internal blanks. LIAM3 catch-up systemd service also exited 0 at 15:24.

## 2026-10-29 Drive delivery hardening
- GWS Drive list/get/update now retry bounded transient and rate-limit failures; idempotent updates retry after backoff, while non-idempotent creates remain single-shot to avoid duplicate files after ambiguous responses.
- Every GWS upload now reads the remote file back and verifies its ID, MIME type, byte size, MD5, target folder, and non-trashed state. Catch-up also checks the saved fallback's remote file on each hourly pass; a deleted, moved, or mismatched file is treated as a delivery gap and re-uploaded. Authentication/API unavailability becomes a visible delivery gap and uses the existing throttled alert/retry path.
- Local XLSX remains available and attached to email even when Drive fails. Regression suite: 61 passed. Deployed the uploader and catch-up verifier to LIAM2/LIAM3; both passed `py_compile`.
- LIAM3 live test at 15:42 KST updated the existing fallback file in place (Drive ID `1P1V92U9cCkeMXZfKekSLbhB3rIlZVu3R`); the post-upload remote readback passed ID, XLSX MIME, byte-size, MD5, parent-folder, and non-trashed checks. The LIAM3 catch-up systemd run then exited 0 after its hourly remote-file audit.

## 2026-10-28 Shared operational email
- Scheduled report email now uses the shared SMTP mailer; the Gmail API/OAuth mail path was removed from `scripts/run_job.py`. Drive/Sheets OAuth is independent.
- SMTP credentials live at `~/.config/a4-mailer/smtp.env` on the node's private Linux filesystem (directory `0700`, file `0600`). Recipient lists remain repository-specific.
- The A4 sender inventory was wired to load this common transport as a default without overriding explicit project settings.
- SMTP authentication and delivery passed on 2026-10-28 from the LIAM1 WSL, LIAM2 WSL, and LIAM3 WSL. Each test delivered to the two repository-configured recipients. LIAM2/LIAM3 used the shared transport checker; LIAM1 exercised `run_job._send_email`, the production notification function. No crawler or Sheet write was run.
- LIAM2 and LIAM3 have the updated Amazon sender and common helper. LIAM3's other installed A4 mailers were also connected and backed up before edits.
- If Amazon email delivery fails or has no configured recipient, `run_job.py` now reports the SMTP failure through Telegram when Telegram is configured; it never retries via Gmail OAuth.
- This shell is LIAM1's Ubuntu WSL (Windows host `DESKTOP-RO042LL`). LIAM1 SSH still times out, but local WSL mail delivery is verified. LIAM1's local cron service is stopped; production scheduling is on LIAM3 with LIAM2 takeover. LIAM4 remains unverified.

## Repository
- repo: `crawl_amazon_beauty_bestsellers` - PUBLIC: https://github.com/free-gunw607/crawl_amazon_beauty_bestsellers
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`

## Current Objective
Collect Amazon Beauty & Personal Care Top 100 across 5 regions (US/DE/UK/FR/ES), publish to the primary Google Sheet `beauty_personal_care_top100_live`, and keep the daily 5AM KST pipeline recoverable with stale-sheet alerting.

## 2026-10-28 Service Account Recovery
- LIAM3 is the primary scheduler (05:00 KST + hourly catch-up/watchdog); LIAM2 is the secondary takeover worker (05:30 KST).
- Both cron blocks now use `AMZ_BS_ROOT_BACKEND=sa` and a node-local key at `~/.config/amzbs/service-account.json` (directory mode 700, key mode 600). The key was added as a writer to the primary Sheet and Drive fallback folder; existing rows/files were not deleted or replaced.
- LIAM3 and LIAM2 each passed the Service Account read-only sheet watchdog. LIAM2 catch-up and title-history checks also ran safely as no-ops against the already-current 2026-10-28 sheet.
- 2026-10-28 Top 100 published 100 rows in all five regions. Title completion first hit the per-user Sheets write quota; the retry completed all five regions at 100/100.
- Historical title recovery filled 354 titles via local/current mappings, then recovered the remaining 35 blank cells (21 region-ASIN groups) through polite marketplace product-page lookups. No block signal occurred. The history tab now has zero blank title cells. This updated title cells only; no history rows were deleted or inserted during this title repair.
- Read-only Drive inventory confirms exactly one fallback XLSX per date 2026-10-23 through 2026-10-28. LIAM3 local-source-versus-sheet history comparison for 2026-10-23 through 2026-10-27 found zero missing local keys; 104 sheet-only keys were preserved.
- Historical scheduled root publishing failed on 2026-10-24 through 2026-10-27 because the user OAuth credential was expired/revoked. LIAM3's 2026-10-28 05:00 run also started before the Service Account switch and used GWS OAuth. The next scheduled primary run (2026-10-29 05:00 KST) is the first full production run on the Service Account path.
- Historical note (superseded 2026-10-28): Gmail OAuth previously blocked mail. Operational email now uses shared SMTP; Google OAuth/Service Account is separate and used for Drive/Sheets.
- `scripts/enrich_titles_until_complete.py` now reads and writes Sheets through the configured Service Account and retries transient/quota API errors. `scripts/backfill_history_titles_from_marketplaces.py` repairs only blank history-title cells, stops on Amazon block signals, and never alters row keys.
- 2026-10-28 pipeline repair: today's 05:00 run collected and published 500/500 rows, appended 245 `root_rank_history` rows, reached 100/100 titles in every regional tab, and created/uploaded the independent fallback XLSX. It was marked failed only because the same run attempted 389 old history-title repairs and hit the Sheets per-user write quota after 354 updates (35 blanks remained at that checkpoint).
- Removed the whole-history title repair from the daily critical path; the daily job still verifies all five live Top 100 tabs and the root publisher appends today's history rows. The report now displays per-region history append counts and only marks complete when the Drive fallback file exists.
- Added `--report-existing` to re-audit and resend a saved run without recrawling or creating a duplicate Drive workbook. Used it on 2026-10-28: read-only live audit confirmed 100/100 titles in US/DE/UK/FR/ES; all four phase/final report emails were accepted by SMTP with the existing fallback XLSX attached to the relevant reports.
- LIAM2 and LIAM3 were rechecked against the live Sheet using their Service Account identities at 23:12 KST; both reported all five tabs current, zero stale regions, 32,632 history rows, newest marketplace history date 2026-10-27. Their read-only catch-up commands both returned “all regional tabs already have today's stamp.”
- The LIAM2 `invalid_grant` lines are from its 05:30 catch-up run before the Service Account switch; the same catch-up code with the installed SA environment now passes. The old errors were GWS OAuth, not SMTP.

## Primary Live Sheet
- title: `beauty_personal_care_top100_live`
- spreadsheet id: `1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80`
- URL: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- important tabs: `[US] Top 100`, `[DE] Top 100`, `[UK] Top 100`, `[FR] Top 100`, `[ES] Top 100`, `root_rank_history`, `trend_14d`, `Cross-Region Catalog`, `Rank Changes`, `Price History`

## 2026-10-16 Automation Recovery
- Scheduler `gws` OAuth had an `invalid_grant` refresh token. The first re-auth was made in the wrong default config; the cron-owned config at `A3-runtime-standards/local-config/gws` was then re-authorized with Sheets and Gmail scopes.
- Gmail API is enabled for that OAuth project. End-to-end email alert and Telegram alert smoke tests both succeeded.
- The 05:00 root upload completed for all five regions. Final live-Sheet verification after the completion pass: `US 09:12`, `DE 09:23`, `UK 09:38`, `FR 09:49`, `ES 10:00 KST`; all five Top 100 tables have `99/99` populated title rows.
- The 05:20 completion schedule now covers `us de uk fr es` and resolves the exact live-Sheet blanks through marketplace fallback. It no longer wastes its daily run on stale DB-wide title queues.
- The fallback publisher explicitly enforces the authenticated `gws` backend outside cron too, and republishes after a prior title lookup succeeded but publish failed.
- The hourly watchdog was tested at 10:03 KST: `ok=true`, no stale regions, `root_rank_history` newest date `2026-10-16`.
- `root_rank_history` title backfill on this recovery updated 313 current-mappable titles. Historical rows without a locally/currently resolvable title remain and are separate from the daily Top 100 completeness guarantee.
- Corrected the Top 100 verification range from `A4:C103` to `A4:C104`: row 4 is a header, and rank 100 is row 104. Final live audit confirms US/DE/UK/FR/ES and `[ALL] Top 100` are all `100/100` titled.
- `[ALL] Top 100` had been excluded from the publisher and was stale since 2026-08-31. It now regenerates from the five latest regional snapshots as a deduplicated global Top 100.
- Daily fallback workbook is built directly from the local SQLite store, not exported from Google Sheets. It contains the five regional Top 100 tabs, `ALL Top 100`, history, and analytics; it is uploaded to Drive and emailed as an attachment. A live Drive upload and attachment-email test succeeded on 2026-10-16: file id `1MOde3GPApRCUDcGphsIik-hFj3Bgn_AG`.
- The daily schedule is a single sequential orchestrator at 05:00, not independent 05:00/05:20/06:00 jobs. It waits for root upload before title completion, then creates the independent fallback workbook; if root upload fails, title completion is skipped but the fallback workbook still runs from the local store. It emits a dual-channel delay alert after 20 minutes and uses `flock` to prevent overlap with another day.

## 2026-10-13 Recovery Status
- Today 05:00 KST did not run automatically.
- Evidence:
  - before repair, active crontab did not contain a `crawl_amazon_beauty_bestsellers` job;
  - user systemd timers could not be used in this environment (`Failed to connect to bus: No such file or directory`);
  - `.agent/logs/` had no 2026-10-13 05:00 run log for this repo.
- A cron fallback is now installed:
  - `0 5 * * * ... scripts/run_job.py --no-detail >> .agent/logs/cron_run_job.log 2>&1`
  - `17 * * * * ... scripts/watchdog_sheet.py --max-age-hours 30 --alert >> .agent/logs/cron_watchdog.log 2>&1`
- Cron environment now includes the working `gws` path and config:
  - `PATH=/home/liam/.nvm/versions/node/v20.20.1/bin:...`
  - `AMZ_BS_ROOT_BACKEND=gws`
  - `AMZ_BS_ROOT_SHEETS_ID=1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80`
  - `GOOGLE_WORKSPACE_CLI_CONFIG_DIR=/home/liam/agent-coding/agent-system/A3-runtime-standards/local-config/gws`
- Manual recovery on 2026-10-13 KST updated the primary Sheet 3. Watchdog verification at 07:00 KST:
  - `US`: `2026-10-13 06:54 KST`
  - `DE`: `2026-10-13 06:39 KST`
  - `UK`: `2026-10-13 06:43 KST`
  - `FR`: `2026-10-13 06:34 KST`
  - `ES`: `2026-10-13 06:34 KST`
  - `root_rank_history_rows`: `10921`
  - `root_rank_history_newest_date`: `2026-10-12`
- A full `scripts/run_job.py` manual attempt published root sheets first but then hung in `fill-gaps`; the daily cron now uses `--no-detail` so Top100/history publishing is not blocked by detail enrichment.
- A cron-equivalent `scripts/run_job.py --no-detail` attempt completed the core path but returned nonzero because of live collection issues:
  - `US` published successfully;
  - `DE/UK/FR` had transient DNS resolution failures;
  - `ES` hit a captcha/block signal;
  - `fill-titles --region us` timed out after 240s.
- Follow-up schedule validation on 2026-10-13 09:36 KST fixed the daily lane so `--no-detail` is root-cycle only. It completed in 1m37s with `rc=0` and published 100 rows for every region.
- Final Sheet verification at 09:38 KST:
  - `US`: `2026-10-13 09:36 KST`
  - `DE`: `2026-10-13 09:37 KST`
  - `UK`: `2026-10-13 09:37 KST`
  - `FR`: `2026-10-13 09:37 KST`
  - `ES`: `2026-10-13 09:37 KST`
  - `root_rank_history_rows`: `11352`
  - `root_rank_history_newest_date`: `2026-10-13`
- `scripts/run_job.py` now releases stale locks even on `KeyboardInterrupt`/fatal crashes.
- Historical note (superseded 2026-10-28): email alert support previously used Gmail API through `gws`. Operational mail now uses shared SMTP.
- Telegram alert support now accepts `TG_*`, `TELEGRAM_*`, and common `BOT_TOKEN`/`CHAT_ID` env names, and falls back to the gitignored WH env files used by `build_ops_powerhouse` / `capture_finance_pdf_news`. A verified Telegram smoke sent successfully on 2026-10-13 KST.
- Title completeness recovery on 2026-10-13:
  - initial Sheet title state after fast root publish: `US 100/100`, `DE 100/100`, `UK 100/100`, `FR 82/100`, `ES 75/100`;
  - root-page parser provides 100 ASIN/rank rows, but Amazon only renders about 60 titles in the root DOM; `data-client-recs-list` has ASIN/rank but no title metadata;
  - existing `/dp/ASIN` title enrichment works, but must run as small batches or it can hold the daily publish lane;
  - added `scripts/enrich_titles_until_complete.py`, which repeats bounded `fill-titles --publish-root`, measures live Sheet completeness after each round, and falls back to alternate marketplaces for stalled ASINs;
  - final verified Sheet title state: `US 100/100`, `DE 100/100`, `UK 100/100`, `FR 100/100`, `ES 100/100`;
  - ES final stalled ASIN `B08B981F4X` was filled via DE/UK fallback title lookup.
- `root_rank_history` title backfill:
  - `scripts/enrich_titles_until_complete.py` now backfills blank `root_rank_history!I:I` cells after title enrichment using current Top100 titles and local DB/product detail title history;
  - 2026-10-13 rows are now `400/400` titled;
  - historical audit before backfill: `1972/11352` history rows lacked titles (`17.37%`);
  - after Top100 + DB fallback backfill: `693/11352` rows still lack titles (`6.10%`);
  - remaining historical blanks are older ASINs that are not present in current Top100 mapping or local DB title history; new daily rows should be backfilled by the scheduled enrichment job.

## 2026-10-12 Recovery Status
- Local repo was stale at `9850d18`, 48 commits behind `origin/main`; it has now been fast-forwarded to `d98edaf`.
- Latest pushed code was already on `origin/main`; the immediate missing-code problem was local staleness, not evidence that `liam3` had unpushed commits.
- Manual root-cycle publish succeeded to the primary Sheet 3 using the workspace `gws` config dir:
  - `US`: 100 crawled / 100 published; sheet stamp `2026-10-12 09:13 KST`
  - `DE`: 100 crawled / 100 published; sheet stamp `2026-10-12 09:20 KST`
  - `UK`: 100 crawled / 100 published; sheet stamp `2026-10-12 09:19 KST`
  - `FR`: 100 crawled / 100 published; sheet stamp `2026-10-12 09:20 KST`
  - `ES`: 100 crawled / 100 published; sheet stamp `2026-10-12 09:19 KST`
- `root_rank_history` received same-run append rows. US rows appear as `2026-10-11` because history dates use marketplace timezone, while execution was `2026-10-12` KST.
- `src/crawl_amazon_beauty_bestsellers/root_publish.py` now supports `AMZ_BS_ROOT_BACKEND=gws`, reusing the proven workspace Google Workspace CLI OAuth path.

## Failure Causes Identified
1. Local checkout was not current: it was 48 commits behind `origin/main`.
2. The active crontab no longer contains this repo's old local lane; `.agent/crontab_backup_20260826.txt` preserves the prior line only as backup.
3. The interim scheduler loop was not durable; `.agent/logs/scheduler_loop.log` stops after 2026-08-25 23:18 KST.
4. Earlier cron-era Sheets publish failed because `gws` was not available/configured in the cron environment.
5. The latest root publisher expected `~/.config/gsheet-sync/{client_secret.json,refresh_token.json}`, but this machine's valid OAuth state is the workspace-local `gws` config at `/home/liam/agent-coding/agent-system/A3-runtime-standards/local-config/gws`.
6. Service-account Drive upload reached Google but failed with Drive storage quota; owner OAuth via `gws` is the working path for Drive/Sheets.
7. Sandboxed network calls to Amazon failed; escalated network runs are required for live crawling from this environment.
8. Amazon captcha/block signals still occur under pressure; the repo policy is to stop/cool down instead of retry storming.
9. `run_job.py` full pipeline can spend a long time in `fill-titles`; the urgent 2026-10-12 sheet recovery used `root-cycle` per region to avoid blocking on enrichment.

## Scheduler
- active fallback: crontab block `crawl_amazon_beauty_bestsellers`
- daily pipeline: `05:00 KST`, `scripts/run_daily_pipeline.py` (root publish, then exact-blank title completion, then independent local-data XLSX)
- hourly stale-sheet watchdog: `:17`, `scripts/watchdog_sheet.py --max-age-hours 30 --alert`
- daily XLSX Drive vault + email attachment: `scripts/export_fallback_workbook.py --email`, generated from SQLite and independent of Google Sheets read/write
- intended systemd units remain in `deploy/systemd/`, but user systemd is not currently usable in this environment.

## Key Files
- `scripts/run_job.py` - orchestrator for root-cycle5 regions + fill-titles + report
- `src/crawl_amazon_beauty_bestsellers/cli.py` - CLI commands
- `src/crawl_amazon_beauty_bestsellers/root_publish.py` - primary Sheet 3 publisher
- `src/crawl_amazon_beauty_bestsellers/sheets_publish.py` - gws/token/SA sheet helper paths
- `src/crawl_amazon_beauty_bestsellers/storage/store.py` - SQLite storage and analytics queries
- `deploy/systemd/amzbs-beauty.service`
- `deploy/systemd/amzbs-beauty.timer`
- `deploy/systemd/amzbs-beauty-watchdog.service`
- `deploy/systemd/amzbs-beauty-watchdog.timer`
- `scripts/watchdog_sheet.py`
- `scripts/enrich_titles_until_complete.py`
- `scripts/backfill_history_titles_from_marketplaces.py`

## Pending
- Stabilize `liam1` SSH/Tailscale and document the liam1-3 repo synchronization path.
- Monitor the next unattended 05:00 pipeline through its log and the delivered dual-channel report.
- Decide whether `fill-titles`/`fill-gaps` should become a separate throttled enrichment cron rather than part of the daily Top100 publish lane.
