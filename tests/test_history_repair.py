import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from audit_repair_root_history import _history_keys, _incomplete_cohorts, _summarize_missing


def test_history_key_comparison_uses_date_region_asin_rank() -> None:
    rows = [
        ["2026-10-29", "US", "A", "1", "10"],
        ["2026-10-29", "US", "A", "2", "10"],
        ["2026-10-29", "US", "", "3"],
    ]

    assert _history_keys(rows) == {
        ("2026-10-29", "US", "A", "1"),
        ("2026-10-29", "US", "A", "2"),
    }


def test_missing_history_summary_groups_append_rows_without_modifying_existing() -> None:
    summary = _summarize_missing([
        ["2026-10-29", "UK", "A", "1"],
        ["2026-10-29", "UK", "B", "2"],
        ["2026-10-28", "US", "C", "3"],
    ])

    assert summary["missing_rows"] == 3
    assert summary["missing_by_region_date"] == [
        {"region": "UK", "date": "2026-10-29", "rows": 2},
        {"region": "US", "date": "2026-10-28", "rows": 1},
    ]


def test_local_incomplete_cohorts_count_unique_asins_per_region_date() -> None:
    rows = [
        ["2026-09-17", "UK", f"A{idx}", str(idx)]
        for idx in range(1, 51)
    ]
    rows.append(["2026-09-17", "UK", "A1", "9"])

    assert _incomplete_cohorts(rows) == [
        {"region": "UK", "date": "2026-09-17", "unique_asins": 50}
    ]
