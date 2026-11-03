# Italy Market Rollout

Status: complete and production-verified on 2026-11-03. Italy is live in Google Sheets, fallback XLSX, public feed, and Beauty Index v32; LIAM3 daily/catch-up/watchdog schedules are active.
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
- Production rollout on 2026-11-03 verified all six market tabs at 100/100; the fallback workbook has 19 tabs, with Italy's `IT Top 100` and `IT Rank History` appended after the 17 legacy tabs. The Italy history tab held 100 rows/100 unique keys. Drive XLSX upload used the service account and verified file ID, size, and MD5; public JSON includes Italy and 36,460 history rows. Hourly catch-up and watchdog both succeeded after switching the LIAM3 services to the isolated release worktree. Existing workbook tabs and the old dirty checkout were preserved.
- A subsequent public-feed audit found six blank titles in the latest Italy history cohort. `d002aec` extends repair to map the current Top 100 title by ASIN only for the latest history day, while preserving all existing nonblank cells and never applying today's title to older days. LIAM3 publish repaired 6 cells and appended 0 history rows. The public API now has 6 markets × 100 items, 100 Italy history rows today, and zero blank titles.
- The pre-repair XLSX had the same six blanks because it is generated independently from SQLite. `a5b2e99` applies the same-day-only fallback during workbook export. The rebuilt 19-tab XLSX has 100/100 Italy Top 100 rows and 100/100 today history rows, zero blank titles, and was uploaded to the existing Drive file ID `1-QYo4YEySvDAV5sx9fbtbuR1zTP0YujG`. The public JSON mirror file ID `1pAVxxxbr8x2S3eKVoPspCBnElwv69FtB` was refreshed at 14:52 KST.
- LIAM3 watchdog passed at 14:53 KST. Daily timer next runs 2026-11-04 05:00 KST; hourly catch-up and watchdog remain active. The site keeps its canonical address and v31 remains the immediate rollback for v32.
- All 68 repository tests pass, including Italy retry/persistence and fallback-title guards. The watchdog monitors 17 Google Sheet tabs (legacy 15 plus Italy's two). Sites v32 is deployed at the existing canonical URL, and live `/api/data` now returns six markets with 100 entries each. The sheet title repair, public JSON update, dated fallback XLSX regeneration/Drive update, LIAM3 scheduler activation, and Git pushes are complete.
- A bare `curl -I` HEAD probe returned 503, but the actual crawler's GET requests returned 200. The HEAD result was therefore not evidence that Amazon.it Beauty Top 100 was unavailable.
