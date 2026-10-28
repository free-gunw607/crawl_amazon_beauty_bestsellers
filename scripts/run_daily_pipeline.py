from __future__ import annotations

"""Run one ordered daily delivery without allowing Drive errors to hide XLSX."""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET_URL = "https://docs.google.com/spreadsheets/d/1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80/edit"
REGIONS = ("US", "DE", "UK", "FR", "ES")


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = REPO_ROOT / ".env"
    if env_file.is_file():
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                env.setdefault(key.strip(), value.strip().strip("\"'"))
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if not env.get("AMZ_BS_ROOT_BACKEND"):
        env["AMZ_BS_ROOT_BACKEND"] = "sa" if env.get("GDRIVE_CREDS") else "gws"
    env.setdefault("AMZ_BS_ROOT_SHEETS_ID", "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80")
    return env


def _read_summary(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _merge_history_counts_from_log(root: dict[str, object]) -> dict[str, object]:
    """Recover append counts omitted by older run_job summaries from their raw log."""
    log_path = Path(str(root.get("log", "")))
    if not log_path.is_file():
        return root
    rows = root.get("regions")
    if not isinstance(rows, list):
        return root
    by_region = {
        str(row.get("region", "")).upper(): row
        for row in rows
        if isinstance(row, dict)
    }
    try:
        for line in log_path.read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(item, dict) or "history_appended" not in item:
                continue
            region = str(item.get("region", "")).upper()
            if region in by_region:
                by_region[region]["history_appended"] = int(item["history_appended"] or 0)
    except OSError:
        pass
    return root


def _run(name: str, command: list[str], env: dict[str, str]) -> int:
    print(f"[daily] {name} start: {' '.join(command)}", flush=True)
    started = time.monotonic()
    proc = subprocess.run(command, cwd=REPO_ROOT, env=env)
    print(f"[daily] {name} finished rc={proc.returncode} elapsed={int(time.monotonic() - started)}s", flush=True)
    return proc.returncode


def _root_table(root: dict[str, object]) -> list[str]:
    rows = root.get("regions")
    if not isinstance(rows, list):
        return ["No root summary was produced."]
    by_region = {str(row.get("region", "")).upper(): row for row in rows if isinstance(row, dict)}
    lines = ["             US    DE    UK    FR    ES   TOTAL"]
    for label, key in (
        ("Collected", "crawled"),
        ("Published", "published"),
        ("History +", "history_appended"),
        ("Failed", "fail"),
    ):
        values = [int(by_region.get(region, {}).get(key, 0) or 0) for region in REGIONS]
        lines.append(f"{label:<10} " + " ".join(f"{value:>5}" for value in values) + f" {sum(values):>7}")
    return lines


def _title_completion_command(python: str, summary_path: Path, *, read_only: bool = False) -> list[str]:
    command = [
        python,
        "scripts/enrich_titles_until_complete.py",
        "--regions", "us", "de", "uk", "fr", "es",
        "--batch-size", "10",
        "--max-rounds", "0",
        "--timeout-sec", "420",
        "--sleep-sec", "15",
        "--no-backfill-history",
    ]
    if read_only:
        command.append("--no-fallback")
    command.extend(["--summary-json", str(summary_path)])
    return command


def _title_lines(titles: dict[str, object], title_rc: int | None) -> list[str]:
    if title_rc is None:
        return ["Skipped because the root collection did not complete."]
    rows = titles.get("regions")
    if not isinstance(rows, list):
        return [f"Title completion failed (exit {title_rc})."]
    lines: list[str] = []
    for row in rows:
        if isinstance(row, dict):
            lines.append(
                f"{str(row.get('region', '?')).upper()}: "
                f"{row.get('titled', 0)}/{row.get('total', 0)} titles, missing {row.get('missing', 0)}"
            )
    return lines or ["No title result was produced."]


def _fallback_lines(fallback: dict[str, object], fallback_rc: int) -> list[str]:
    xlsx = Path(str(fallback.get("xlsx", "")))
    if not xlsx.is_file():
        return [f"XLSX creation failed (exit {fallback_rc})."]
    lines = [f"Local XLSX: {xlsx.name} ({xlsx.stat().st_size:,} bytes)"]
    drive = fallback.get("drive")
    if isinstance(drive, dict) and drive.get("link"):
        lines.append(f"Drive: {drive['link']}")
    else:
        lines.append(f"Drive: unavailable ({fallback.get('drive_error', 'not attempted')})")
    lines.append("The same local XLSX is attached to this email.")
    return lines


def _build_final(trigger: str, root_rc: int, title_rc: int | None, fallback_rc: int, root: dict[str, object], titles: dict[str, object], fallback: dict[str, object]) -> str:
    drive = fallback.get("drive")
    drive_uploaded = isinstance(drive, dict) and bool(drive.get("file_id"))
    completed = root_rc == 0 and title_rc == 0 and fallback_rc == 0 and drive_uploaded
    status = "COMPLETED" if completed else "ATTENTION REQUIRED"
    recovery = trigger in {"catchup", "secondary-takeover", "manual"}
    drive_line = (
        f"Drive fallback XLSX: {drive.get('link')}"
        if isinstance(drive, dict) and drive.get("link")
        else f"Drive fallback XLSX: failed ({fallback.get('drive_error', 'not attempted')})"
    )
    history = titles.get("history")
    lines = [
        "Amazon Beauty Final Report",
        f"{time.strftime('%Y-%m-%d')} KST | Final status: {status}",
        "",
        "[1] Initial collection and recovery result",
        "Scheduled primary result: " + ("not applicable" if recovery else ("completed" if root_rc == 0 else "failed")),
        "Recovery result: " + ("executed below" if recovery else "not required"),
        *_root_table(root),
        "",
        "[2] Title completion final result",
        *_title_lines(titles, title_rc),
        (
            "root_rank_history title backfill: "
            f"updated {history.get('updated', 0)}, remaining {history.get('remaining_after', 0)}"
            if isinstance(history, dict)
            else "Historical title repair: deferred from the daily path; today's rank rows are appended in [1]."
        ),
        "",
        "[3] Primary delivery",
        f"Google Sheet: {SHEET_URL}",
        drive_line,
        "",
        "[4] Independent fallback XLSX",
        *_fallback_lines(fallback, fallback_rc),
        "Source: local SQLite, independent of Google Sheets export or Drive upload.",
    ]
    return "\n".join(lines)


def _send(subject: str, body: str, attachment: Path | None, telegram: bool = False) -> bool:
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from run_job import _send_email, _send_telegram

    sent, detail = _send_email(subject, body, [attachment] if attachment and attachment.is_file() else None)
    if not sent:
        _send_telegram(f"⚠️ Amazon Beauty report email failed: {detail}")
    if telegram:
        _send_telegram(body)
    return sent


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--trigger", default="scheduled", choices=("scheduled", "catchup", "secondary-takeover", "manual"))
    parser.add_argument(
        "--report-existing",
        type=Path,
        help="Re-audit and deliver a prior run's report without recrawling or reuploading its fallback XLSX.",
    )
    args = parser.parse_args()
    env = _env()
    if args.report_existing:
        run_dir = args.report_existing.expanduser().resolve()
        root_path, titles_path, fallback_path = (run_dir / "root.json", run_dir / "titles.json", run_dir / "fallback.json")
        if not root_path.is_file() or not fallback_path.is_file():
            parser.error("--report-existing requires existing root.json and fallback.json files")
        root = _read_summary(root_path)
        root = _merge_history_counts_from_log(root)
        root_rc = 0 if root.get("status") == "completed" else 1
        title_rc = _run(
            "read-only live title audit",
            _title_completion_command(sys.executable, titles_path, read_only=True),
            env,
        )
        titles = _read_summary(titles_path)
        fallback = _read_summary(fallback_path)
        workbook = Path(str(fallback.get("xlsx", "")))
        fallback_rc = 0 if workbook.is_file() else 1
    else:
        run_dir = REPO_ROOT / ".agent" / "state" / "daily_pipeline" / time.strftime("%Y%m%d_%H%M%S")
        run_dir.mkdir(parents=True, exist_ok=True)
        root_path, titles_path, fallback_path = (run_dir / "root.json", run_dir / "titles.json", run_dir / "fallback.json")

        root_rc = _run("root collection", [sys.executable, "scripts/run_job.py", "--no-detail", "--no-notify", "--summary-json", str(root_path)], env)
        title_rc: int | None = None
        if root_rc == 0:
            title_rc = _run(
                "title completion",
                _title_completion_command(sys.executable, titles_path),
                env,
            )
        else:
            print("[daily] title completion skipped because root collection failed", flush=True)

        # This must finish before any report. Drive failure is captured inside the
        # exporter and cannot prevent the local file from being attached below.
        fallback_rc = _run("independent XLSX fallback", [sys.executable, "scripts/export_fallback_workbook.py", "--summary-json", str(fallback_path)], env)
        root, titles, fallback = _read_summary(root_path), _read_summary(titles_path), _read_summary(fallback_path)
        workbook = Path(str(fallback.get("xlsx", "")))

    final = _build_final(args.trigger, root_rc, title_rc, fallback_rc, root, titles, fallback)
    drive_uploaded = isinstance(fallback.get("drive"), dict) and bool(fallback["drive"].get("file_id"))
    complete = root_rc == 0 and title_rc == 0 and fallback_rc == 0 and drive_uploaded

    # Successful runs retain the three phase reports. Failed runs send one
    # final report rather than flooding the inbox every time a catch-up fires.
    phase_mail_results: list[bool] = []
    if complete:
        phase_mail_results.append(_send("[Amazon Beauty] initial collection result", "\n".join(["[1] Initial collection result", *_root_table(root)]), None))
        phase_mail_results.append(_send("[Amazon Beauty] title completion result", "\n".join(["[2] Title completion result", *_title_lines(titles, title_rc)]), None))
        phase_mail_results.append(_send("[Amazon Beauty] independent fallback XLSX", "\n".join(["[4] Independent fallback XLSX", *_fallback_lines(fallback, fallback_rc)]), workbook))
    phase_mail_ok = all(phase_mail_results)
    if complete and not phase_mail_ok:
        final = final.replace("Final status: COMPLETED", "Final status: ATTENTION REQUIRED (phase email delivery incomplete)")
        final += f"\nPhase emails accepted: {sum(phase_mail_results)}/{len(phase_mail_results)}"
    subject = f"[Amazon Beauty] Final {'COMPLETED' if complete and phase_mail_ok else 'ATTENTION REQUIRED'} {time.strftime('%Y-%m-%d %H:%M KST')}"
    final_mail_ok = _send(subject, final, workbook, telegram=True)
    return 0 if complete and phase_mail_ok and final_mail_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
