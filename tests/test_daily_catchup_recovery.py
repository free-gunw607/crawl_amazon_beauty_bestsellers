import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import daily_catchup
import watchdog_sheet
from daily_catchup import _failed_root_regions, _fallback_missing_drive, _recent_marketplace_block, _recent_root_block, _root_recovery_command


def test_catchup_respects_55_minute_marketplace_block_cooldown(tmp_path: Path) -> None:
    titles = tmp_path / "titles.json"
    titles.write_text(json.dumps({"regions": [{"region": "US", "blocked": "captcha"}]}), encoding="utf-8")
    now = time.time()

    assert _recent_marketplace_block(tmp_path, now=now)
    assert not _recent_marketplace_block(tmp_path, now=now + 55 * 60)


def test_catchup_detects_missing_drive_delivery(tmp_path: Path) -> None:
    workbook = tmp_path / "fallback.xlsx"
    workbook.write_bytes(b"test")
    fallback = tmp_path / "fallback.json"

    fallback.write_text(json.dumps({"xlsx": str(workbook), "drive_error": "expired oauth"}), encoding="utf-8")
    assert _fallback_missing_drive(tmp_path)

    fallback.write_text(json.dumps({"xlsx": str(workbook), "drive": {"file_id": "drive-id"}}), encoding="utf-8")
    assert not _fallback_missing_drive(tmp_path)


def test_partial_root_run_selects_only_incomplete_regions(tmp_path: Path) -> None:
    (tmp_path / "root.json").write_text(json.dumps({"regions": [
        {"region": "us", "crawled": 100, "published": 100, "fail": 0},
        {"region": "uk", "crawled": 0, "published": 0, "fail": 1},
    ]}), encoding="utf-8")

    assert _failed_root_regions(tmp_path) == ["uk"]


def test_root_recovery_command_uses_run_job_region_choices() -> None:
    command = _root_recovery_command(["UK", "Fr"])
    assert command[-2:] == ["uk", "fr"]


def test_failed_region_is_not_retried_if_another_node_updated_sheet_later(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "root.json").write_text(json.dumps({
        "finished": "2026-10-29T13:40:28+0900",
        "regions": [{"region": "uk", "crawled": 0, "published": 0, "fail": 1}],
    }), encoding="utf-8")
    monkeypatch.setattr(watchdog_sheet, "_gws_values", lambda _range, _env: [["2026-10-29 13:42 KST"]])

    assert _failed_root_regions(tmp_path, {}) == []


def test_sheet_verification_marks_a_same_day_short_table_as_stale(monkeypatch) -> None:
    today_stamp = time.strftime("%Y-%m-%d") + " 13:00 KST"

    def values(range_name: str, _env: dict[str, str]) -> list[list[str]]:
        if range_name.endswith("A1:C1"):
            return [[today_stamp]]
        count = 99 if range_name.startswith("[UK]") else 100
        return [[str(rank), f"ASIN{rank}"] for rank in range(1, count + 1)]

    monkeypatch.setattr(watchdog_sheet, "_gws_values", values)

    assert daily_catchup._stale_regions({}) == ["uk"]


def test_catchup_respects_recent_root_captcha_cooldown(tmp_path: Path) -> None:
    log = tmp_path / "run.log"
    log.write_text('{"region":"UK","crawled":0,"blocked":"https://amazon.co.uk/"}', encoding="utf-8")
    (tmp_path / "root.json").write_text(json.dumps({"log": str(log)}), encoding="utf-8")
    now = time.time()

    assert _recent_root_block(tmp_path, now=now)
    assert not _recent_root_block(tmp_path, now=now + 55 * 60)
