from pathlib import Path
from types import SimpleNamespace
import subprocess
import hashlib
import json

from crawl_amazon_beauty_bestsellers import drive_upload


def test_drive_upload_defaults_to_user_oauth_even_with_sheet_service_account(monkeypatch, tmp_path: Path) -> None:
    workbook = tmp_path / "fallback.xlsx"
    workbook.write_bytes(b"xlsx")
    monkeypatch.setenv("GDRIVE_CREDS", "/configured/sheets-service-account.json")
    monkeypatch.delenv("AMZ_BS_DRIVE_BACKEND", raising=False)
    monkeypatch.setenv("AMZ_BS_DRIVE_FOLDER_ID", "owner-drive-folder")
    calls: list[tuple[Path, str, str | None]] = []

    def upload_with_user_oauth(path: Path, folder_id: str, remote_name: str | None = None) -> dict[str, str]:
        calls.append((path, folder_id, remote_name))
        return {"file_id": "uploaded", "name": remote_name or path.name, "link": "https://drive.example/uploaded"}

    monkeypatch.setattr(drive_upload, "_upload_via_gws", upload_with_user_oauth)

    result = drive_upload.upload_file(workbook, "daily.xlsx")

    assert result["file_id"] == "uploaded"
    assert calls == [(workbook, "owner-drive-folder", "daily.xlsx")]


def test_service_account_drive_upload_requires_explicit_backend(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("GDRIVE_CREDS", "/configured/sheets-service-account.json")
    monkeypatch.setenv("AMZ_BS_DRIVE_BACKEND", "unsupported")

    try:
        drive_upload.upload_file(tmp_path / "fallback.xlsx")
    except drive_upload.DriveUploadError as exc:
        assert "unsupported Drive upload backend" in str(exc)
    else:
        raise AssertionError("unsupported Drive backend should fail")


def test_gws_upload_runs_from_repo_root_for_cli_path_validation(monkeypatch, tmp_path: Path) -> None:
    captured: list[dict[str, object]] = []
    workbook = tmp_path / "fallback.xlsx"
    workbook.write_bytes(b"xlsx-content")
    responses = [
        SimpleNamespace(returncode=0, stdout='{"files":[]}', stderr=""),
        SimpleNamespace(returncode=0, stdout='{"id":"drive-id","name":"fallback.xlsx"}', stderr=""),
        SimpleNamespace(returncode=0, stdout=json.dumps({
            "id": "drive-id", "name": "fallback.xlsx", "mimeType": drive_upload.XLSX_MIME,
            "size": str(workbook.stat().st_size), "md5Checksum": hashlib.md5(b"xlsx-content").hexdigest(),
            "parents": ["folder-id"], "trashed": False,
        }), stderr=""),
    ]

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured.append({"command": command, **kwargs})
        return responses.pop(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = drive_upload._upload_via_gws(workbook, "folder-id")

    assert result["file_id"] == "drive-id"
    assert len(captured) == 3
    assert captured[0]["command"][2:4] == ["files", "list"]
    assert captured[1]["command"][2:4] == ["files", "create"]
    assert captured[2]["command"][2:4] == ["files", "get"]
    assert all(item["cwd"] == Path(drive_upload.__file__).resolve().parents[2] for item in captured)


def test_gws_upload_updates_existing_daily_workbook_without_creating_duplicate(monkeypatch, tmp_path: Path) -> None:
    calls: list[list[str]] = []
    workbook = tmp_path / "fallback.xlsx"
    workbook.write_bytes(b"updated-xlsx")
    responses = [
        SimpleNamespace(returncode=0, stdout='{"files":[{"id":"existing-id","name":"daily.xlsx","webViewLink":"https://drive/existing"}]}', stderr=""),
        SimpleNamespace(returncode=0, stdout='{"id":"existing-id","name":"daily.xlsx"}', stderr=""),
        SimpleNamespace(returncode=0, stdout=json.dumps({
            "id": "existing-id", "name": "daily.xlsx", "webViewLink": "https://drive/existing",
            "mimeType": drive_upload.XLSX_MIME, "size": str(workbook.stat().st_size),
            "md5Checksum": hashlib.md5(b"updated-xlsx").hexdigest(),
            "parents": ["folder-id"], "trashed": False,
        }), stderr=""),
    ]

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return responses.pop(0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = drive_upload._upload_via_gws(workbook, "folder-id", "daily.xlsx")

    assert [call[3] for call in calls] == ["list", "update", "get"]
    assert any("existing-id" in argument for argument in calls[1])
    assert result == {"file_id": "existing-id", "name": "daily.xlsx", "link": "https://drive/existing"}


def test_gws_update_retries_quota_then_verifies_remote_checksum(monkeypatch, tmp_path: Path) -> None:
    workbook = tmp_path / "daily.xlsx"
    workbook.write_bytes(b"verified workbook")
    calls: list[list[str]] = []
    responses = [
        SimpleNamespace(returncode=0, stdout='{"files":[{"id":"id-1","name":"daily.xlsx"}]}', stderr=""),
        SimpleNamespace(returncode=1, stdout="", stderr="429 rate limit exceeded"),
        SimpleNamespace(returncode=0, stdout='{"id":"id-1","name":"daily.xlsx"}', stderr=""),
        SimpleNamespace(returncode=0, stdout=json.dumps({
            "id": "id-1", "name": "daily.xlsx", "mimeType": drive_upload.XLSX_MIME,
            "size": str(workbook.stat().st_size), "md5Checksum": hashlib.md5(b"verified workbook").hexdigest(),
            "parents": ["folder-id"], "trashed": False,
        }), stderr=""),
    ]
    waits: list[int] = []

    def fake_run(command: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(command)
        return responses.pop(0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(drive_upload.time, "sleep", waits.append)

    result = drive_upload._upload_via_gws(workbook, "folder-id", "daily.xlsx")

    assert result["file_id"] == "id-1"
    assert waits == [65]
    assert [call[3] for call in calls] == ["list", "update", "update", "get"]


def test_remote_verification_detects_wrong_content_or_folder(tmp_path: Path) -> None:
    workbook = tmp_path / "daily.xlsx"
    workbook.write_bytes(b"expected")
    valid = {
        "mimeType": drive_upload.XLSX_MIME,
        "size": str(workbook.stat().st_size),
        "md5Checksum": hashlib.md5(b"expected").hexdigest(),
        "parents": ["folder-id"],
        "trashed": False,
    }
    assert drive_upload._file_matches_local(valid, workbook, "folder-id")
    assert not drive_upload._file_matches_local({**valid, "parents": ["other-folder"]}, workbook, "folder-id")
    assert not drive_upload._file_matches_local({**valid, "md5Checksum": "wrong"}, workbook, "folder-id")
