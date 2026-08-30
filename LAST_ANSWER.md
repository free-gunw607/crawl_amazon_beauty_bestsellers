# LAST ANSWER

## Current state (2026-08-30)
- v0.9: **Sheet 3 live** with 5-region Beauty & Personal Care Top 100
- Sheet 3: https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit
- **bootstrap_us_location()** auto-pins delivery to NY 10001 on every new AmazonClient
- **Prices in USD** (currency_pref switched from KRW)
- **Final coverage**: Title 96%, URL 100%, **Price 84%**, Rating 96%

## Session summary (2026-08-30)
1. **R1-R4**: Full rank extraction (parse_recs_list), captcha recovery (break→continue), URL bug fix, list_price fallback, fill-gaps CLI
2. **R5**: USD price switch (KRW→USD), noprice detail_asins query, enrichment prefers records with prices
3. **R6**: bootstrap_us_location() auto-call in _client(), noprice 2-step fallback (US first → local), root_panel_grid enrichment priority fix

## Key discovery
The root cause of ~80 price-less ASINs was NOT "products unavailable on Amazon" — it was Amazon hiding `buy_box_price` because the session had no pinned delivery location, causing Amazon to geolocate the IP to Korea and hide prices for items it deemed "not shippable to Korea." The `bootstrap_us_location()` method existed but was never called automatically. Adding one line to `_client()` fixed US from 92→100/100.

## Remaining gaps (79 noprice)
Amazon's geo-detection still hides prices for ~16% of products even with NY delivery pin (Korean IP). Requires proxy/VPN to each target region for 100% coverage.

## Git commits
- `ede0103` R6: bootstrap auto-call + noprice fallback
- `b473def` R5: USD switch + enrichment priority
- prior: R1-R4 (rank extraction, captcha, URLs, fill-gaps)

## How to operate
- fill-gaps: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli fill-gaps --region all`
- publish: `PYTHONPATH=src python -m crawl_amazon_beauty_bestsellers.cli publish-root --region <mp>`
- run full stack: `./repo root-cycle --region <mp>` (list + publish + detail + sheet update)
- tests: `PYTHONPATH=src python -m pytest tests/ -q` (19/19 passing)

## Resume pointer
- everything durable in git + `.agent/`; restart-from-nothing = clone repo + read STATUS.md
