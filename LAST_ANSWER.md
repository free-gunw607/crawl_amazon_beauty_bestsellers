# LAST ANSWER

## Current state
- v0.4: **PUBLIC repo live** (https://github.com/free-gunw607/crawl_amazon_beauty_bestsellers) with GitHub Actions collecting all 8 panels every 6h and committing the public dataset back — 3 verified runs, `ok:8 failed:0`
- Architecture empirically split: runner IPs pass list pages but are captcha-blocked on /dp/ → cloud owns lists, local home-IP line owns detail passes (crontab registered, fires when cron daemon starts)
- Drive publishing wired both ways: CI via `GCP_SA_JSON` secret (auto-skip until provided), locally via gws OAuth (already proven)

## Deliverable proof
- public dataset commits: `a11e335`, `3703b33` (17 files: per-node list.csv/jsonl) + workbook export each run
- run trail: workflow runs 32856162687 / 32857639481 / 32859096238 (success)
- local DB: ~1,500 list / ~560 detail rows; tests 5 passed; health alerts NONE

## How to operate
- watch automation: https://github.com/free-gunw607/crawl_amazon_beauty_bestsellers/actions
- manual cloud cycle: `gh workflow run collect.yml -f detail=false`
- local manual cycle: `PYTHONPATH=src python3 scripts/run_job.py`
- publish rich workbook from local DB: `./repo export-xlsx && ./repo upload-drive`
- block telemetry: `./repo health`

## Pending owner actions (2)
1. **GCP console steps** (Drive CI publishing):
   a. console.cloud.google.com → project create/select
   b. APIs & Services → Library → enable **Google Drive API**
   c. IAM → Service Accounts → create (`amazon-bs-publisher`) → Keys → Add key → JSON → download
   d. Drive folder `crawl_amazon_beauty_bestsellers` → Share → SA email as Editor
   e. tell me the JSON path → I run `gh secret set GCP_SA_JSON` (+ folder id secret) → CI step goes live
2. **cron daemon**: run `sudo service cron start` once → local 6h detail lane goes automatic (crontab already registered at :17 KST). Optional persistence: `/etc/wsl.conf` `[boot] command=service cron start`

## Known realities
- runner detail fetches always captcha on first /dp/ hit — by design we stop there (stop-on-block policy); don't "fix" this from CI, it's an IP-reputation wall
- ASIN B01MDTVZTZ repeatedly transient-fails locally too — watch next local pass
- SQLite no longer committed (local-only); public dataset = csv snapshots + xlsx

## Wisdomhouse — PROMOTED (owner-approved 2026-08-26)
4 entries under episode `EP-AMZBS-DUALOPS-20260826-01`: soft-block telemetry (`WH-CRAWL-AMZBS-001`), cloud-lists/local-details lane split (`WH-CRAWL-AMZBS-002`), privilege-free scheduler (`WH-RUNTIME-AMZBS-001`), SA-quota boundary + formula-driven Sheets (`WH-DATA-AMZBS-001`). Canonical: A2 `Wisdomhouse/by-repo/crawl_amazon_beauty_bestsellers.md`
4. **cloud-lists/local-details lane split** for datacenter-blocked scraping targets

## Resume pointer
- everything durable in git + `.agent/`; restart-from-nothing = clone repo + read STATUS.md top table

## Phase status
- current phase: v0.4 dual-lane operations (cloud LIVE, local armed)
- next phase: SA credential wiring → multi-day accumulation → next registry batch
