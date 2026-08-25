# LAST ANSWER

## Current state
- v0.3: 9 production panels registered and collected; same-day double-block recovery proven (2026-08-25)
- Schedule: crontab entries REGISTERED (hourly lists + 6h detail pass, lockfile-safe); cron daemon start is one owner command (`sudo service cron start`) because WSL2 has no systemd and cron isn't running
- Drive: `./repo upload-drive` wired end-to-end except credentials — owner must supply GCP service-account JSON + folder id

## What happened today (compressed)
1. crash recovery → baseline reverified
2. batch 1+2 expansion: 7 panels approved & collected cleanly
3. hard block on Serums detail (03:40) → immediate stop per policy
4. cooldown → probe clean → retry soft-blocked (50 empty parses at 10:19)
5. junk rows purged; second cooldown → detached retry with --save-raw → 46/50 details, BSR 100% (11:33–12:10)
6. schedule designed for politeness (hourly lists ≈30 req/h; details 6-hourly), registered in cron + systemd units kept as alternative

## Deliverable proof
- `artifacts/db/bestsellers.sqlite`: ~1500 list rows / ~560 detail rows across 9 nodes
- `artifacts/exports/xlsx/amazon_bs_20260825.xlsx` (regenerate anytime: `./repo export-xlsx`)
- `.agent/runs/run_*.json`: full manifest trail including both block events
- tests: `python3 -m pytest tests/ -q` → 5 passed

## How to operate
- manual single panel: `./repo run --node <id>` / all-panel list pass: `PYTHONPATH=src python3 scripts/run_job.py --no-detail`
- health/block telemetry: `./repo health` (alerts when any ratio < 0.5)
- workbook: `./repo export-xlsx`; upload after creds: `./repo upload-drive`
- schedule install (systemd envs): `scripts/install_schedule.sh install|status|uninstall`

## Pending owner actions (only these remain)
1. `sudo service cron start` — activates the already-registered hourly/6h schedule
2. GCP service account JSON → set `GDRIVE_CREDS`, `AMZ_BS_DRIVE_FOLDER_ID` (share folder with SA email) → test `./repo upload-drive`
3. optional: `/etc/wsl.conf` boot command so cron survives WSL restarts

## Known data realities
- buy-box price/seller exist only for US-shippable items (~40–63% by panel); list reference price captured for all
- detail counts vary 40–75 by panel (bounded variant expansion ≤5/parent, cap 25)
- ASIN B01MDTVZTZ failed fetches in all three attempts today (transient errors, not captcha) — watch it, not urgent

## Resume pointer
- if session dies: read STATUS.md "Schedule status" + "Next actions"; everything durable lives in git + `.agent/`
- next natural milestone: first automated cron cycle log at `.agent/logs/cron_list.log`

## Wisdomhouse candidates (recommended to owner, not promoted)
1. soft-block telemetry via field-completeness ratios (extends `WH-CRAWL-FIXFIN-001`)
2. setsid-detach + stale-manifest marking for long crawls driven by agent tooling

## Phase status
- current phase: v0.3 scheduled-ops pending owner daemon start
- next phase: multi-day automated accumulation → next registry batch

## Durable handoff path
- repo root `LAST_ANSWER.md` (this file) + `STATUS.md`
- `.agent/answers/` archives timestamped copies
- `.agent/state/project_state.json` machine-readable state incl. block_events array
