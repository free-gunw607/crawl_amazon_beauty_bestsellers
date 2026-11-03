# Italy Market Rollout

Status: isolated live-crawler validation passed; Beauty Index v32 is deployed. Google Sheet/Drive and scheduler rollout remains in progress.
Baseline: `.agent/baselines/pre_italy_20261103.md`.

## Compatibility contract

- Italy is Amazon.it Beauty root Top 100 only. Do not add Italian category crawls.
- Keep the spreadsheet ID and every existing tab name, sheet ID, column, and row protocol.
- Publish the Italy snapshot in `[IT] Top 100`; append its daily history only in `IT Rank History`.
- Keep Italy out of the analyst/macro-facing `root_rank_history`, `[ALL] Top 100`, and existing cross-market tabs during this trial.
- Keep all existing fallback XLSX tabs and their order/schema; append `IT Top 100` and `IT Rank History` after the legacy tabs.
- Add `markets.it` to the public feed only when the sheet has a complete 1–100 snapshot. Existing five markets remain independently publishable.
- A country failure must not erase or rewrite another country's daily snapshot/history.

## Rollout gates

1. Freeze the pre-change source, workbook metadata, fallback layout, and live site versions.
2. Add Italy marketplace metadata and thread it through root crawl, title repair, sheet publisher, watchdog/catch-up, fallback export, and public feed.
3. Run an Italy-only live collection. Require 100 unique ASINs and ranks 1–100 before writing the new sheet tabs.
4. Publish the two Italy tabs and verify sheet IDs/names, headers, all 100 rows, append-only history keys, and the five existing tabs' IDs/headers/stamps.
5. Regenerate the independent SQLite-backed XLSX and verify the old tab sequence is unchanged with only two appended Italy tabs.
6. Refresh the public JSON, require the five legacy markets and validate optional Italy data. Beauty Index v32 is already deployed and supports optional Italy data. v31 and v28 are saved rollback targets.
7. Enable Italy on the scheduled runner only after the live trial passes; verify the next scheduled run and the catch-up/watchdog path.

## Rollback

- Disable `it` in the marketplace registry/schedule selection and revert the Italy code commit.
- Restore the prior saved website version if the new UI/feed causes a rendering problem. Website rollback does not revert the Drive JSON or Google Sheet.
- Leave any Italy tabs and accumulated rows in place. Rollback never deletes history or alters the five legacy markets.
- The saved pre-change Git commit and Sites v31/v28 IDs are recorded in the baseline file. v32 source `cf9a34a4f8dd4b8cf01781f81a2eff86138ec10d`, saved version `appgprj_6ae534c42f588191b0f2a26e03185615~appgver_a9705bb7a320819194f97ca01e8b5741`, and deployment `appgdep_6ae9684119f881919f7d45469b33e176` are recorded in `BEAUTY_INDEX_VERSIONS.md`.

## Current implementation notes

- Canonical marketplace metadata is in `src/crawl_amazon_beauty_bestsellers/marketplaces.py`.
- Existing five-market aggregate tabs are pinned by `LEGACY_AGGREGATE_MARKETS`.
- Public dashboard reads Italy's dedicated history separately and treats its tabs/feed as optional until provisioned.
- The repository's `curl_cffi` collector successfully fetched Amazon.it Beauty page 1 and page 2 (HTTP 200 each); the production `Pipeline.crawl_list("it:ROOT")` was then run against temporary SQLite/snapshot paths and returned 100 rows, 100 unique ASINs, ranks 1–100, and passed the strict Italy gate. No production database was touched.
- One probe across two pages yielded only 98 distinct ASINs despite 100 ranks; a later diagnostic pair and three consecutive isolated production-pipeline runs each yielded 100 distinct ASINs. The underlying first-run overlap was not captured, so its exact cause is unproven. The collector now permits up to three complete two-page attempts; empty parses and explicit block signals stop rather than retrying aggressively. If all attempts remain incomplete, it raises a structured failure and does not persist the partial snapshot to SQLite.
- The clean production-pipeline probe parsed titles, ratings, and prices for 60/100 list positions. A product-detail page for one blank-title ASIN returned HTTP 200 and a usable Italian `#productTitle`. The existing title-recovery workflow can fill those gaps. Italian comma-decimal star ratings are now parsed in both list and product-detail parsers.
- Italy history title repair now fills only blank title cells when the existing date/ASIN/rank keys match SQLite; it does not reappend or rewrite history records. This ensures the later title-completion publish also repairs the dedicated `IT Rank History` tab.
- All 63 repository tests pass, including Italy retry/persistence guards; Python source compilation and `git diff --check` pass. The new watchdog test expects 17 tabs (the legacy 15 plus Italy's two). Sites v32 build and generated worker/browser-script validation passed and deployment succeeded at the existing canonical address. Live `/api/data` still returns the five current 100-row markets; Italy is absent until the Sheet tabs and snapshot are published. Google Sheets write, Drive update, scheduler activation, and crawler-repo Git push remain pending.
- A bare `curl -I` HEAD probe returned 503, but the actual crawler's GET requests returned 200. The HEAD result was therefore not evidence that Amazon.it Beauty Top 100 was unavailable.
