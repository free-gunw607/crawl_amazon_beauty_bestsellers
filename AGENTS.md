# Repo AGENTS

> Scope: repository-local rules  
> Global policy: `~/.codex/AGENTS.md`  
> Human master guide: `~/agent-coding/agent-system/A2-workspace-memory/Guide.md`  
> Structure reference: `~/agent-coding/agent-system/A2-workspace-memory/Structure.md`

## Repository
- current repo: `crawl_amazon_beauty_bestsellers`
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`
- standardized project name: `crawl_amazon_beauty_bestsellers`

## Objective
Collect Amazon beauty bestseller lists and product detail vendor intelligence on an hourly schedule

## Usage rules
1. Follow the global rules in `~/.codex/AGENTS.md`.
2. Read A2 workspace-memory docs when project-wide context, naming, workflow, status, or decision history is needed.
3. Keep this file focused on repository-specific rules only.
4. Update this file only when repository-local behavior changes.
5. If required capability is missing, identify the likely MCP or tool, explain why it is needed, and ask before installation or activation.
6. For new repos, treat `~/agent-coding/agent-system/A1-system-governance/docs/TARGET_OS/` as the target-OS governance baseline.
7. In owner-approved proactive mode, propose needed MCPs/tools/packages immediately and install right after explicit approval, then continue execution without delay.

## Repository-specific rules
- preferred approach:
  - direct HTTP collection with curl_cffi chrome-transport impersonation; browser automation only if a verified blocker appears
  - US delivery-location session pinning (settings `delivery_zip`) so price/seller data reflects the US marketplace
  - registry-first category expansion: new categories stay `available` until a live dry-run passes, then owner-visible `registry-approve`
- constraints:
  - politeness defaults are mandatory: randomized delays, transient-only retries, immediate stop on captcha/block detection, no retry storms
  - keep hourly request volume bounded: hourly cycles are list-only; full detail passes run every 6h; expand active categories gradually and observe block signals between batches
  - soft blocks (HTTP 200 with empty parses) count as block signals: purge junk rows, cooldown >=55min before retry
  - never commit secrets (`.env`, tokens, service-account JSON); Drive uploads use the workspace gws CLI OAuth by default (`drive_upload.py`), service-account env path remains optional
  - schedule activation (`run_job.py` timer) and any remote side effect require explicit owner approval
- local expectations:
  - keep repository-local execution reproducible
  - keep repository-local docs aligned with reality
  - keep `.agent/` readable for owners and useful for runtime handoff
  - keep `.agent/approvals/POLICY.md` aligned with actual approval behavior

## Reusable know-how discovery

- When work reveals a pattern that another A4 project could reuse, recommend a Wisdomhouse candidate to the owner in the handoff.
- Include the problem, generalized lesson, proposed `A2-workspace-memory/Wisdomhouse/` path, verification evidence, and reuse value. Do not force a theme during intake; use detailed rationale and optional keywords instead.
- Do not automatically promote secrets, credentials, raw customer data, or project-specific exports.
- Consult an existing Wisdomhouse entry before adopting a shared crawler or runtime pattern.
- After owner approval, update Wisdomhouse `CATALOG.md` and `by-repo/<repo_name>.md`, then link the promotion from the repo's `STATUS.md` and `LAST_ANSWER.md`. A `by-theme/<theme>/` document is added later when retrospective taxonomy review finds a stable recurring pattern.
- Assign stable Knowledge/Artifact IDs, preserve original filenames under `Wisdomhouse/artifacts/<knowledge_id>/`, and append new ledger rows in `Wisdomhouse_Master_Catalog.xlsx`. Record provenance, SHA-256, `Theme Status`, optional `Theme`, `Keywords`, `Know-how Rationale`, `Evidence`, and `Reuse Value`.
- Give every owner-approved promotion its own Knowledge ID; use Episode ID and Related Knowledge IDs only to connect entries from the same work episode.

## Key files
- `README.md`
- `ENTRY.md`
- `AGENTS.md`
- `STATUS.md`
- `.agent/README.md`
- `.agent/approvals/POLICY.md`

## Vault update triggers
Update the relevant A2 document when:
- project status changes
- a reusable workflow emerges
- a major architecture decision is made
- a new MCP or tool meaningfully changes the workflow

## MCP tracking
- Do not assume MCP installation is desired just because a capability is missing.
- If this repo adopts or depends on an MCP, update `~/agent-coding/agent-system/A2-workspace-memory/MCPs.md`.
- Update `STATUS.md` when MCP dependency or capability status changes.
- Update this file when MCP adoption changes repository-local behavior.
