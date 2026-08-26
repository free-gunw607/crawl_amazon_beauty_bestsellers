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
    print(json.dumps(data, ensure_ascii=False, indent=2, default=str))


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
