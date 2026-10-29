from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHEET_ID = "1XQoI7SSuFKbuRAeD23uQIfJu3FBXEv__6rvm68Zfo80"
GWS_CONFIG_DIR = str(Path.home() / ".config" / "gws-amazon")
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _env() -> dict[str, str]:
    env = dict(os.environ)
    env.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", GWS_CONFIG_DIR)
    env.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", "keyring")
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    return env


def export_sheet(output: Path, env: dict[str, str]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.run(
        [
            "gws", "drive", "files", "export", "--params",
            json.dumps({"fileId": SHEET_ID, "mimeType": XLSX_MIME}),
            "--output", str(output),
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    if proc.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError((proc.stderr or proc.stdout).strip()[-600:] or "Sheet XLSX export failed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the live Sheet as a daily XLSX vault backup.")
    parser.add_argument("--email", action="store_true", help="email the exported workbook after Drive upload")
    parser.add_argument("--no-upload", action="store_true", help="only create the local XLSX")
    args = parser.parse_args()

    day = time.strftime("%Y%m%d")
    output = REPO_ROOT / "artifacts" / "exports" / "xlsx" / f"beauty_personal_care_top100_live_{day}.xlsx"
    env = _env()
    # drive_upload.py invokes gws in a child process; keep it on the same
    # scheduler-owned OAuth config as the export command.
    os.environ.setdefault("GOOGLE_WORKSPACE_CLI_CONFIG_DIR", env["GOOGLE_WORKSPACE_CLI_CONFIG_DIR"])
    os.environ.setdefault("GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND", env["GOOGLE_WORKSPACE_CLI_KEYRING_BACKEND"])
    export_sheet(output, env)
    result: dict[str, object] = {"xlsx": str(output), "bytes": output.stat().st_size}

    if not args.no_upload:
        from crawl_amazon_beauty_bestsellers.drive_upload import upload_file

        result["drive"] = upload_file(output, remote_name=output.name)

    if args.email:
        sys.path.insert(0, str(REPO_ROOT / "scripts"))
        from run_job import _send_email

        link = result.get("drive", {}).get("link", "") if isinstance(result.get("drive"), dict) else ""
        _send_email(
            f"[Amazon Beauty] daily XLSX backup {time.strftime('%Y-%m-%d %H:%M KST')}",
            "\n".join([
                "Daily Google Sheet XLSX backup completed.",
                f"Sheet: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit",
                f"Drive: {link}" if link else "Drive upload disabled.",
            ]),
            attachments=[output],
        )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
