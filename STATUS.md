# STATUS

## Repository
- repo: `crawl_amazon_beauty_bestsellers` — **PUBLIC**: https://github.com/free-gunw607/crawl_amazon_beauty_bestsellers
- workspace path: `~/agent-coding/agent-projects/A4-worker-repos/crawl_amazon_beauty_bestsellers`

## Current objective
Collect Amazon Beauty & Personal Care Top 100 across 5 regions (US/DE/UK/FR/ES) with 100% title coverage, publish to Google Sheet 3 only. Run daily at 5AM KST via systemd timer. Telegram briefing after each run.

## Live Google Sheet (Sheet 3 — PRIMARY)
https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- Tab: `beauty_personal_care_top100_live`
- **Sheet 1 ABANDONED** — all effort focused on Sheet 3

## Current phase
v1.1 ROOT-CYCLE PIPELINE (2026-09-03)
- **Pipeline**: `run_job.py` runs root-cycle (5 regions) + fill-titles per region
- **Title 100%** all 5 regions (US/DE/UK/FR/ES) — achieved via fill-titles feature
- **Total time**: ~7 min full pipeline
- **systemd timer**: daily 5AM KST (UTC 20:00), single service unit
- **Telegram report**: detailed Korean briefing with per-region breakdown

## Pipeline workflow
1. `root-cycle --region <mp|all>` — fetch TOP 100 from root bestseller page
2. `fill-titles --region <mp>` — lightweight title-only fetch for ASINs with empty titles
3. Publish to Sheet 3 via `publish-root --region <mp>`
4. Telegram report sent automatically

## Scheduler
- **1 timer**: `amzbs-beauty.timer` — daily 5AM KST (UTC 20:00)
- **1 service**: `amzbs-beauty.service` — runs `run_job.py` then sends Telegram report
- **Install**: `systemctl --user daemon-reload && systemctl --user enable --now amzbs-beauty.timer`
- **Check**: `systemctl --user status amzbs-beauty.timer`

## Data quality
| Region | Title | Rating | Price | Status |
|--------|-------|--------|-------|--------|
| US | 100% | 100% | ~93% | ✅ |
| DE | 100% | 100% | ~97% | ✅ |
| UK | 100% | 100% | ~99% | ✅ |
| FR | 100% | 100% | ~89% | ✅ |
| ES | 100% | 100% | ~80% | ✅ |

- **Price gaps**: geo-restriction on Korean IP (requires proxy/VPN for 100%)
- **All prices USD** (currency_pref switched KRW→USD)

## Key files
- `scripts/run_job.py` — main orchestrator (root-cycle5 regions + fill-titles)
- `src/crawl_amazon_beauty_bestsellers/cli.py` — CLI commands (root-cycle, fill-titles, publish-root)
- `src/crawl_amazon_beauty_bestsellers/pipeline.py` — pipeline logic including `fill_titles_only()`
- `src/crawl_amazon_beauty_bestsellers/storage/store.py` — SQLite storage with `update_title()`
- `src/crawl_amazon_beauty_bestsellers/root_publish.py` — Sheet3 publisher
- `~/.config/systemd/user/amzbs-beauty.service` — systemd service
- `~/.config/systemd/user/amzbs-beauty.timer` — systemd timer

## Git history
- `26c10d3` Sheet3 전용 파이프라인: root-cycle + fill-titles, 텔레그램 리포트 JSON 파싱 버그 수정
- `f818a4f` improve Telegram briefing: detailed Korean report with per-region breakdown
- `dda5d09` fix Telegram briefing: parse JSON output, region-aggregated report

## Pending items
1. Verify tomorrow's 5AM KST timer run
2. Optional: `fill-titles --region all` timeout issue (individual regions work fine)
3. Optional: clean up `category_registry.json` (23 non-ROOT nodes no longer used)
