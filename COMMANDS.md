# COMMANDS

## Quick Start
```bash
cd ~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers
./repo entry
./repo doctor
./repo agent-status
./repo last-answer
```

## Discoverability Commands
`entry`
Show the owner-facing front door.

`modes`
Show the main launch/use-case modes.

`examples`
Show the copy-paste command catalog.

`doctor`
Run lightweight discoverability checks.

`last-answer`
Show the current durable handoff summary.

## Runtime Commands
`agent-status`
Show the standard `.agent` runtime summary.

`agent-log`
Inspect the latest runtime log or show the log directory.

`agent-approvals`
Show the default approval policy and any saved approval artifacts.

`agent-bundle`
Inspect the issue-bundle directory and related bundle guidance.

`agent-resume`
Show resumable run guidance and the latest run artifacts if present.

`agent-queue`
Inspect queued work items and queue guidance.

`node-status`
Show execution lease, auth-family lease, and write-session state.

`preflight`
Check repo identity, required B3 files, and runtime readiness.

`compliance`
Refresh and display `.agent/state/compliance_state.json`.

`claim-node --node-id <id>`
Claim the active execution node lease for this repo.

`claim-write-session --path <path>`
Claim active write ownership for the intended repo paths.

`create-manifest --target-repo <repo> --path <path>`
Create a durable mutation manifest before approved inter-repo mutation.

`snapshot-repo --reason "..."`
Create a repo snapshot and register it in the workspace ledger.

`publish-repo-snapshot --drive-folder-id <id>`
Upload a repo snapshot to Google Drive via `gws`, update registry metadata, and emit a Slack receipt payload.

## Launcher
- preferred owner path on bash / WSL: `./repo ...`
- preferred owner path on PowerShell: `\.\repo.ps1 ...`
- raw Python module invocation is the lower-level contributor path

## Project Commands (crawl_amazon_beauty_bestsellers)
`bootstrap-session`
Pin the US delivery location (ZIP from settings) and verify the transport; prints USD probe result.

`crawl-list --node <id> [--pages N]`
Crawl one bestseller category list into SQLite + jsonl/csv snapshots.

`crawl-detail --node <id> [--top N]`
Enrich the category's ranked ASINs with product/vendor details.

`run --node <id> | --active [--no-detail]`
Full cycle for one node or all `production_approved` registry nodes: list → detail → storage → manifest.

`discover-categories --root <id> [--max-depth N]`
Walk the bestseller sidebar tree and register categories as `available`.

`registry-list` / `registry-approve --node <id>`
Show the registry / promote a verified category to production.

`export-xlsx [--date YYYY-MM-DD]`
Build the daily Excel workbook (per-node sheets, details, 14-day trend).

`serve [--port 8790]`
Local read API: `/health`, `/categories`, `/latest/{node_id}`, `/history?asin=`, `/stats`.

`stats`
Database accumulation summary.

## Examples
- `./repo bootstrap-session`
- `./repo crawl-list --node 11060451`
- `./repo run --node 11060451`
- `./repo discover-categories --root 11060451 --max-depth 2`
- `./repo registry-approve --node 11060521`
- `./repo export-xlsx`
- `./repo serve --port 8790`
- `PYTHONPATH=src python3 scripts/run_job.py`  # hourly scheduler entry
- add further workflow examples here as the repo matures

## Notes
- prefer use-case examples over raw subcommand lists
- use `LAST_ANSWER.md` and `.agent/` runtime files as the default progress trail
- schedule activation and Drive upload are owner approval gates per global policy §5.3
