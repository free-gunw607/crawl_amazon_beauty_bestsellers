# Crawl Amazon Beauty Bestsellers

This repository is for Collect Amazon beauty bestseller lists and product detail vendor intelligence on an hourly schedule.

## Owner Front Door
- preferred owner goto command on bash / WSL: `./repo entry`
- preferred owner goto command on PowerShell: `\.\repo.ps1 entry`
- launcher-first usage is the default owner path

## Discoverability
- preferred owner launcher: `./repo ...` on bash/WSL and `\.\repo.ps1 ...` on PowerShell
- owner-facing front door: `ENTRY.md`
- file/module map: `CODEMAP.md`
- command examples: `COMMANDS.md`
- lightweight CLI discoverability commands should include: `entry`, `modes`, `examples`, `doctor`, `last-answer`

## Agent Runtime
- repo-local runtime workspace: `.agent/`
- approval policy: `.agent/approvals/POLICY.md`
- runtime overview: `.agent/README.md`
- durable handoff summary: `LAST_ANSWER.md`
- standard runtime commands should include: `agent-status`, `agent-log`, `agent-approvals`, `agent-bundle`, `agent-resume`, `agent-queue`

## Operating default
- proceed autonomously in normal repo-local work
- minimize interruptions
- prefer durable file-based handoff over frequent terminal progress summaries
- reserve approval requests for major scope, trust, authentication, remote-side-effect, privacy-sensitive, or destructive boundaries

## Current direction
- clarify the stable execution path
- prefer the simplest reliable implementation route
- keep repository-local execution reproducible and understandable
- keep durable handoff files current as work advances

## Beauty Index dashboard
- Run `python3 scripts/serve_dashboard.py --port 8781` to open the read-only dashboard at `http://127.0.0.1:8781`.
- The dashboard reads current regional Top 100 snapshots and the complete append-only `root_rank_history` tab from Google Sheets using a read-only scope (10-minute memory cache). SQLite supplies local brand enrichment and a fallback if Sheets is unavailable.
- It presents regional Top 100 rankings, brand-aware search and a brand directory, rank movements, daily snapshot selection, cross-market coverage, and per-ASIN rank history.
- The working-copy database may lag behind production. For current daily data, run the dashboard beside the active LIAM3 SQLite database. The server binds to localhost by default; remote access should stay on an authenticated private network.
- The public Beauty Index is deployed at https://liambeautyindex.dpdns.org. Its UI source is maintained in the connected Sites source repository (v10 commit `75a296d7a685d14b61aef26df3b5166c2a014aa9`); the daily pipeline updates its dedicated public JSON mirror without changing the macro workbook or fallback XLSX.

## Policy references
- global policy: `~/.codex/AGENTS.md`
- A2 guide: `~/agent-coding/agent-system/A2-workspace-memory/Guide.md`
- A2 structure: `~/agent-coding/agent-system/A2-workspace-memory/Structure.md`
- target OS baseline: `~/agent-coding/agent-system/A1-system-governance/docs/TARGET_OS/00_ENTRY.md`

## Workspace placement
- worker repo root: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- the repo may keep its own local operating rules, but new repos should anchor to the target-OS governance package
