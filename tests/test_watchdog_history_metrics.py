import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from datetime import datetime

from watchdog_sheet import STAMPED_TABS, _history_metrics, _stamp_is_fresh


def test_history_metrics_separates_populated_rows_from_blank_physical_rows() -> None:
    metrics = _history_metrics({
        "range": "root_rank_history!A1:I10",
        "values": [
            ["date", "region", "asin"],
            ["2026-10-28", "US", "A", "2"],
            [],
            ["2026-10-29", "US", "A", "1"],
            ["2026-10-29", "US", "A", "1"],
            ["2026-10-28", "DE", "B", "1"],
            ["2026-10-28", "UK", "C", "1"],
            ["2026-10-28", "FR", "D", "1"],
            ["2026-10-28", "ES", "E", "1"],
        ],
    })

    assert metrics == {
        "rows": 7,
        "physical_last_row": 10,
        "last_populated_row": 9,
        "blank_rows_within_range": 1,
        "trailing_blank_rows": 1,
        "newest_date": "2026-10-29",
        "latest_by_region": {
            "US": {"date": "2026-10-29", "rows": 2, "unique_keys": 1},
            "DE": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "UK": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "FR": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "ES": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
        },
        "duplicate_keys": 1,
        "blank_row_numbers_sample": [3],
        "date_region_cohorts": 6,
        "incomplete_date_region_cohorts": 6,
        "incomplete_date_region_samples": [
            {"date": "2026-10-28", "region": "DE", "unique_asins": 1},
            {"date": "2026-10-28", "region": "ES", "unique_asins": 1},
            {"date": "2026-10-28", "region": "FR", "unique_asins": 1},
            {"date": "2026-10-28", "region": "UK", "unique_asins": 1},
            {"date": "2026-10-28", "region": "US", "unique_asins": 1},
            {"date": "2026-10-29", "region": "US", "unique_asins": 1},
        ],
    }


def test_watchdog_covers_all_fifteen_published_workbook_tabs() -> None:
    assert len(STAMPED_TABS) == 15
    assert "UK Rank History" in STAMPED_TABS
    assert "[ALL] Top 100" in STAMPED_TABS
    assert "Price History" in STAMPED_TABS


def test_watchdog_marks_invalid_or_old_tab_stamp_stale() -> None:
    now = datetime(2026, 10, 29, 14, 0)

    assert _stamp_is_fresh("2026-10-29 13:40 KST", now, 30)[0]
    assert not _stamp_is_fresh("2026-10-28 05:03 KST", now, 8)[0]
    assert not _stamp_is_fresh("", now, 30)[0]
