from __future__ import annotations

import importlib.util
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_fallback_workbook.py"
SPEC = importlib.util.spec_from_file_location("export_fallback_workbook", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_fallback_repairs_only_blank_titles_from_the_latest_italy_snapshot() -> None:
    history = [
        ["2026-11-02", "IT", "B000000001", "1", "", "EUR", "", "", ""],
        ["2026-11-03", "IT", "B000000001", "1", "", "EUR", "", "", ""],
        ["2026-11-03", "IT", "B000000002", "2", "", "EUR", "", "", "Keep existing"],
        ["2026-11-03", "IT", "B000000003", "3", "", "EUR", "", "", ""],
    ]
    top = [
        ["fetched"], ["source"], ["rank", "asin", "title"],
        ["1", "B000000001", "Today's title"],
        ["2", "B000000002", "Do not overwrite"],
    ]

    repaired = MODULE._repair_latest_italy_history_titles(history, top)

    assert repaired[0][8] == ""  # Never project today's title into an old date.
    assert repaired[1][8] == "Today's title"
    assert repaired[2][8] == "Keep existing"
    assert repaired[3][8] == ""  # ASIN absent from today's Top 100 stays blank.
    assert history[1][8] == ""  # Input rows are not mutated.
