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
            ["2026-10-28", "DE", "B"],
            ["2026-10-28", "UK", "C"],
            ["2026-10-28", "FR", "D"],
            ["2026-10-28", "ES", "E"],
        ],
    })

    assert metrics == {
        "rows": 5,
        "physical_last_row": 8,
        "blank_rows_within_range": 2,
        "newest_date": "2026-10-28",
    }
