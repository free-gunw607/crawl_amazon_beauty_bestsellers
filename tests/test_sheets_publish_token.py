from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from crawl_amazon_beauty_bestsellers.sheets_publish import (
    SheetsPublishError,
    _publish_rest,
    oauth_access_token,
    oauth_ready,
)


def test_oauth_ready_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("GSHEET_SYNC_DIR", str(tmp_path))
    assert oauth_ready() is False


def test_oauth_access_token_refresh_flow(tmp_path, monkeypatch):
    d = tmp_path
    (d / "client_secret.json").write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))
    (d / "refresh_token.json").write_text(json.dumps({"refresh_token": "rtok"}))

    calls = {}

    def fake_post(url, data=None, timeout=None):
        calls["url"] = url
        calls["data"] = data
        class R:
            status_code = 200
            text = ""
            def json(self):
                return {"access_token": "atok"}
        return R()

    import requests as requests_mod
    monkeypatch.setattr(requests_mod, "post", fake_post)
    token = oauth_access_token(d)
    assert token == "atok"
    assert calls["url"] == "https://oauth2.googleapis.com/token"
    assert calls["data"]["refresh_token"] == "rtok"
    assert calls["data"]["client_id"] == "cid"


def test_oauth_access_token_error_raises(tmp_path, monkeypatch):
    (tmp_path / "client_secret.json").write_text(json.dumps({"installed": {"client_id": "cid", "client_secret": "csec"}}))
    (tmp_path / "refresh_token.json").write_text('{"refresh_token": "x"}')

    def fail_post(url, data=None, timeout=None):
        class R:
            status_code = 400
            text = "bad grant"
            def json(self):
                return {}
        return R()

    import requests as requests_mod
    monkeypatch.setattr(requests_mod, "post", fail_post)
    with pytest.raises(SheetsPublishError):
        oauth_access_token(tmp_path)


def test_publish_rest_writes_tabs(tmp_path, monkeypatch):
    meta = {
        "T1": {"sheet_id": 1, "rows": 1000, "cols": 26},
        "trend_14d": {"sheet_id": 2, "rows": 1000, "cols": 26},
    }

    seen = []

    def fake_get(url, params=None, headers=None, timeout=None):
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
            def json(self):
                return {"sheets": [
                    {"properties": {"title": t, "sheetId": m["sheet_id"],
                                    "gridProperties": {"rowCount": m["rows"], "columnCount": m["cols"]}}}
                    for t, m in meta.items()
                ]}
        seen.append(("GET", url))
        return R()

    def fake_post(url, json=None, headers=None, timeout=None, params=None, data=None):
        class R:
            status_code = 200
            def raise_for_status(self):
                pass
        seen.append(("POST", url))
        return R()

    import requests as requests_mod
    monkeypatch.setattr(requests_mod, "get", fake_get)
    monkeypatch.setattr(requests_mod, "post", fake_post)

    tabs = {"T1": [["h1", "h2"], ["a", "b"]], "trend_14d": [["day"], ["2026-08-26"]]}
    out = _publish_rest("SHEETID", tabs, "tok123", "token")

    assert out == {"backend": "token", "tabs": 2, "rows": 4}
    posts = [u for k, u in seen if k == "POST"]
    assert any(":batchUpdate" in u and "spreadsheets/SHEETID" in u for u in posts)
    assert any(u.endswith(":clear") or "clear" in u for u in posts)
