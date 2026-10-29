from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_daily_pipeline import (
    _build_final,
    _global_sheet_refresh_command,
    _merge_history_counts_from_log,
    _root_complete,
    _regions_in_root,
    _root_collection_command,
    _root_table,
    _titles_complete,
    _title_completion_command,
)


def test_root_collection_command_normalizes_pipeline_regions_for_run_job() -> None:
    command = _root_collection_command("python", Path("root.json"), ("UK",))
    assert command[command.index("--regions") + 1] == "uk"


def test_title_completion_keeps_historical_backfill_off_daily_quota_path() -> None:
    command = _title_completion_command("python", Path("titles.json"))

    assert "--no-backfill-history" in command
    assert "--backfill-latest-history" in command
    assert command[command.index("--summary-json") + 1] == "titles.json"

    audit_command = _title_completion_command("python", Path("audit.json"), read_only=True)
    assert "--no-fallback" in audit_command
    assert "--no-backfill-history" in audit_command
    assert "--backfill-latest-history" not in audit_command


def test_partial_recovery_refreshes_shared_sheet_views_without_crawling() -> None:
    command = _global_sheet_refresh_command("python")

    assert command[-3:] == ["--region", "es", "--shared-views-only"]
    assert "root-cycle" not in command


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


def test_missing_live_top100_title_cannot_be_reported_as_complete() -> None:
    titles = {
        "regions": [
            {"region": region, "total": 100, "titled": 99 if region == "US" else 100, "missing": 1 if region == "US" else 0}
            for region in ("US", "DE", "UK", "FR", "ES")
        ]
    }

    assert not _titles_complete(titles)


def test_root_completion_requires_full_publish_and_no_failed_regions() -> None:
    root = {
        "regions": [
            {"region": region, "crawled": 100, "published": 100, "fail": int(region == "UK")}
            for region in ("US", "DE", "UK", "FR", "ES")
        ]
    }

    assert not _root_complete(root)


def test_root_recovery_summary_is_evaluated_for_its_selected_regions() -> None:
    root = {"regions": [{"region": "uk", "crawled": 100, "published": 100, "fail": 0}]}
    assert _regions_in_root(root) == ("UK",)
    assert _root_complete(root, _regions_in_root(root))
    assert not _root_complete(root, ("US", "DE", "FR", "ES"))


def test_root_completion_rejects_short_publish_counts() -> None:
    root = {"regions": [{"region": "UK", "crawled": 100, "published": 99, "fail": 0}]}

    assert not _root_complete(root, ("UK",))


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
