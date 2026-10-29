from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers import root_publish


@pytest.mark.parametrize("backend", ["gws", "sa"])
def test_shared_views_mode_does_not_touch_regions_or_append_history(monkeypatch, backend: str) -> None:
    monkeypatch.setenv("AMZ_BS_ROOT_BACKEND", backend)
    monkeypatch.setattr(root_publish, "ensure_root_spreadsheet", lambda *_args, **_kwargs: "sheet-id")
    monkeypatch.setattr(root_publish, "_shared_root_tabs", lambda *_args: {"trend_14d": [["header"], ["row"]]})
    monkeypatch.setattr(root_publish, "_grid_resize_requests", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(root_publish, "root_history_rows", lambda *_args: (_ for _ in ()).throw(AssertionError("history append called")))
    calls = []
    if backend == "gws":
        monkeypatch.setattr(root_publish, "_sheet_meta_gws", lambda _sheet_id: {})
        monkeypatch.setattr(root_publish, "_gws", lambda args, params, body=None: calls.append((args, body)) or {})
        token = None
    else:
        monkeypatch.setattr(root_publish, "_sheet_meta_sa", lambda *_args: {})
        monkeypatch.setattr(root_publish, "_api", lambda *args, **kwargs: calls.append((args, kwargs)) or {})
        token = "test-token"

    result = root_publish.publish_root_region(object(), object(), "es", token=token, shared_views_only=True)

    assert result["shared_views"] == ["trend_14d"]
    assert result["published_tabs"] == 1
    assert len(calls) == 3  # in-progress marker, data, completion stamp
    if backend == "gws":
        assert all(call[0][-1] == "batchUpdate" for call in calls)
    else:
        assert [call[1]["body"]["data"][0]["range"] for call in calls] == [
            "'trend_14d'!A1", "'trend_14d'!A2", "'trend_14d'!A1",
        ]
