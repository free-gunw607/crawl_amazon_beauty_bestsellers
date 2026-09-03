from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any

from .config import load_settings
from .http_client import AmazonClient
from .pipeline import Pipeline
from .storage.xlsx_export import export_day


def _print(data: Any):
    print(json.dumps(data, ensure_ascii=False, default=str))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="crawl_amazon_beauty_bestsellers",
        description="Amazon beauty bestseller list + product/vendor intelligence collector",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("bootstrap-session", help="pin US delivery location and verify transport")
    p.add_argument("--zip", default=None)

    p = sub.add_parser("crawl-list", help="crawl one bestseller category list")
    p.add_argument("--node", required=True)
    p.add_argument("--pages", type=int, default=None)
    p.add_argument("--save-raw", action="store_true")
    p.add_argument("--list-type", default="bestsellers",
                   choices=["bestsellers", "new_releases", "movers_and_shakers", "most_wished_for"])
    p.add_argument("--root-dept", default=None, help="department slug when node not in registry (e.g. beauty, electronics)")

    p = sub.add_parser("crawl-detail", help="enrich ASINs of a category with product detail")
    p.add_argument("--node", required=True)
    p.add_argument("--top", type=int, default=None)
    p.add_argument("--save-raw", action="store_true")
    p.add_argument("--expand-variants", action="store_true")

    p = sub.add_parser("run", help="full cycle for one node or all approved nodes")
    p.add_argument("--node", default=None)
    p.add_argument("--active", action="store_true")
    p.add_argument("--no-detail", action="store_true")
    p.add_argument("--marketplace", default=None, help="filter active nodes by marketplace code (us/uk/de/fr/es)")
    p.add_argument("--list-type", default="bestsellers",
                   choices=["bestsellers", "new_releases", "movers_and_shakers", "most_wished_for"])

    p = sub.add_parser("discover-categories", help="discover bestseller category tree into registry")
    p.add_argument("--root", default="11060451")
    p.add_argument("--max-depth", type=int, default=2)
    p.add_argument("--root-dept", default=None)

    p = sub.add_parser("registry-list", help="show category registry")

    p = sub.add_parser("registry-approve", help="promote a category to production_approved")
    p.add_argument("--node", required=True)

    p = sub.add_parser("export-xlsx", help="export day workbook from accumulated data")
    p.add_argument("--date", default=None)

    p = sub.add_parser("upload-drive", help="upload a workbook (default: latest daily xlsx) to Google Drive")
    p.add_argument("--file", default=None)

    p = sub.add_parser("publish-sheets", help="publish tabs to the live Google Sheet")
    p.add_argument("--spreadsheet-id", default=None)
    p.add_argument("--tabs", choices=["ci", "local", "all"], default="all")
    p.add_argument("--date", default=None)
    p.add_argument("--backend", choices=["gws", "sa", "token"], default=None)

    p = sub.add_parser("publish-mr", help="publish multi-region tabs to the dedicated MR spreadsheet")
    p.add_argument("--region", required=True, help="marketplace code (us/uk/de/fr/es)")

    p = sub.add_parser("crawl-root", help="crawl the marketplace root Beauty & Personal Care list (1..100)")
    p.add_argument("--region", required=True)

    p = sub.add_parser("publish-root", help="publish region root Top100 into sheet 3 (beauty_personal_care_top100_live)")
    p.add_argument("--region", required=True)

    p = sub.add_parser("root-cycle", help="crawl-root then publish-root for one region")
    p.add_argument("--region", required=True)

    p = sub.add_parser("fill-gaps", help="retry detail fetch for ASINs with missing data")
    p.add_argument("--region", required=True, help="marketplace code (us/uk/de/fr/es) or 'all'")

    p = sub.add_parser("fill-titles", help="fetch titles only for ASINs with empty titles in ROOT snapshots")
    p.add_argument("--region", required=True, help="marketplace code (us/uk/de/fr/es) or 'all'")

    p = sub.add_parser("stats", help="database stats")

    p = sub.add_parser("health", help="parser field-completeness trend")
    p.add_argument("--limit", type=int, default=20)

    p = sub.add_parser("serve", help="local read API")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8790)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = load_settings()
    if getattr(args, "save_raw", False):
        settings.crawler.save_raw_html = True

    if args.command == "bootstrap-session":
        client = AmazonClient(settings)
        try:
            info = client.bootstrap_us_location()
            probe = client.get(f"{settings.amazon.base_url}/Best-Sellers/zgbs/beauty/11060451")
            usd = "$" in probe.text[:200000]
            _print({**info, "probe_http": probe.status_code, "usd_seen_on_probe": usd})
        finally:
            client.close()
        return 0

    pipeline = Pipeline(settings)
    try:
        if args.command == "crawl-list":
            entries = pipeline.crawl_list(args.node, pages=args.pages, list_type=args.list_type,
                                          root_slug=args.root_dept)
            summary = {
                "count": len(entries),
                "with_price": sum(1 for e in entries if e.price_amount is not None),
                "with_rating": sum(1 for e in entries if e.rating is not None),
                "warnings": sorted({w for e in entries for w in e.parse_warnings}),
                "top5": [
                    {"rank": e.rank, "asin": e.asin, "title": e.title[:60]}
                    for e in entries[:5]
                ],
            }
            _print(summary)
        elif args.command == "crawl-detail":
            entries = pipeline.crawl_list(args.node)
            ordered = [e.asin for e in sorted(entries, key=lambda x: x.rank)]
            if args.top:
                settings.crawler.detail_top = min(settings.crawler.detail_top, args.top)
            details, failures = pipeline.crawl_details(ordered, expand_variants=args.expand_variants)
            quality = {
                "details": len(details),
                "failures": len(failures),
                "usd_price": sum(1 for d in details if d.buy_box_currency == "USD"),
                "seller_found": sum(1 for d in details if d.seller_name),
                "bsr_found": sum(1 for d in details if d.bsr_main_rank is not None),
                "ingredients_found": sum(1 for d in details if d.ingredients),
                "manufacturer_found": sum(1 for d in details if d.manufacturer),
            }
            _print({"quality": quality, "failures": failures[:5]})
        elif args.command == "run":
            if args.active:
                nodes = [str(e["node_id"]) for e in pipeline.registry.active_nodes()]
                if args.marketplace:
                    mp = args.marketplace.lower()
                    if mp == "us":
                        nodes = [n for n in nodes if ":" not in n]
                    else:
                        nodes = [n for n in nodes if n.startswith(f"{mp}:")]
                if not nodes:
                    print("no production_approved categories; approve with registry-approve first")
                    return 2
            elif args.node:
                nodes = [args.node]
            else:
                print("specify --node <id> or --active")
                return 2
            results = []
            failed = 0
            for index, node_id in enumerate(nodes, start=1):
                print(f"[{index}/{len(nodes)}] node {node_id}")
                try:
                    results.append(pipeline.run_node(node_id, include_details=not args.no_detail,
                                                     list_type=args.list_type))
                except Exception as exc:
                    failed += 1
                    results.append({"node_id": node_id, "error": str(exc)})
            _print({"runs": results, "ok": len(nodes) - failed, "failed": failed})
            return 1 if failed else 0
        elif args.command == "discover-categories":
            found = pipeline.discover_categories(args.root, max_depth=args.max_depth, root_slug=args.root_dept)
            unique = {d["node_id"]: d for d in found}
            _print({
                "discovered_unique": len(unique),
                "registry_total": len(pipeline.registry.all_entries()),
            })
        elif args.command == "registry-list":
            _print(pipeline.registry.all_entries())
        elif args.command == "registry-approve":
            ok = pipeline.registry.approve(args.node)
            pipeline.registry.save()
            print("approved" if ok else "not found")
            return 0 if ok else 1
        elif args.command == "export-xlsx":
            name_map = {str(e.get("node_id")): e.get("name") or "" for e in pipeline.registry.all_entries()}
            date = args.date
            if not date and not pipeline.store.day_latest_rows(time.strftime("%Y-%m-%d")):
                date = pipeline.store.latest_data_day()
            path = export_day(settings, pipeline.store, date, name_map=name_map)
            print(str(path))
        elif args.command == "upload-drive":
            from pathlib import Path

            from .drive_upload import DriveUploadError, upload_file

            if args.file:
                target = Path(args.file)
            else:
                exports = sorted(Path("artifacts/exports/xlsx").glob("amazon_bs_*.xlsx"))
                if not exports:
                    print("no xlsx export found; run export-xlsx first")
                    return 2
                target = exports[-1]
            try:
                _print({"uploaded": str(target), **upload_file(target)})
            except DriveUploadError as exc:
                print(str(exc))
                return 3
        elif args.command == "publish-sheets":
            from .sheets_publish import DEFAULT_SPREADSHEET_ID, SheetsPublishError, build_tab_payloads, oauth_ready, publish

            spreadsheet_id = args.spreadsheet_id or os.environ.get("AMZ_BS_SHEETS_ID") or DEFAULT_SPREADSHEET_ID
            name_map = {str(e.get("node_id")): e.get("name") or "" for e in pipeline.registry.all_entries()}
            tabs = build_tab_payloads(pipeline.store, args.date, name_map, lanes=args.tabs)
            if not tabs:
                print("no data to publish for this date/lanes")
                return 2
            if args.backend:
                backend = args.backend
            elif os.environ.get("GDRIVE_CREDS"):
                backend = "sa"
            elif oauth_ready():
                backend = "token"
            else:
                backend = "gws"
            try:
                _print({"spreadsheet": spreadsheet_id, **publish(spreadsheet_id, tabs, backend)})
            except SheetsPublishError as exc:
                print(str(exc))
                return 3
        elif args.command == "publish-mr":
            from .mr_publish import SheetsPublishError, publish_region

            try:
                _print(publish_region(settings, pipeline.registry, pipeline.store, args.region.lower()))
            except SheetsPublishError as exc:
                print(str(exc))
                return 3
        elif args.command in ("crawl-root", "publish-root", "root-cycle"):
            from .http_client import CaptchaBlocked
            from .root_publish import SheetsPublishError, publish_root_region

            region = args.region.lower()
            key = "ROOT" if region == "us" else f"{region}:ROOT"
            try:
                if args.command in ("crawl-root", "root-cycle"):
                    try:
                        entries = pipeline.crawl_list(key)
                        _print({"region": region.upper(), "crawled": len(entries),
                                "ranks": [min(e.rank for e in entries), max(e.rank for e in entries)] if entries else []})
                    except CaptchaBlocked as exc:
                        _print({"region": region.upper(), "crawled": 0, "blocked": str(exc.url)})
                        if args.command == "root-cycle":
                            return 4
                if args.command in ("publish-root", "root-cycle"):
                    _print(publish_root_region(settings, pipeline.store, region))
            except SheetsPublishError as exc:
                print(str(exc))
                return 3
        elif args.command == "fill-gaps":
            from .http_client import CaptchaBlocked
            from .root_publish import publish_root_region

            regions = ["us", "uk", "de", "fr", "es"] if args.region.lower() == "all" else [args.region.lower()]
            for region in regions:
                key = "ROOT" if region == "us" else f"{region}:ROOT"
                # Phase 1: fill ASINs with no detail record at all
                missing = pipeline.store.missing_detail_asins(key)
                asins = [r["asin"] for r in missing]
                if asins:
                    _print({"region": region.upper(), "missing": len(asins)})
                    if region == "us":
                        # US: try amazon.com first
                        us_details, us_failures = [], []
                        try:
                            us_details, us_failures = pipeline.crawl_details(asins, marketplace="us")
                        except CaptchaBlocked:
                            pass
                    else:
                        # Non-US: use local marketplace directly (amazon.com captcha-blocks these)
                        try:
                            pipeline.crawl_details(asins, marketplace=region)
                        except CaptchaBlocked:
                            pass
                # Phase 2: re-fetch no-price ASINs
                # Step A: try US first (bootstrap works, USD prices)
                noprice = pipeline.store.noprice_detail_asins(key)
                noprice_asins = [r["asin"] for r in noprice]
                if noprice_asins:
                    _print({"region": region.upper(), "noprice_us": len(noprice_asins)})
                    for asin in noprice_asins:
                        pipeline.store._query("DELETE FROM product_details WHERE asin=?", (asin,))
                    us_details, us_failures = [], []
                    try:
                        us_details, us_failures = pipeline.crawl_details(noprice_asins, marketplace="us")
                    except CaptchaBlocked:
                        pass
                    # Collect ASINs that failed, got empty titles, or have no price on US
                    failed_asins = [f["asin"] for f in us_failures] if us_failures else []
                    for d in us_details:
                        if not d.title or not d.title.strip():
                            failed_asins.append(d.asin)
                        elif not d.buy_box_price and not d.list_price_amount:
                            failed_asins.append(d.asin)
                    # Step B: for failures, try local marketplace
                    if failed_asins and region != "us":
                        _print({"region": region.upper(), "noprice_local": len(failed_asins)})
                        try:
                            pipeline.crawl_details(failed_asins, marketplace=region)
                        except CaptchaBlocked:
                            pass
                if not asins and not noprice_asins:
                    _print({"region": region.upper(), "gaps": 0})
                try:
                    publish_root_region(settings, pipeline.store, region)
                except Exception:
                    pass
        elif args.command == "fill-titles":
            regions = ["us", "uk", "de", "fr", "es"] if args.region.lower() == "all" else [args.region.lower()]
            for region in regions:
                result = pipeline.fill_titles_only(region)
                _print(result)
        elif args.command == "stats":
            _print(pipeline.store.stats())
        elif args.command == "health":
            rows = pipeline.store.recent_health(args.limit)
            alerts = []
            for row in rows:
                for metric in ("price_ratio", "bsr_ratio", "rating_ratio", "title_ratio"):
                    value = row.get(metric)
                    if value is not None and value < 0.5:
                        alerts.append(f"{row['checked_at']} {row['node_id']}/{row['kind']} {metric}={value:.2f}")
            _print({"recent": rows, "alerts_below_0.5": alerts})
        elif args.command == "serve":
            from .server import serve

            serve(settings, host=args.host, port=args.port)
    finally:
        pipeline.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
