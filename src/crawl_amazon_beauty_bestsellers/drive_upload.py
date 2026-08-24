from __future__ import annotations

import json
import os
from pathlib import Path


class DriveUploadError(RuntimeError):
    pass


def upload_file(file_path: Path, remote_name: str | None = None) -> dict[str, str]:
    creds_env = os.environ.get("GDRIVE_CREDS", "")
    folder_id = os.environ.get("AMZ_BS_DRIVE_FOLDER_ID", "")
    if not creds_env:
        raise DriveUploadError(
            "GDRIVE_CREDS not configured; register the Google service account first (owner approval gate)"
        )
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
    media = MediaFileUpload(str(file_path), mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    file_metadata = {"name": remote_name or file_path.name}
    if folder_id:
        file_metadata["parents"] = [folder_id]
    created = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, name, webViewLink", supportsAllDrives=True)
        .execute()
    )
    return {"file_id": created.get("id", ""), "name": created.get("name", ""), "link": created.get("webViewLink", "")}
