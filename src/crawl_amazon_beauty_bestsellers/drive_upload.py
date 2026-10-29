from __future__ import annotations

import json
import os
from pathlib import Path

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DEFAULT_GWS_FOLDER_ID = "1xns4GiMLt1ZPa8me9At4IpgWDyB-SOgp"


class DriveUploadError(RuntimeError):
    pass


def _upload_via_gws(file_path: Path, folder_id: str, remote_name: str | None = None) -> dict[str, str]:
    import subprocess

    root = Path(__file__).resolve().parents[2]
    name = remote_name or file_path.name

    def run(command: list[str], operation: str) -> dict[str, object]:
        try:
            proc = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as exc:
            raise DriveUploadError("gws CLI not found on PATH") from exc
        if proc.returncode != 0:
            raise DriveUploadError(f"gws {operation} failed: {proc.stderr.strip()[-500:]}")
        stdout = proc.stdout
        try:
            return json.loads(stdout[stdout.index("{"):])
        except (ValueError, json.JSONDecodeError) as exc:
            raise DriveUploadError(f"gws {operation} returned invalid JSON") from exc

    escaped_name = name.replace("\\", "\\\\").replace("'", "\\'")
    escaped_folder = folder_id.replace("\\", "\\\\").replace("'", "\\'")
    query = f"name = '{escaped_name}' and '{escaped_folder}' in parents and trashed = false"
    listed = run(
        [
            "gws", "drive", "files", "list",
            "--params", json.dumps({
                "q": query,
                "pageSize": 100,
                "orderBy": "modifiedTime desc",
                "fields": "files(id,name,webViewLink,modifiedTime)",
                "supportsAllDrives": True,
                "includeItemsFromAllDrives": True,
            }),
        ],
        "file lookup",
    )
    matches = listed.get("files", [])
    existing = matches[0] if isinstance(matches, list) and matches and isinstance(matches[0], dict) else None
    if existing and existing.get("id"):
        params = {
            "fileId": existing["id"],
            "supportsAllDrives": True,
            "fields": "id,name,webViewLink",
        }
        info = run(
            [
                "gws", "drive", "files", "update",
                "--params", json.dumps(params),
                "--upload", str(file_path),
                "--upload-content-type", XLSX_MIME,
            ],
            "file update",
        )
    else:
        info = run(
            [
                "gws", "drive", "files", "create",
                "--upload", str(file_path),
                "--upload-content-type", XLSX_MIME,
                "--params", '{"supportsAllDrives": true, "fields": "id,name,webViewLink"}',
                "--json", json.dumps({"name": name, "parents": [folder_id]}),
            ],
            "upload",
        )
    file_id = info.get("id", "")
    return {
        "file_id": file_id,
        "name": str(info.get("name") or (existing or {}).get("name") or name),
        "link": str(info.get("webViewLink") or (existing or {}).get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"),
    }


def upload_file(file_path: Path, remote_name: str | None = None) -> dict[str, str]:
    backend = os.environ.get("AMZ_BS_DRIVE_BACKEND", "gws").lower()
    creds_env = os.environ.get("GDRIVE_CREDS", "")
    folder_id = os.environ.get("AMZ_BS_DRIVE_FOLDER_ID", "")
    if backend == "gws":
        return _upload_via_gws(file_path, folder_id or DEFAULT_GWS_FOLDER_ID, remote_name)
    if backend != "sa":
        raise DriveUploadError(f"unsupported Drive upload backend: {backend}")
    if not creds_env:
        raise DriveUploadError("GDRIVE_CREDS is required when AMZ_BS_DRIVE_BACKEND=sa")
    if backend == "sa":
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload

        try:
            creds_json = Path(creds_env).read_text(encoding="utf-8")
        except FileNotFoundError:
            creds_json = creds_env
        info = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/drive.file"]
        credentials = service_account.Credentials.from_service_account_info(info, scopes=scopes)
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        media = MediaFileUpload(str(file_path), mimetype=XLSX_MIME)
        file_metadata = {"name": remote_name or file_path.name}
        if folder_id:
            file_metadata["parents"] = [folder_id]
        created = (
            service.files()
            .create(body=file_metadata, media_body=media, fields="id, name, webViewLink", supportsAllDrives=True)
            .execute()
        )
        return {"file_id": created.get("id", ""), "name": created.get("name", ""), "link": created.get("webViewLink", "")}
