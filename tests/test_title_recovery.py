from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import enrich_titles_until_complete as title_recovery
from crawl_amazon_beauty_bestsellers.http_client import CaptchaBlocked


def test_title_recovery_reaudits_and_retries_only_until_live_sheet_is_complete(monkeypatch) -> None:
    audits = iter([
        (99, 100, [("94", "B0CC1CHN7K")]),
        (99, 100, [("94", "B0CC1CHN7K")]),
        (100, 100, []),
    ])
    fills: list[list[tuple[str, str]]] = []
    sleeps: list[int] = []
    monkeypatch.setattr(title_recovery, "_sheet_title_count", lambda _region, _env: next(audits))

    def fill(_region, missing, _markets, max_items):
        fills.append(list(missing))
        assert max_items == len(missing)
        return 1

    monkeypatch.setattr(title_recovery, "_fallback_marketplace_titles", fill)
    monkeypatch.setattr(title_recovery.time, "sleep", sleeps.append)

    result = title_recovery._recover_region_titles(
        "us", max_rounds=4, sleep_sec=10, max_sleep_sec=60,
        markets=["de", "uk"], env={},
    )

    assert result["titled"] == 100
    assert result["missing"] == 0
    assert len(fills) == 2
    assert sleeps == [10]


def test_title_recovery_stops_immediately_on_amazon_block(monkeypatch) -> None:
    monkeypatch.setattr(title_recovery, "_sheet_title_count", lambda _region, _env: (99, 100, [("94", "B0CC1CHN7K")]))

    def blocked(*_args, **_kwargs):
        raise CaptchaBlocked("https://www.amazon.com/dp/B0CC1CHN7K")

    monkeypatch.setattr(title_recovery, "_fallback_marketplace_titles", blocked)

    result = title_recovery._recover_region_titles(
        "us", max_rounds=4, sleep_sec=10, max_sleep_sec=60,
        markets=["de", "uk"], env={},
    )

    assert result["missing"] == 1
    assert result["blocked"]
    assert len(result["rounds"]) == 1
