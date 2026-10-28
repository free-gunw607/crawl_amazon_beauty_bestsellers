from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_daily_pipeline import (
    _build_final,
    _merge_history_counts_from_log,
    _root_table,
    _title_completion_command,
)


def test_title_completion_keeps_historical_backfill_off_daily_quota_path() -> None:
    command = _title_completion_command("python", Path("titles.json"))

    assert "--no-backfill-history" in command
    assert command[command.index("--summary-json") + 1] == "titles.json"

    audit_command = _title_completion_command("python", Path("audit.json"), read_only=True)
    assert "--no-fallback" in audit_command


def test_root_report_includes_append_only_history_rows() -> None:
    lines = _root_table({
        "regions": [
            {"region": "us", "crawled": 100, "published": 100, "history_appended": 100},
            {"region": "de", "crawled": 100, "published": 100, "history_appended": 98},
        ]
    })

    history_line = next(line for line in lines if line.startswith("History +"))
    assert "100" in history_line
    assert "98" in history_line
    assert history_line.rstrip().endswith("198")


def test_drive_upload_failure_cannot_be_reported_as_pipeline_complete() -> None:
    report = _build_final(
        "scheduled",
        0,
        0,
        0,
        {"regions": []},
        {"regions": []},
        {"drive_error": "upload unavailable"},
    )

    assert "Final status: ATTENTION REQUIRED" in report


def test_older_root_summary_recovers_history_counts_from_raw_log(tmp_path: Path) -> None:
    log_path = tmp_path / "run.log"
    log_path.write_text(
        '{"region":"US","published":100,"history_appended":96}\n',
        encoding="utf-8",
    )
    root = {
        "log": str(log_path),
        "regions": [{"region": "us", "crawled": 100, "published": 100}],
    }

    merged = _merge_history_counts_from_log(root)

    assert merged["regions"][0]["history_appended"] == 96
