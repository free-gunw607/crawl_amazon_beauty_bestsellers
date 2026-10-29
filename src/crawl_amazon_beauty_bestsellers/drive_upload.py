from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import subprocess
import time

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
DEFAULT_GWS_FOLDER_ID = "1xns4GiMLt1ZPa8me9At4IpgWDyB-SOgp"


class DriveUploadError(RuntimeError):
    pass


def _run_gws_json(
    command: list[str],
    operation: str,
    *,
    env: dict[str, str] | None = None,
    retries: int = 1,
    retry_not_found: bool = False,
) -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    last_error = ""
    for attempt in range(retries):
        try:
            proc = subprocess.run(command, cwd=root, env=env, capture_output=True, text=True, timeout=600)
        except FileNotFoundError as exc:
            raise DriveUploadError("gws CLI not found on PATH") from exc
        except subprocess.TimeoutExpired as exc:
            last_error = f"gws {operation} timed out"
        else:
            if proc.returncode == 0:
                stdout = proc.stdout
                try:
                    return json.loads(stdout[stdout.index("{"):])
                except (ValueError, json.JSONDecodeError) as exc:
                    raise DriveUploadError(f"gws {operation} returned invalid JSON") from exc
            last_error = (proc.stderr or proc.stdout).strip()[-500:]

        lowered = last_error.lower()
        retryable = any(token in lowered for token in (
            "429", "500", "502", "503", "504", "rate limit", "temporarily unavailable",
            "user rate limit exceeded", "userratelimitexceeded", "quota exceeded for quota metric",
            "resource_exhausted", "connection reset", "connection aborted", "timed out", "internal error",
        )) or (retry_not_found and ("404" in lowered or "not found" in lowered))
        if not retryable or attempt + 1 >= retries:
            break
        rate_limited = any(token in lowered for token in (
            "429", "rate limit", "userratelimitexceeded", "quota exceeded for quota metric", "resource_exhausted",
        ))
        delay = 65 if rate_limited else min(2 ** (attempt + 1), 15)
        time.sleep(delay)
    raise DriveUploadError(f"gws {operation} failed: {last_error}")


def _file_matches_local(info: dict[str, object], file_path: Path, folder_id: str) -> bool:
    if info.get("trashed") is True or info.get("mimeType") != XLSX_MIME:
        return False
    try:
        if int(info.get("size", -1)) != file_path.stat().st_size:
            return False
    except (TypeError, ValueError, OSError):
        return False
    parents = info.get("parents")
    if not isinstance(parents, list) or folder_id not in parents:
        return False
    remote_md5 = str(info.get("md5Checksum", "")).lower()
    digest = hashlib.md5()
    try:
        with file_path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    except OSError:
        return False
    return bool(remote_md5) and remote_md5 == digest.hexdigest()


def _get_gws_file(file_id: str, *, env: dict[str, str] | None = None, retry_not_found: bool = False) -> dict[str, object]:
    return _run_gws_json(
        [
            "gws", "drive", "files", "get",
            "--params", json.dumps({
                "fileId": file_id,
                "supportsAllDrives": True,
                "fields": "id,name,mimeType,size,md5Checksum,modifiedTime,parents,trashed,webViewLink",
            }),
        ],
        "file verification",
        env=env,
        retries=4,
        retry_not_found=retry_not_found,
    )


def verify_file(file_id: str, file_path: Path, folder_id: str, *, env: dict[str, str] | None = None) -> bool:
    """Check that Drive still has the exact local XLSX in the expected folder."""
    try:
        info = _get_gws_file(file_id, env=env)
    except DriveUploadError as exc:
        message = str(exc).lower()
        if "404" in message or "not found" in message:
            return False
        raise
    return _file_matches_local(info, file_path, folder_id)


def _upload_via_gws(file_path: Path, folder_id: str, remote_name: str | None = None) -> dict[str, str]:
    name = remote_name or file_path.name

    escaped_name = name.replace("\\", "\\\\").replace("'", "\\'")
    escaped_folder = folder_id.replace("\\", "\\\\").replace("'", "\\'")
    query = f"name = '{escaped_name}' and '{escaped_folder}' in parents and trashed = false"
    listed = _run_gws_json(
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
        retries=4,
    )
    matches = listed.get("files", [])
    existing = matches[0] if isinstance(matches, list) and matches and isinstance(matches[0], dict) else None
    if existing and existing.get("id"):
        params = {
            "fileId": existing["id"],
            "supportsAllDrives": True,
            "fields": "id,name,webViewLink",
        }
        info = _run_gws_json(
            [
                "gws", "drive", "files", "update",
                "--params", json.dumps(params),
                "--upload", str(file_path),
                "--upload-content-type", XLSX_MIME,
            ],
            "file update",
            retries=4,
        )
    else:
        # Create is intentionally single-shot: it is not idempotent. If its
        # response is ambiguous, the next scheduled attempt starts with a name
        # lookup and updates the created file instead of blindly creating again.
        info = _run_gws_json(
            [
                "gws", "drive", "files", "create",
                "--upload", str(file_path),
                "--upload-content-type", XLSX_MIME,
                "--params", '{"supportsAllDrives": true, "fields": "id,name,webViewLink"}',
                "--json", json.dumps({"name": name, "parents": [folder_id]}),
            ],
            "upload",
            retries=1,
        )
    file_id = info.get("id", "")
    if not file_id:
        raise DriveUploadError("Drive upload response contained no file ID")
    verified = _get_gws_file(str(file_id), retry_not_found=True)
    if not _file_matches_local(verified, file_path, folder_id):
        raise DriveUploadError("Drive upload verification failed: remote XLSX does not match local file or target folder")
    return {
        "file_id": file_id,
        "name": str(verified.get("name") or info.get("name") or (existing or {}).get("name") or name),
        "link": str(verified.get("webViewLink") or info.get("webViewLink") or (existing or {}).get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"),
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
