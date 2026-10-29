# LAST ANSWER

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
