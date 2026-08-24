# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers`
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- standardized project name: `crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon.com beauty-sector bestseller lists and product detail/vendor intelligence on an hourly schedule, accumulate time-series locally, publish Excel to Google Drive

## Current phase
v0.2 multi-category expansion — 7 panels live-collected; expansion HALTED by block event (2026-08-25 ~03:40 KST)

## Active production panels (7)
| node | panel | last cycle |
|---|---|---|
| 11060451 | Skin Care | verified 2026-08-25 v0.1 (60 list / 103 details accumulated) |
| 11060711 | Face | 2026-08-25 02:42 — 60 list / 75 detail, BSR 73/75 |
| 11060521 | Body | 2026-08-25 03:10 — 60/75, BSR 74/75, USD+seller 45/75 |
| 11061941 | Eyes | 2026-08-25 03:21 — 60/75, BSR 75/75, USD+seller 36/75 |
| 11060661 | Moisturizers | 2026-08-25 03:26 — 60/40, BSR 40/40 |
| 11062651 | Sunscreens | 2026-08-25 03:47 — 60/44, BSR 43/44 |
| 11056291 | Body Washes | 2026-08-25 ~03:52 — 60/75, BSR 75/75, USD+seller 47/75 |

Partial: `7792528011` (Face Serums) — registry-approved, bestseller list OK (60/60), detail aborted at 1/50 by block detection. Needs one full re-run after cooldown.

## Current blockers
1. **BLOCK EVENT**: captcha/block page on second detail fetch for node 7792528011 (run 20260825_0340_a8f5dc). Pipeline stopped immediately per policy (no retry storm). All live crawling paused; cooldown ≥1h before any probe.
2. Schedule activation awaits owner approval (per global policy §5.3)
3. Drive service-account registration awaits owner approval

## Resume procedure (after cooldown)
1. single light probe: `./repo crawl-list --node 7792528011` — if clean, continue; if blocked, extend cooldown
2. complete the interrupted panel: `./repo run --node 7792528011`
3. only then consider further category batches (registry-first lifecycle unchanged)

## Recent completed work (2026-08-25 session 2)
- crash recovery handoff: baseline reverified (tests 5 passed, preflight/compliance clean, live USD probe OK)
- docs catch-up for commit 665f572 (universal list types, health_checks table, bounded variant expansion)
- batch 1 dry-run → approve → full cycle: Face, Body, Eyes, Moisturizers
- block-signal scan clean at checkpoint → batch 2: Sunscreens, Body Washes approved and collected; Serums list-only then block hit
- stop-on-block behavior verified in practice: immediate halt, zero retries, explicit error in run manifest
- xlsx regenerated over 8 nodes (`artifacts/exports/xlsx/amazon_bs_20260825.xlsx`)

## Capability and MCP status
- required external capabilities: none missing; curl_cffi installed to user site (PEP 668 --user)
- approved but not active: Drive service-account upload (`drive_upload.py` ready, needs GDRIVE_CREDS + folder id)
- active MCP dependencies: none

## Progress snapshot
- overall progress: 70% (was 60%) — 7 of ~67 categories collecting, scheduler proven, export pipeline done
- current confidence: high for single-cycle collection; low for sustained hourly pacing until block cause is observed over cooldown
- current stability: live data accumulating; live crawling intentionally paused

## Next actions
1. after ≥1h cooldown: Serums re-probe + completing run (resume procedure above)
2. owner decision: activate hourly systemd timer / cron for `scripts/run_job.py`
3. owner decision: GCP service account + GDRIVE_CREDS registration, wire Drive upload into run cycle
4. next category batch only after a full clean multi-hour window

## Reusable-pattern notes
- anti-bot ladder and transient-only retry follow `WH-CRAWL-FIXFIN-001`
- atomic run manifests follow `WH-RUNTIME-AGORA-001`
- category registry lifecycle follows `WH-CATALOG-MULTI-001`
