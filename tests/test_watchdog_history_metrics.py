import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from watchdog_sheet import _history_metrics


def test_history_metrics_separates_populated_rows_from_blank_physical_rows() -> None:
    metrics = _history_metrics({
        "range": "root_rank_history!A1:I8",
        "values": [
            ["date", "region", "asin"],
            ["2026-10-28", "US", "A"],
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
        "physical_last_row": 8,
        "blank_rows_within_range": 0,
        "newest_date": "2026-10-29",
        "latest_by_region": {
            "US": {"date": "2026-10-29", "rows": 2, "unique_keys": 1},
            "DE": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "UK": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "FR": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
            "ES": {"date": "2026-10-28", "rows": 1, "unique_keys": 1},
        },
        "duplicate_keys": 1,
    }
