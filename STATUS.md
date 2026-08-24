# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers`
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- standardized project name: `crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon.com beauty-sector bestseller lists and product detail/vendor intelligence on an hourly schedule, accumulate time-series locally, publish Excel to Google Drive

## Current phase
v0.1 single-panel implementation live-verified (Skin Care 11060451)

## Current focus
- hourly schedule activation (owner approval gate)
- Google Drive service-account registration (owner approval gate)
- staged expansion to remaining 66 discovered categories

## Recent completed work (2026-08-25)
- bootstrap via `new_project.sh`; registered in A2 `Projects.md` (2.11)
- curl_cffi chrome-transport client with US delivery-location pinning (ZIP 10001) — USD confirmed on live probe
- bestseller list parser live-verified: 60/60 entries, price/rating 100%, zero warnings
- product detail parser live-verified at scale: 50/50 details, BSR 50/50, manufacturer 50/50, ingredients 38/50; buy-box price+seller captured for US-shippable items (19/50), unshippable items recorded with explicit availability reason
- category discovery: 67 beauty categories registered with clean ancestor paths
- end-to-end `./repo run --node 11060451`: list → detail → SQLite/jsonl/csv → atomic run manifest
- daily Excel export verified (`artifacts/exports/xlsx/amazon_bs_20260825.xlsx`)
- local read API verified (`serve`: /health /categories /latest /history /stats)
- scheduler runner verified (`scripts/run_job.py --no-detail`, lockfile + log)
- parser regression tests: 5 passed

## Current blockers
- schedule activation and Drive upload await owner approval (per global policy §5.3)

## Capability and MCP status
- required external capabilities: none missing; curl_cffi installed to user site (PEP 668 --user)
- approved but not active: Drive service-account upload (`drive_upload.py` ready, needs GDRIVE_CREDS + folder id)
- active MCP dependencies: none

## Progress snapshot
- overall progress: 60%
- current confidence: high for single-panel collection; medium for multi-category scale-up pacing
- current stability: live-verified v0.1

## Next actions
1. owner decision: activate hourly systemd timer / cron for `run_job.py`
2. owner decision: create GCP service account, register GDRIVE_CREDS, wire Drive upload into run cycle
3. staged activation of remaining categories (batch dry-run then registry-approve)

## Reusable-pattern notes
- anti-bot ladder and transient-only retry follow `WH-CRAWL-FIXFIN-001`
- atomic run manifests follow `WH-RUNTIME-AGORA-001`
- category registry lifecycle follows `WH-CATALOG-MULTI-001`
