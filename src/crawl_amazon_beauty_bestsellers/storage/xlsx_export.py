from __future__ import annotations

import json
import time
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

from ..config import Settings
from .store import Store


def _autosize(ws):
    for column_cells in ws.columns:
        length = max((len(str(c.value)) for c in column_cells if c.value is not None), default=8)
        ws.column_dimensions[get_column_letter(column_cells[0].column)].width = min(max(length + 2, 8), 60)


CURATED_SPEC_COLUMNS = [
    ("Item Form", "item_form"),
    ("Skin Type", "skin_type"),
    ("Item Weight", "item_weight"),
    ("Unit Count", "unit_count"),
    ("Active Ingredients", "active_ingredients"),
    ("Material Type Free", "material_free"),
    ("Sun Protection Factor", "spf"),
    ("Age Range Description", "age_range"),
    ("Country as Labeled", "country"),
    ("Country of Origin", "country"),
    ("Recommended Uses For Product", "recommended_uses"),
    ("Product Benefits", "product_benefits"),
]


def _parse_specs(raw: str) -> dict[str, str]:
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def export_day(settings: Settings, store: Store, date_str: str | None = None) -> Path:
    date_str = date_str or time.strftime("%Y-%m-%d")
    wb = Workbook()
    header_font = Font(bold=True)
    wrap = Alignment(wrap_text=True, vertical="top")

    first = True
    per_node = store.day_latest_rows(date_str)
    for node_id, rows in sorted(per_node.items()):
        sheet_name = f"node_{node_id}"[:31]
        if first:
            ws = wb.active
            ws.title = sheet_name
            first = False
        else:
            ws = wb.create_sheet(sheet_name)
        headers = ["rank", "asin", "title", "rating", "ratings_count", "price", "currency", "offers_text", "url"]
        ws.append(headers)
        for cell in ws[1]:
            cell.font = header_font
        for row in rows:
            ws.append([
                row.get("rank"), row.get("asin"), row.get("title"),
                row.get("rating"), row.get("ratings_count"),
                row.get("price_amount"), row.get("price_currency"),
                row.get("offers_text"), row.get("url"),
            ])
        _autosize(ws)

    details = store.detail_day_rows(date_str)
    if details:
        parsed_details = [(row, _parse_specs(row.get("specs") or "")) for row in details]

        ws = wb.create_sheet("details")
        keys = [
            "asin", "brand", "manufacturer", "model_number", "seller_name",
            "buy_box_price", "buy_box_currency", "list_price_amount",
            "bsr_main_rank", "bsr_main_category", "date_first_available",
            "availability", "price_source", "variants_count",
        ]
        header_cols: list[str] = []
        for _, column in CURATED_SPEC_COLUMNS:
            if column not in header_cols:
                header_cols.append(column)
        ws.append(["fetched_at"] + keys + header_cols + ["specs_json"])
        for cell in ws[1]:
            cell.font = header_font
        for row, specs in parsed_details:
            curated_values = []
            for column in header_cols:
                value = ""
                for label, target in CURATED_SPEC_COLUMNS:
                    if target != column:
                        continue
                    candidate = specs.get(label)
                    if candidate:
                        value = candidate
                        break
                curated_values.append(value)
            specs_pretty = json.dumps(specs, ensure_ascii=False)[:3000]
            ws.append([row.get("fetched_at")] + [row.get(k) for k in keys] + curated_values + [specs_pretty])
            ws.cell(row=ws.max_row, column=len(keys) + len(curated_values) + 2).alignment = wrap
        _autosize(ws)

        ws = wb.create_sheet("specs_long")
        ws.append(["asin", "brand", "spec_key", "spec_value"])
        for cell in ws[1]:
            cell.font = header_font
        for row, specs in parsed_details:
            for key, value in sorted(specs.items()):
                ws.append([row.get("asin"), row.get("brand"), key, str(value)[:500]])
        _autosize(ws)

    trend = store.trend_rows(days=14)
    if trend:
        ws = wb.create_sheet("trend_14d")
        ws.append(["day", "node_id", "asin", "best_rank", "snapshots", "max_ratings"])
        for cell in ws[1]:
            cell.font = header_font
        for row in trend:
            ws.append(list(row.values()))
        _autosize(ws)

    exports_dir = settings.resolve(settings.storage.exports_dir)
    exports_dir.mkdir(parents=True, exist_ok=True)
    out_path = exports_dir / f"amazon_bs_{date_str.replace('-', '')}.xlsx"
    wb.save(out_path)
    return out_path
