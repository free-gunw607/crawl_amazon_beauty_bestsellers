#!/usr/bin/env python3
"""Publish a validated, public-safe snapshot to the standalone Beauty Index Site."""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
from crawl_amazon_beauty_bestsellers.marketplaces import MARKETPLACE_CODES, MARKETPLACE_META

CONFIG_FILE = Path.home() / ".config" / "amzbs" / "beauty-index.env"
DRIVE_FILE_ID_PATH = Path.home() / ".config" / "amzbs" / "beauty-index-drive-id"
REGIONS = MARKETPLACE_CODES
REQUIRED_REGIONS = ("us", "uk", "de", "fr", "es")


def _settings() -> dict[str, str]:
    values = dict(os.environ)
    if CONFIG_FILE.is_file():
        for raw in CONFIG_FILE.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values.setdefault(key.strip(), value.strip().strip("\"'"))
    return values


def _dashboard_data():
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from serve_dashboard import DashboardData

    db_path = Path(os.environ.get("AMZ_BS_DB_PATH", REPO_ROOT / "artifacts/db/bestsellers.sqlite"))
    data = DashboardData(db_path)
    history = data.sheet_history()
    if data._sheet_error:
        raise RuntimeError("Google Sheets read failed; keeping the last public snapshot unchanged.")
    if not history:
        raise RuntimeError("Google Sheets history is empty; refusing to publish an empty public archive.")

    markets = {}
    all_asins = {row["asin"] for row in history}
    for region in REQUIRED_REGIONS:
        snapshot = data._sheet_snapshots.get(region)
        if not snapshot:
            raise RuntimeError(f"Missing Google Sheet snapshot for {region.upper()}.")
        entries = snapshot["entries"]
        ranks = {entry["rank"] for entry in entries}
        asins = {entry["asin"] for entry in entries}
        if len(entries) != 100 or ranks != set(range(1, 101)) or len(asins) != 100:
            raise RuntimeError(f"Refusing incomplete {region.upper()} snapshot ({len(entries)}/100 rows).")
        all_asins.update(asins)
        markets[region] = {
            "name": MARKETPLACE_META[region]["name"],
            "flag": MARKETPLACE_META[region]["flag"],
            "display_order": MARKETPLACE_META[region]["display_order"],
            "day": snapshot["day"],
            "stamp": snapshot["stamp"],
            "entries": entries,
        }

    # New markets are opt-in by data presence: a failed first Italy run cannot
    # block or replace the five established markets' public update.
    for region in (code for code in REGIONS if code not in REQUIRED_REGIONS):
        snapshot = data._sheet_snapshots.get(region)
        if not snapshot:
            continue
        entries = snapshot["entries"]
        if len(entries) != 100 or {entry["rank"] for entry in entries} != set(range(1, 101)) or len({entry["asin"] for entry in entries}) != 100:
            continue
        all_asins.update(entry["asin"] for entry in entries)
        markets[region] = {
            "name": MARKETPLACE_META[region]["name"],
            "flag": MARKETPLACE_META[region]["flag"],
            "display_order": MARKETPLACE_META[region]["display_order"],
            "day": snapshot["day"], "stamp": snapshot["stamp"], "entries": entries,
        }

    # Keep product metadata separate and keyed by ASIN. This does not change the
    # macro-facing Google workbook or fallback XLSX layout.
    product_rows = [{"asin": asin, "brand": "", "image_url": "", "image_urls": []} for asin in sorted(all_asins)]
    for offset in range(0, len(product_rows), 350):
        batch = product_rows[offset:offset + 350]
        data._enrich_brands(batch)
        data._enrich_images(batch)
        data._enrich_image_candidates(batch)
    products = {
        row["asin"]: {"brand": row.get("brand", ""), "image_url": row.get("image_url", ""),
                      "image_urls": row.get("image_urls", [])}
        for row in product_rows
    }
    normalized_history = []
    for row in history:
        normalized_history.append({
            "day": row["day"], "region": row["region"], "asin": row["asin"],
            "rank": row["rank"], "title": row["title"],
            "price_amount": row["price_amount"], "price_currency": row["price_currency"],
            "rating": row["rating"], "ratings_count": row["ratings_count"],
        })
    now = datetime.now(timezone(timedelta(hours=9))).isoformat(timespec="seconds")
    return {
        "schema_version": 1,
        "generated_at": now,
        "source": "Google Sheets public ranking snapshot",
        "history": normalized_history,
        "products": products,
        "markets": markets,
    }


def _publish_drive_snapshot(payload: dict, path: Path, settings: dict[str, str], *, if_stale: bool = False) -> dict:
    """Update one dedicated public JSON file; never touches the macro workbook."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    credentials_path = settings.get("GDRIVE_CREDS", "").strip()
    if not credentials_path or not Path(credentials_path).is_file():
        raise RuntimeError("GDRIVE_CREDS service-account file is required for Drive JSON publishing")
    creds = service_account.Credentials.from_service_account_file(
        credentials_path, scopes=["https://www.googleapis.com/auth/drive"]
    )
    service = build("drive", "v3", credentials=creds, cache_discovery=False)
    file_id = DRIVE_FILE_ID_PATH.read_text(encoding="utf-8").strip() if DRIVE_FILE_ID_PATH.is_file() else ""
    if not file_id:
        raise RuntimeError("Dedicated public Drive mirror ID is not provisioned; refusing to create a file under the service account quota")
    media = MediaFileUpload(str(path), mimetype="application/json", resumable=True)
    stamp_map = {region: value["stamp"] for region, value in payload["markets"].items()}
    marker = "beauty-index-stamps:" + json.dumps(stamp_map, sort_keys=True, separators=(",", ":"))
    if file_id and if_stale:
        current = service.files().get(fileId=file_id, supportsAllDrives=True, fields="description,modifiedTime,size").execute()
        if marker in str(current.get("description", "")):
            return {"file_id": file_id, "url": f"https://drive.google.com/uc?export=download&id={file_id}",
                    "size": current.get("size"), "modified_time": current.get("modifiedTime"), "status": "current"}
    if file_id:
        service.files().update(fileId=file_id, body={"description": marker}, media_body=media,
                               fields="id,name,mimeType,size,modifiedTime,webViewLink", supportsAllDrives=True).execute()
    if not file_id:
        raise RuntimeError("Drive snapshot upload returned no file ID")
    DRIVE_FILE_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
    DRIVE_FILE_ID_PATH.write_text(file_id + "\n", encoding="utf-8")
    DRIVE_FILE_ID_PATH.chmod(0o600)
    permissions = service.permissions().list(fileId=file_id, supportsAllDrives=True, fields="permissions(id,type,role)").execute().get("permissions", [])
    if not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in permissions):
        service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}, supportsAllDrives=True, fields="id,type,role").execute()
    verified = service.files().get(fileId=file_id, supportsAllDrives=True, fields="id,name,mimeType,size,modifiedTime,webViewLink").execute()
    final_permissions = service.permissions().list(fileId=file_id, supportsAllDrives=True, fields="permissions(id,type,role)").execute().get("permissions", [])
    if verified.get("mimeType") != "application/json" or not any(p.get("type") == "anyone" and p.get("role") == "reader" for p in final_permissions):
        raise RuntimeError("Drive snapshot exists but is not publicly readable JSON")
    return {"file_id": file_id, "url": f"https://drive.google.com/uc?export=download&id={file_id}",
            "size": verified.get("size"), "modified_time": verified.get("modifiedTime")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--if-stale", action="store_true", help="Skip upload when the public snapshot already matches the current Sheet stamps.")
    parser.add_argument("--summary-json", type=Path)
    args = parser.parse_args()
    settings = _settings()
    if settings.get("AMZ_BS_DRIVE_BACKEND", "gws").lower() != "gws":
        print("[beauty-index] public publishing is not configured", flush=True)
        return 2
    started = time.monotonic()
    try:
        payload = _dashboard_data()
        latest_stamps = {region: value["stamp"] for region, value in payload["markets"].items()}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        SNAPSHOT_PATH = Path(os.environ.get("TMPDIR", "/tmp")) / "beauty-index-public.json"
        SNAPSHOT_PATH.write_bytes(body)
        remote = _publish_drive_snapshot(payload, SNAPSHOT_PATH, settings, if_stale=args.if_stale)
        result = {
            "status": remote.get("status", "published"), "generated_at": payload["generated_at"],
            "history_records": len(payload["history"]), "products": len(payload["products"]),
            "bytes": len(body), "stamps": latest_stamps,
            "remote": remote, "elapsed_seconds": round(time.monotonic() - started, 1),
        }
        print("[beauty-index] " + json.dumps(result, ensure_ascii=False), flush=True)
        if args.summary_json:
            args.summary_json.parent.mkdir(parents=True, exist_ok=True)
            args.summary_json.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 0
    except Exception as exc:
        result = {"status": "failed", "error": str(exc)}
        print("[beauty-index] " + json.dumps(result, ensure_ascii=False), flush=True)
        if args.summary_json:
            args.summary_json.parent.mkdir(parents=True, exist_ok=True)
            args.summary_json.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
