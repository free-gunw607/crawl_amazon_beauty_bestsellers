# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers`
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- standardized project name: `crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon.com beauty-sector bestseller lists and product detail/vendor intelligence on an hourly schedule, accumulate time-series locally, publish Excel to Google Drive

## Current phase
v0.3 scheduled operations — 9 production panels; schedule registered (cron entries in place); two block events survived and recovered same-day

## Active production panels (9, all registry `production_approved`)
| node | panel | state |
|---|---|---|
| 11060451 | Skin Care | v0.1 verified baseline |
| 11060711 | Face | full cycle OK (75 details, BSR 73/75) |
| 11060521 | Body | full cycle OK (75 details, BSR 74/75) |
| 11061941 | Eyes | full cycle OK (75 details, BSR 75/75) |
| 11060661 | Moisturizers | full cycle OK (40 details, BSR 40/40) |
| 11062651 | Sunscreens | full cycle OK (44 details, BSR 43/44) |
| 11056291 | Body Washes | full cycle OK (75 details, BSR 75/75) |
| 7792528011 | Face Serums | RECOVERED after 2 block events: retry run 20260825_1133_6ccf68 → 46/50 details, BSR 46/46, USD+seller 21/46 |

## Schedule status (owner approved 2026-08-25)
- crontab REGISTERED: hourly list snapshots (`--no-detail`, xx:17) + detail/vendor pass every 6h (01/07/13/19 at :47), lockfile-protected
- ⚠ cron daemon NOT running in this WSL2 env; owner one-liner pending: `sudo service cron start`
- persistence hint for WSL reboots (owner optional): add `[boot] command=service cron start` to `/etc/wsl.conf` (needs sudo)
- systemd user units preserved under `deploy/systemd/` (+`scripts/install_schedule.sh`) for any future systemd-enabled environment
- volume design rationale: 9-panel full-detail hourly ≈ 1000 req/h invited both of today's blocks; bounded design = ~30 list requests/hour + ~500 detail requests every 6h

## Block event log (same day, both recovered)
1. 03:40 hard captcha/block on Serums detail fetch #2 → pipeline stopped immediately (policy verified in practice)
2. 10:19 soft block: 50/50 detail fetches returned HTTP 200 pages that parsed to zero fields → detected by quality summary, junk rows purged from DB, cooldown re-entered
3. Recovery proof: after ≥55min cooldown, single detached run parsed 46/50 with BSR 100% — cooldown works, keep using it

## Current blockers
1. cron daemon start requires owner sudo (one command)
2. Drive upload awaits owner-supplied GCP service-account JSON + folder id (CLI ready: `./repo upload-drive`)

## Recent completed work (2026-08-25 session 2, continued)
- owner approval captured for BOTH gates (schedule + Drive)
- `upload-drive` CLI subcommand added (clear error until GDRIVE_CREDS registered)
- deploy/systemd timer units + install script; adapted to WSL reality with crontab fallback
- COMMANDS.md: schedule commands + Drive registration steps documented
- A2 `Projects.md` milestone updated (7→9 panels, schedule state)
- serums double-block recovery cycle completed cleanly

## Capability and MCP status
- required external capabilities: none missing beyond owner-side credentials
- prepared but credential-gated: Drive service-account upload (`src/.../drive_upload.py` + CLI wired)
- active MCP dependencies: none

## Progress snapshot
- overall progress: 85% — collection, expansion, recovery, scheduling all proven; remaining items are owner-side credentials/commands
- current confidence: high for list cadence; medium-high for 6h detail cadence (soft-block telemetry now observable via `./repo health`)
- current stability: live data accumulating; automated firing pending cron daemon

## Next actions
1. owner: `sudo service cron start` (then verify `.agent/logs/cron_list.log` after next hour boundary)
2. owner: register GCP SA JSON → set `GDRIVE_CREDS` + `AMZ_BS_DRIVE_FOLDER_ID` → test `./repo upload-drive`
3. next category batch only after a few clean automated days (registry-first lifecycle unchanged)

## Reusable-pattern notes (Wisdomhouse candidates — recommended, not promoted)
- **Soft-block telemetry**: HTTP-200-with-empty-parse is a distinct block class; per-run field-completeness ratios (already in `health_checks`) are the detector. Evidence: run `20260825_1019_a54758` (50 empty parses, no captcha raise). Candidate path: `A2-workspace-memory/Wisdomhouse/by-repo/crawl_amazon_beauty_bestsellers.md` extension of `WH-CRAWL-FIXFIN-001`.
- **Detached long-crawl discipline**: host-tool timeouts kill foreground crawls mid-run and orphan `status:"running"` manifests; setsid-detach + manifest staleness marking avoids it. Evidence: orphaned `run_20260825_0946_b86943.json` marked failed retroactively.
