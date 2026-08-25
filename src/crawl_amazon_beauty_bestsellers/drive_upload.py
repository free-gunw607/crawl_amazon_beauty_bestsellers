from __future__ import annotations

import json
import os
from pathlib import Path

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DEFAULT_GWS_FOLDER_ID = "1xns4GiMLt1ZPa8me9At4IpgWDyB-SOgp"


class DriveUploadError(RuntimeError):
    pass


def _upload_via_gws(file_path: Path, folder_id: str) -> dict[str, str]:
    import subprocess

    cmd = [
        "gws", "drive", "files", "create",
        "--upload", str(file_path),
        "--upload-content-type", XLSX_MIME,
        "--params", '{"supportsAllDrives": true}',
        "--json", json.dumps({"name": file_path.name, "parents": [folder_id]}),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except FileNotFoundError:
        raise DriveUploadError("gws CLI not found on PATH")
    if proc.returncode != 0:
        raise DriveUploadError(f"gws upload failed: {proc.stderr.strip()[-300:]}")
    stdout = proc.stdout
    info = json.loads(stdout[stdout.index("{"):])
    file_id = info.get("id", "")
    return {
        "file_id": file_id,
        "name": info.get("name", ""),
        "link": f"https://drive.google.com/file/d/{file_id}/view",
    }


def upload_file(file_path: Path, remote_name: str | None = None) -> dict[str, str]:
    creds_env = os.environ.get("GDRIVE_CREDS", "")
    folder_id = os.environ.get("AMZ_BS_DRIVE_FOLDER_ID", "")
    if creds_env:
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
    return _upload_via_gws(file_path, folder_id or DEFAULT_GWS_FOLDER_ID)
