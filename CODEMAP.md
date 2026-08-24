# CODEMAP

## Core Entry Points
- `repo`: bash / WSL owner launcher and standard runtime command front door
- `repo.ps1`: PowerShell owner launcher and standard runtime command front door
- `ENTRY.md`: owner-facing front door
- `README.md`: high-level repository purpose and orientation
- `STATUS.md`: live situation board
- `src/crawl_amazon_beauty_bestsellers/cli.py`: CLI entrypoint (`./repo <command>` passthrough)
- `scripts/run_job.py`: lockfile-guarded scheduled job runner (hourly cycle)

## Source / Integration
- `src/crawl_amazon_beauty_bestsellers/http_client.py`: curl_cffi chrome-transport client, US delivery-location pinning, captcha fail-safe, politeness delays
- `src/crawl_amazon_beauty_bestsellers/parsers/bestseller_list.py`: bestseller grid parser (rank/asin/title/rating/reviews/price/offers)
- `src/crawl_amazon_beauty_bestsellers/parsers/product_detail.py`: product detail parser (brand/seller/buy-box/list price/BSR/specs/ingredients/variants)
- `src/crawl_amazon_beauty_bestsellers/parsers/category_tree.py`: sidebar category-tree discovery with ancestor-path reconstruction
- `src/crawl_amazon_beauty_bestsellers/pipeline.py`: run orchestration with atomic run manifests (`.agent/runs/run_*.json`)
- `src/crawl_amazon_beauty_bestsellers/registry.py`: category registry lifecycle (available/cataloged/accessible/production_approved/disabled)
- `src/crawl_amazon_beauty_bestsellers/config.py`: settings loading from `config/settings.yml`
- `src/crawl_amazon_beauty_bestsellers/models.py`: dataclasses (ListEntry, ProductDetail, CategoryNode)
- `src/crawl_amazon_beauty_bestsellers/server.py`: local read API (`./repo serve`)
- `src/crawl_amazon_beauty_bestsellers/drive_upload.py`: Google Drive upload via service account (approval-gated, not yet active)

## Validation / Export
- `src/crawl_amazon_beauty_bestsellers/storage/store.py`: SQLite accumulation + jsonl/csv snapshot writers
- `src/crawl_amazon_beauty_bestsellers/storage/xlsx_export.py`: daily Excel workbook builder (per-node sheets, details, 14-day trend)
- `tests/test_parsers.py`: fixture-backed parser regression tests

## Data Artifacts
- `artifacts/db/bestsellers.sqlite`: time-series accumulation DB
- `artifacts/snapshots/{node_id}/<stamp>/list.{jsonl,csv}`: per-run list snapshots
- `artifacts/details/*.jsonl`: per-run detail batches
- `artifacts/exports/xlsx/amazon_bs_YYYYMMDD.xlsx`: daily workbooks
- `artifacts/raw/`: optional debug HTML captures (gitignored)
- `config/category_registry.json`: discovered category registry
- `config/settings.yml`: runtime configuration

## Notes
- update this file whenever the repo gains a new major module or entrypoint
