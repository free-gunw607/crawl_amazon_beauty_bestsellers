# LAST ANSWER

## Current state
- v0.2 multi-category collector: 7 production panels collected end-to-end (2026-08-25)
- Panels: Skin Care 11060451, Face 11060711, Body 11060521, Eyes 11061941, Moisturizers 11060661, Sunscreens 11062651, Body Washes 11056291 — all list pages parse 60/60 with USD price + rating
- Face Serums 7792528011: approved; list OK (60/60) but detail crawl was halted by a captcha/block page at item 2 (run `20260825_0340_a8f5dc`)
- Live crawling is intentionally PAUSED since ~03:40 KST per stop-on-block policy

## Block event
- second detail fetch of run `20260825_0340_a8f5dc` returned a block page → pipeline stopped immediately, no retries
- ~400 detail fetches had accumulated over the session before the signal; treat as volume-based rate pressure until proven otherwise
- cooldown: no Amazon requests for ≥1 hour, then resume procedure in `STATUS.md`

## Deliverable proof
- artifact paths:
  - `artifacts/db/bestsellers.sqlite` (1260 list rows / 488 detail rows across 8 nodes)
  - `artifacts/snapshots/<node>/<ts>/list.{jsonl,csv}` and `artifacts/details/*.jsonl`
  - `artifacts/exports/xlsx/amazon_bs_20260825.xlsx` (regenerated post-expansion)
  - `.agent/runs/run_*.json` (atomic run manifests incl. the blocked one)
- proof timestamp: 2026-08-25 04:00 KST
- tests: `python3 -m pytest tests/ -q` → 5 passed

## How to operate
- one cycle: `./repo run --node <id>` or all approved nodes: `PYTHONPATH=src python3 scripts/run_job.py`
- read API: `./repo serve` then GET `/latest/<node_id>`
- daily workbook: `./repo export-xlsx`
- panel health: `./repo health`

## Pending owner decisions (approval gates)
1. when to resume after cooldown (or leave to next session following STATUS resume procedure)
2. activate the hourly schedule (systemd user timer or cron running `scripts/run_job.py`)
3. Google Drive service account creation + `GDRIVE_CREDS` registration to enable `drive_upload.py`

## Known data realities
- buy-box price/seller exist only for US-shippable items (~40–85% by panel); unshippable items recorded with explicit availability reason; list-page reference price captured for all
- detail counts vary (40–75) due to bounded variant expansion: ≤5 variants/parent, cap 25/panel
- movers_and_shakers is client-rendered and gracefully skipped (documented in commit 665f572)

## Resume pointer
- restart work at the STATUS.md "Resume procedure": light list probe on 7792528011 → `./repo run --node 7792528011`
- parser iteration workflow: `--save-raw` then inspect `artifacts/raw/`

## Phase status
- current phase: v0.2 paused-by-policy (7/7 clean panels + 1 partial)
- next phase: cooldown recovery → hourly schedule activation (owner gate) → further batches

## Durable handoff path
- repo root `LAST_ANSWER.md` is the current summary
- `.agent/answers/` stores archived timestamped copies
- `.agent/state/project_state.json` stores machine-readable current state
