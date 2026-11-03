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


def test_service_account_updates_same_daily_xlsx_and_verifies_checksum(monkeypatch, tmp_path: Path) -> None:
    from google.oauth2 import service_account
    from googleapiclient import discovery
    from googleapiclient import http as google_http

    workbook = tmp_path / "daily.xlsx"
    workbook.write_bytes(b"service-account workbook")
    creds_file = tmp_path / "service-account.json"
    creds_file.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("GDRIVE_CREDS", str(creds_file))
    monkeypatch.setenv("AMZ_BS_DRIVE_BACKEND", "sa")
    monkeypatch.setenv("AMZ_BS_DRIVE_FOLDER_ID", "folder-id")

    scope_capture: list[list[str]] = []
    monkeypatch.setattr(
        service_account.Credentials, "from_service_account_info",
        lambda _info, scopes: scope_capture.append(scopes) or object(),
    )
    remote = {
        "id": "same-file", "name": workbook.name, "mimeType": drive_upload.XLSX_MIME,
        "size": str(workbook.stat().st_size),
        "md5Checksum": hashlib.md5(workbook.read_bytes()).hexdigest(),
        "parents": ["folder-id"], "trashed": False,
        "webViewLink": "https://drive.example/same-file",
    }
    calls: list[str] = []

    class Request:
        def __init__(self, payload):
            self.payload = payload

        def execute(self):
            return self.payload

    class Files:
        def list(self, **kwargs):
            calls.append("list")
            assert "'folder-id' in parents" in kwargs["q"]
            return Request({"files": [{"id": "same-file"}]})

        def update(self, **kwargs):
            calls.append("update")
            assert kwargs["fileId"] == "same-file"
            return Request(remote)

        def create(self, **_kwargs):
            raise AssertionError("idempotent update must not create a duplicate")

        def get(self, **kwargs):
            calls.append("get")
            assert kwargs["fileId"] == "same-file"
            return Request(remote)

    class Service:
        def files(self):
            return Files()

    monkeypatch.setattr(discovery, "build", lambda *_args, **_kwargs: Service())
    monkeypatch.setattr(google_http, "MediaFileUpload", lambda *args, **kwargs: (args, kwargs))

    result = drive_upload.upload_file(workbook)

    assert result == {"file_id": "same-file", "name": workbook.name, "link": "https://drive.example/same-file"}
    assert calls == ["list", "update", "get"]
    assert scope_capture == [["https://www.googleapis.com/auth/drive"]]


def test_service_account_drive_verification_checks_remote_bytes_and_parent(monkeypatch, tmp_path: Path) -> None:
    from google.oauth2 import service_account
    from googleapiclient import discovery

    workbook = tmp_path / "daily.xlsx"
    workbook.write_bytes(b"verified service-account workbook")
    creds_file = tmp_path / "service-account.json"
    creds_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(service_account.Credentials, "from_service_account_info", lambda *_args, **_kwargs: object())
    remote = {
        "id": "daily-file", "mimeType": drive_upload.XLSX_MIME,
        "size": str(workbook.stat().st_size), "md5Checksum": hashlib.md5(workbook.read_bytes()).hexdigest(),
        "parents": ["folder-id"], "trashed": False,
    }

    class Request:
        def execute(self):
            return remote

    class Files:
        def get(self, **kwargs):
            assert kwargs["fileId"] == "daily-file"
            return Request()

    class Service:
        def files(self):
            return Files()

    monkeypatch.setattr(discovery, "build", lambda *_args, **_kwargs: Service())

    assert drive_upload.verify_file(
        "daily-file", workbook, "folder-id",
        env={"AMZ_BS_DRIVE_BACKEND": "sa", "GDRIVE_CREDS": str(creds_file)},
    )
