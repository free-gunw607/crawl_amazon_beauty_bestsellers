from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers.root_publish import _italy_history_title_repairs


def test_italy_repairs_todays_trailing_blank_titles_from_top100_by_asin() -> None:
    existing = [
        ["2026-11-03", "IT", "B000000001", "1"],
        ["2026-11-02", "IT", "B000000002", "2"],
        ["2026-11-03", "IT", "B000000003", "3", "", "", "", "", ""],
        ["2026-11-03", "IT", "B000000004", "4", "", "", "", "", "Existing title"],
    ]
    history = [
        ["2026-11-03", "IT", "B000000001", "1", "", "EUR", "", "", ""],
        ["2026-11-02", "IT", "B000000002", "2", "", "EUR", "", "", ""],
        ["2026-11-03", "IT", "B000000003", "3", "", "EUR", "", "", "SQLite title"],
        ["2026-11-03", "IT", "B000000004", "4", "", "EUR", "", "", "Do not overwrite"],
    ]
    top = [
        ["fetched"], ["source"], ["rank", "asin", "title"],
        ["1", "B000000001", "Today's title"],
        ["3", "B000000003", "Current title must not overwrite"],
        ["4", "B000000004", "Top title must not overwrite"],
    ]

    repairs = _italy_history_title_repairs(existing, history, top, has_header=True)

    assert repairs == [
        {"range": "'IT Rank History'!I3", "values": [["Today's title"]]},
        {"range": "'IT Rank History'!I5", "values": [["SQLite title"]]},
    ]


def test_italy_history_without_header_uses_first_data_row_position() -> None:
    repairs = _italy_history_title_repairs(
        [["2026-11-03", "IT", "B000000001", "1"]],
        [["2026-11-03", "IT", "B000000001", "1", "", "EUR", "", "", ""]],
        [["fetched"], ["source"], ["rank", "asin", "title"], ["1", "B000000001", "Title"]],
        has_header=False,
    )

    assert repairs == [{"range": "'IT Rank History'!I2", "values": [["Title"]]}]
