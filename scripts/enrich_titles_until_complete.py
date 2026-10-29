from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET3_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
GWS_CONFIG_DIR = str(Path.home() / ".config" / "gws-amazon")
DEFAULT_REGIONS = ["us", "de", "uk", "fr", "es"]
DEFAULT_FALLBACK_MARKETS = ["de", "uk", "fr", "us", "es"]
REGIONS_ALL = ["us", "de", "uk", "fr", "es"]
TITLE_OVERRIDES_PATH = REPO_ROOT / "scripts" / "title_overrides.json"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("AMZ_BS_ROOT_BACKEND", "sa" if env.get("GDRIVE_CREDS") else "gws")
    env.setdefault("AMZ_BS_ROOT_SHEETS_ID", SHEET3_ID)
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", GWS_CONFIG_DIR)
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    return env


def _gws_values(range_name: str, env: dict[str, str]) -> list[list[str]]:
    if env.get("AMZ_BS_ROOT_BACKEND", "gws").lower() == "sa":
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from crawl_amazon_beauty_bestsellers.mr_publish import _api
        from crawl_amazon_beauty_bestsellers.root_publish import _service_account_access_token

        url_range = quote(range_name, safe="!:'")
        for attempt in range(6):
            try:
                payload = _api(
                    "GET",
                    f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET3_ID}/values/{url_range}",
                    _service_account_access_token(),
                )
                return payload.get("values", [])
            except Exception as exc:
                if not any(code in str(exc) for code in ("429", "500", "503", "504")) or attempt == 5:
                    raise
                time.sleep(min(60, 2 ** (attempt + 1)))

    proc = subprocess.run(
        [
            "gws",
            "sheets",
            "spreadsheets",
            "values",
            "get",
            "--params",
            json.dumps({"spreadsheetId": SHEET3_ID, "range": range_name}),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[-500:])
    stdout = proc.stdout
    payload = json.loads(stdout[stdout.index("{"):])
    return payload.get("values", [])


def _sheet_title_count(region: str, env: dict[str, str]) -> tuple[int, int, list[tuple[str, str]]]:
    # Row 4 is the table header; ranks 1..100 occupy rows 5..104.
    rows = _gws_values(f"[{region.upper()}] Top 100!A4:C104", env)
    total = 0
    titled = 0
    missing: list[tuple[str, str]] = []
    for row in rows:
        rank = row[0].strip() if row else ""
        asin = row[1].strip() if len(row) > 1 else ""
        if not asin or not rank.isdigit():
            continue
        total += 1
        title = row[2].strip() if len(row) > 2 else ""
        if title:
            titled += 1
        else:
            missing.append((rank, asin))
    return titled, total, missing


def _top100_title_map(env: dict[str, str]) -> dict[tuple[str, str], str]:
    titles: dict[tuple[str, str], str] = {}
    for region in REGIONS_ALL:
        rows = _gws_values(f"[{region.upper()}] Top 100!A4:C104", env)
        for row in rows:
            rank = row[0].strip() if row else ""
            asin = row[1].strip() if len(row) > 1 else ""
            title = row[2].strip() if len(row) > 2 else ""
            if rank.isdigit() and asin and title:
                titles[(region.upper(), asin)] = title
    return titles


def _db_title_map() -> dict[str, str]:
    db_path = REPO_ROOT / "artifacts" / "db" / "bestsellers.sqlite"
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT asin, title
            FROM (
                SELECT asin, title, fetched_at FROM product_details
                WHERE title IS NOT NULL AND TRIM(title) != ''
                UNION ALL
                SELECT asin, title, fetched_at FROM list_entries
                WHERE title IS NOT NULL AND TRIM(title) != ''
            )
            ORDER BY fetched_at DESC
            """
        ).fetchall()
    finally:
        conn.close()
    titles: dict[str, str] = {}
    for row in rows:
        asin = str(row["asin"] or "").strip()
        title = str(row["title"] or "").strip()
        if asin and title and asin not in titles:
            titles[asin] = title
    return titles


def _title_overrides() -> dict[str, str]:
    if not TITLE_OVERRIDES_PATH.exists():
        return {}
    try:
        data = json.loads(TITLE_OVERRIDES_PATH.read_text(encoding="utf-8"))
        return {str(key).lower(): str(value).strip() for key, value in data.items() if str(value).strip()}
    except (OSError, json.JSONDecodeError):
        return {}


def _batch_update_values(updates: list[dict[str, object]], env: dict[str, str], chunk_size: int = 200) -> None:
    if not updates:
        return
    if env.get("AMZ_BS_ROOT_BACKEND", "gws").lower() == "sa":
        sys.path.insert(0, str(REPO_ROOT / "src"))
        from crawl_amazon_beauty_bestsellers.mr_publish import _api
        from crawl_amazon_beauty_bestsellers.root_publish import _service_account_access_token

        endpoint = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET3_ID}/values:batchUpdate"
        for start in range(0, len(updates), chunk_size):
            body = {"valueInputOption": "USER_ENTERED", "data": updates[start:start + chunk_size]}
            for attempt in range(6):
                try:
                    _api("POST", endpoint, _service_account_access_token(), body=body)
                    break
                except Exception as exc:
                    if not any(code in str(exc) for code in ("429", "500", "503", "504")) or attempt == 5:
                        raise
                    time.sleep(min(60, 2 ** (attempt + 1)))
        return

    for start in range(0, len(updates), chunk_size):
        chunk = updates[start:start + chunk_size]
        proc = subprocess.run(
            [
                "gws",
                "sheets",
                "spreadsheets",
                "values",
                "batchUpdate",
                "--params",
                json.dumps({"spreadsheetId": SHEET3_ID}),
                "--json",
                json.dumps({"valueInputOption": "USER_ENTERED", "data": chunk}, ensure_ascii=False),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout).strip()[-800:])


def _backfill_root_rank_history(env: dict[str, str], dates: set[str] | None = None) -> dict[str, object]:
    rows = _gws_values("root_rank_history!A:I", env)
    titles = _top100_title_map(env)
    db_titles = _db_title_map()
    updates: list[dict[str, object]] = []
    missing_before = 0
    date_counts: dict[str, dict[str, int]] = {}

    for row_num, row in enumerate(rows, start=1):
        if len(row) < 4:
            continue
        day = row[0].strip()
        if dates and day not in dates:
            continue
        region = row[1].strip() if len(row) > 1 else ""
        asin = row[2].strip() if len(row) > 2 else ""
        title = row[8].strip() if len(row) > 8 else ""
        if not day or not region or not asin or title:
            continue
        missing_before += 1
        counters = date_counts.setdefault(day, {"missing": 0, "updated": 0})
        counters["missing"] += 1
        found = titles.get((region, asin)) or db_titles.get(asin)
        if found:
            updates.append({"range": f"'root_rank_history'!I{row_num}", "values": [[found[:140]]]})
            counters["updated"] += 1

    _batch_update_values(updates, env)

    rows_after = _gws_values("root_rank_history!A:I", env)
    remaining = 0
    for row in rows_after:
        if len(row) < 4:
            continue
        day = row[0].strip()
        if dates and day not in dates:
            continue
        title = row[8].strip() if len(row) > 8 else ""
        if not title:
            remaining += 1
    return {
        "missing_before": missing_before,
        "updated": len(updates),
        "remaining_after": remaining,
        "by_date": date_counts,
    }


def _fallback_marketplace_titles(
    region: str,
    missing: Iterable[tuple[str, str]],
    markets: list[str],
    max_items: int,
) -> int:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from bs4 import BeautifulSoup
    from crawl_amazon_beauty_bestsellers.config import load_settings
    from crawl_amazon_beauty_bestsellers.http_client import AmazonClient, CaptchaBlocked
    from crawl_amazon_beauty_bestsellers.root_publish import publish_root_region
    from crawl_amazon_beauty_bestsellers.storage.store import Store

    # Honor the scheduler's configured backend so service-account publishing
    # remains available during a human OAuth outage.
    if not os.environ.get("AMZ_BS_ROOT_BACKEND"):
        os.environ["AMZ_BS_ROOT_BACKEND"] = "sa" if os.environ.get("GDRIVE_CREDS") else "gws"
    os.environ.setdefault("AMZ_BS_ROOT_SHEETS_ID", SHEET3_ID)
    settings = load_settings(REPO_ROOT)
    store = Store(settings)
    node = "ROOT" if region == "us" else f"{region}:ROOT"
    filled = 0
    clients: dict[str, AmazonClient] = {}
    ordered_markets = list(dict.fromkeys([region, *markets]))
    overrides = _title_overrides()
    db_titles = _db_title_map()

    missing_rows = list(missing)[:max_items]
    publish_needed = False
    try:
        for _rank, asin in missing_rows:
            title = (
                overrides.get(f"{region}:{asin}".lower(), "")
                or overrides.get(asin.lower(), "")
                or db_titles.get(asin, "")
            )
            source = "override" if title and (overrides.get(f"{region}:{asin}".lower()) or overrides.get(asin.lower())) else "local_db" if title else ""
            for market in ordered_markets if not title else []:
                profile = settings.marketplace(market)
                if profile is None:
                    continue
                client = clients.get(market)
                if client is None:
                    client = AmazonClient(settings, marketplace=profile)
                    clients[market] = client
                    try:
                        client.bootstrap_us_location()
                    except CaptchaBlocked:
                        raise
                    except Exception:
                        pass
                try:
                    response = client.get(f"{profile.base_url}/dp/{asin}")
                    soup = BeautifulSoup(response.text, "html.parser")
                    title_el = soup.select_one("#productTitle")
                    title = (title_el.get_text(" ", strip=True) if title_el else "").strip()
                    if not title:
                        meta = soup.select_one('meta[property="og:title"], meta[name="title"]')
                        title = str(meta.get("content", "")).strip() if meta else ""
                    if title:
                        source = market
                        break
                except CaptchaBlocked:
                    raise
                except Exception:
                    continue
            if title and store.update_title(asin, node, title):
                filled += 1
                publish_needed = True
                print(
                    json.dumps(
                        {"region": region.upper(), "asin": asin, "fallback_market": source, "title": title[:120]},
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
        # A previous attempt can write locally then fail during publish; the
        # local DB title map above will rediscover it and trigger this publish.
        if publish_needed:
            print(publish_root_region(settings, store, region), flush=True)
        return filled
    finally:
        for client in clients.values():
            client.close()
        store.close()


def _recover_region_titles(
    region: str,
    *,
    max_rounds: int,
    sleep_sec: int,
    max_sleep_sec: int,
    markets: list[str],
    env: dict[str, str],
) -> dict[str, object]:
    """Retry only current live-sheet title gaps and verify after every publish."""
    from crawl_amazon_beauty_bestsellers.http_client import CaptchaBlocked

    titled, total, missing = _sheet_title_count(region, env)
    rounds: list[dict[str, object]] = []
    blocked = ""
    for round_no in range(1, max_rounds + 1):
        if total >= 100 and not missing:
            break
        before = len(missing)
        # Rotate fallback-market priority between rounds while keeping the
        # product's own marketplace first inside _fallback_marketplace_titles.
        if markets:
            offset = (round_no - 1) % len(markets)
            round_markets = markets[offset:] + markets[:offset]
        else:
            round_markets = []
        try:
            filled = _fallback_marketplace_titles(region, missing, round_markets, max_items=len(missing))
        except CaptchaBlocked as exc:
            blocked = str(exc)
            rounds.append({"round": round_no, "before_missing": before, "blocked": blocked})
            break
        titled, total, missing = _sheet_title_count(region, env)
        rounds.append({
            "round": round_no,
            "before_missing": before,
            "filled_local": filled,
            "after_missing": len(missing),
        })
        print(json.dumps({"region": region.upper(), "event": "title_recovery_round", **rounds[-1]}, ensure_ascii=False), flush=True)
        if total >= 100 and not missing:
            break
        if round_no < max_rounds and sleep_sec > 0:
            delay = min(max_sleep_sec, sleep_sec * (2 ** (round_no - 1)))
            print(json.dumps({"region": region.upper(), "event": "retry_cooldown", "seconds": delay}, ensure_ascii=False), flush=True)
            time.sleep(delay)
    return {
        "region": region.upper(),
        "titled": titled,
        "total": total,
        "missing": len(missing),
        "missing_asins": missing,
        "rounds": rounds,
        "blocked": blocked,
        "complete": total >= 100 and not missing,
    }


def _notify(summary: str) -> None:
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from run_job import _send_email, _send_telegram

        _send_telegram(summary)
        _send_email(
            f"[Amazon Beauty] title enrichment {time.strftime('%Y-%m-%d %H:%M KST')}",
            summary,
        )
    except Exception as exc:
        print(f"[notify] skipped: {exc}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--regions", nargs="+", default=DEFAULT_REGIONS)
    # Every recovery round works from the exact current live-sheet blanks.
    parser.add_argument("--max-rounds", type=int, default=4, help="bounded recovery rounds per region; later catchups resume remaining gaps")
    parser.add_argument("--sleep-sec", type=int, default=20)
    parser.add_argument("--max-sleep-sec", type=int, default=300)
    parser.add_argument("--target", type=int, default=100)
    parser.add_argument("--alert", action="store_true")
    parser.add_argument("--fallback", action="store_true", default=True)
    parser.add_argument("--no-fallback", dest="fallback", action="store_false")
    parser.add_argument("--fallback-marketplaces", nargs="+", default=DEFAULT_FALLBACK_MARKETS)
    parser.add_argument("--backfill-history", action="store_true", default=True)
    parser.add_argument("--no-backfill-history", dest="backfill_history", action="store_false")
    parser.add_argument("--history-date", action="append", default=None, help="limit root_rank_history backfill to this date; may repeat")
    parser.add_argument("--summary-json", type=Path, help="Write final title/history results for an enclosing report.")
    args = parser.parse_args()

    env = _env()
    results: list[str] = []
    summary_regions: list[dict[str, object]] = []
    history_result: dict[str, object] | None = None
    print(
        json.dumps(
            {
                "event": "title_enrichment_start",
                "regions": args.regions,
                "max_rounds": args.max_rounds,
                "target": args.target,
            },
            ensure_ascii=False,
        ),
        flush=True,
    )

    all_complete = True
    block_seen = False
    for region in [r.lower() for r in args.regions]:
        if args.fallback and not block_seen:
            result = _recover_region_titles(
                region,
                max_rounds=max(1, args.max_rounds),
                sleep_sec=args.sleep_sec,
                max_sleep_sec=args.max_sleep_sec,
                markets=list(args.fallback_marketplaces),
                env=env,
            )
        else:
            titled, total, missing = _sheet_title_count(region, env)
            result = {"region": region.upper(), "titled": titled, "total": total, "missing": len(missing), "missing_asins": missing, "rounds": [], "blocked": ""}
        complete = int(result["total"]) >= args.target and int(result["missing"]) == 0
        all_complete = all_complete and complete
        result["complete"] = complete
        summary_regions.append(result)
        results.append(f"{region.upper()}: {result['titled']}/{result['total']} titles, missing={result['missing']}")
        if result.get("blocked"):
            block_seen = True
            results.append(f"  stopped on Amazon block signal: {result['blocked']}")
        elif block_seen and args.fallback:
            results.append("  network recovery skipped after an earlier marketplace block signal")

    if args.backfill_history:
        history_dates = set(args.history_date) if args.history_date else None
        history_result = _backfill_root_rank_history(env, dates=history_dates)
        print(json.dumps({"event": "root_rank_history_backfill", **history_result}, ensure_ascii=False), flush=True)
        results.append(
            "root_rank_history backfill: "
            f"updated={history_result['updated']}, remaining={history_result['remaining_after']}"
        )

    summary = "\n".join(["Amazon Beauty title enrichment", *results, f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET3_ID}/edit"])
    print(summary, flush=True)
    if args.summary_json:
        args.summary_json.parent.mkdir(parents=True, exist_ok=True)
        args.summary_json.write_text(
            json.dumps({"regions": summary_regions, "history": history_result}, ensure_ascii=False),
            encoding="utf-8",
        )
    if args.alert:
        _notify(summary)
    return 0 if all_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
