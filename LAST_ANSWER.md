# LAST ANSWER

## Current state
- v0.1 single-panel collector is live-verified end to end (2026-08-25)
- Skin Care Products panel (`zgbs/beauty/11060451`): list 60/60 parsed with USD price+rating; details 50/50 with BSR and manufacturer at 100%
- US delivery-location pinning works: session bootstrap pins ZIP 10001 via glow address-change, USD confirmed
- 67 beauty categories discovered and registered (`config/category_registry.json`)
- hourly scheduler entry point proven (`scripts/run_job.py`, lockfile + logs)

## Deliverable proof
- artifact paths:
  - `artifacts/db/bestsellers.sqlite` (360 list rows / 103 detail rows accumulated)
  - `artifacts/snapshots/11060451/*/list.{jsonl,csv}`
  - `artifacts/details/*.jsonl`
  - `artifacts/exports/xlsx/amazon_bs_20260825.xlsx`
  - `.agent/runs/run_*.json` (atomic run manifests)
- proof timestamp: 2026-08-25 00:51 KST
- tests: `python3 -m pytest tests/ -q` → 5 passed

## How to operate
- one cycle: `./repo run --node 11060451`
- read API: `./repo serve` then GET `/latest/11060451`
- daily workbook: `./repo export-xlsx`

## Pending owner decisions (approval gates)
1. activate the hourly schedule (systemd user timer or cron running `scripts/run_job.py`)
2. Google Drive service account creation + `GDRIVE_CREDS` registration to enable `drive_upload.py`

## Known data realities
- ~31 of 50 top ASINs do not ship to a US ZIP address; their buy-box price/seller are legitimately absent on the detail page and recorded as such (list-page reference price still captured for all)
- list page shows 60 entries across 2 pages (Amazon grid layout), rank order preserved

## Resume pointer
- restart work at `./repo run --node 11060451`; parser iteration workflow: `--save-raw` then inspect `artifacts/raw/`

## Phase status
- current phase: v0.1 verified, awaiting schedule + Drive approvals
- next phase: multi-category staged activation

## Durable handoff path
- repo root `LAST_ANSWER.md` is the current summary
- `.agent/answers/` stores archived timestamped copies
- `.agent/state/project_state.json` stores machine-readable current state
