# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers`
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- standardized project name: `crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon.com beauty-sector bestseller lists and product detail/vendor intelligence on an hourly schedule, accumulate time-series locally, publish Excel to Google Drive

## Current phase
v0.3 scheduled operations LIVE — 8 production panels; interim scheduler daemon active; Drive publishing verified via gws OAuth

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

## Schedule status (owner approved 2026-08-25; both paths live)
- **ACTIVE NOW**: `scripts/scheduler_loop.py` interim daemon (privilege-free, setsid-detached) — fires hourly list job at :17 and detail/vendor pass 01/07/13/19 at :47, same cadence as crontab, lockfile + per-hour markers
- crontab entries also REGISTERED (identical cadence) — they take over automatically once cron daemon runs
- cron daemon itself needs root in WSL2 (`sudo service cron start`); until then the loop covers automation
- systemd user units preserved under `deploy/systemd/` for future systemd-enabled environments
- volume design rationale: 8-panel full-detail hourly ≈ 1000 req/h invited both of today's blocks; bounded design = ~24 list requests/hour + ~500 detail requests every 6h

## Drive status (owner approved 2026-08-25 — SOLVED)
- **WORKING**: `./repo upload-drive` uploads the latest daily workbook via workspace `gws` CLI OAuth — no service account needed
- Drive folder `crawl_amazon_beauty_bestsellers` created: id `1xns4GiMLt1ZPa8me9At4IpgWDyB-SOgp`
- first upload verified: `amazon_bs_20260825.xlsx` → https://drive.google.com/file/d/11qQcoXJc5cisiTug7a_HIY3res7G3UUi/view
- service-account env path (`GDRIVE_CREDS`) remains supported as an alternative, not required

## Block event log (same day, both recovered)
1. 03:40 hard captcha/block on Serums detail fetch #2 → pipeline stopped immediately (policy verified in practice)
2. 10:19 soft block: 50/50 detail fetches returned HTTP 200 pages that parsed to zero fields → detected by quality summary, junk rows purged from DB, cooldown re-entered
3. Recovery proof: after ≥55min cooldown, single detached run parsed 46/50 with BSR 100% — cooldown works, keep using it

## Current blockers
- none mandatory; optional owner improvements only:
  - `sudo service cron start` (crontab then replaces the interim loop naturally)
  - optional `/etc/wsl.conf` boot command for cron persistence across WSL restarts
  - scheduler_loop.py dies if the WSL VM itself is shut down — restart it or enable cron after reboot

## Recent completed work (2026-08-25 session 2, continued)
- owner approval captured for BOTH gates (schedule + Drive) — both then solved end-to-end
- Drive: gws OAuth fallback implemented in `drive_upload.py`; folder created; first upload verified via `./repo upload-drive`
- schedule: privilege-free `scheduler_loop.py` interim daemon launched and verified alive
- COMMANDS.md + AGENTS.md updated to match new Drive/schedule reality
- A2 `Projects.md` milestone updated

## Capability and MCP status
- required external capabilities: none missing beyond owner-side credentials
- prepared but credential-gated: Drive service-account upload (`src/.../drive_upload.py` + CLI wired)
- active MCP dependencies: none

## Progress snapshot
- overall progress: 95% — collection, expansion, recovery, scheduling, Drive publishing all live
- current confidence: high for list cadence; medium-high for 6h detail cadence (soft-block telemetry observable via `./repo health`)
- current stability: automated cycles running via interim loop; data accumulating

## Next actions
1. verify first automated list cycle fired at 20:17 (`.agent/logs/scheduler_loop.log` + DB row growth)
2. optional owner: `sudo service cron start` for reboot-durable scheduling
3. next category batch only after a few clean automated days (registry-first lifecycle unchanged)

## Reusable-pattern notes (Wisdomhouse candidates — recommended, not promoted)
- **Soft-block telemetry**: HTTP-200-with-empty-parse is a distinct block class; per-run field-completeness ratios (already in `health_checks`) are the detector. Evidence: run `20260825_1019_a54758` (50 empty parses, no captcha raise). Candidate path: `A2-workspace-memory/Wisdomhouse/by-repo/crawl_amazon_beauty_bestsellers.md` extension of `WH-CRAWL-FIXFIN-001`.
- **Detached long-crawl discipline**: host-tool timeouts kill foreground crawls mid-run and orphan `status:"running"` manifests; setsid-detach + manifest staleness marking avoids it. Evidence: orphaned `run_20260825_0946_b86943.json` marked failed retroactively.
