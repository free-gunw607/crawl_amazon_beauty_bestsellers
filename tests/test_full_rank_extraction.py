from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers.parsers.bestseller_list import parse_list_page, parse_recs_list

SAMPLE = """
<div data-asin="B1111111111">
  <span class="zg-bdg-text">#1</span>
  <img alt="Alpha Product" src="x.jpg">
  <a class="a-link-normal" href="/dp/B1111111111"><span>Alpha Product</span></a>
  <span class="a-icon-alt">4.5 out of 5 stars</span>
  <a class="a-size-small a-link-normal" href="#">12,345 ratings</a>
  <span class="p13n-sc-price">$19.99</span>
</div>
<div data-asin="B2222222222">
  <span class="zg-bdg-text">#2</span>
  <img alt="Beta Product" src="y.jpg">
  <span class="a-icon-alt">4.0 out of 5 stars</span>
</div>
<div data-client-recs-list='[{"id": "B1111111111", "metadataMap": {"render.zg.rank": "1"}},
 {"id": "B2222222222", "metadataMap": {"render.zg.rank": "2"}},
 {"id": "B3333333333", "metadataMap": {"render.zg.rank": "3"}},
 {"id": "B4444444444", "metadataMap": {"render.zg.rank": "4"}}]'></div>
"""


def test_parse_recs_list_extracts_all():
    recs = parse_recs_list(SAMPLE)
    assert recs == [
        ("B1111111111", 1),
        ("B2222222222", 2),
        ("B3333333333", 3),
        ("B4444444444", 4),
    ]


def test_merge_metadata_only_rows():
    entries = parse_list_page(SAMPLE, "11060451", "beauty", 1, "2026-08-26T12:00:00+0900", "run_x")
    by_asin = {e.asin: e for e in entries}
    assert set(by_asin) == {"B1111111111", "B2222222222", "B3333333333", "B4444444444"}
    assert len(entries) == 4
    alpha = by_asin["B1111111111"]
    assert alpha.title == "Alpha Product"
    assert alpha.price_amount == 19.99
    assert alpha.price_currency == "USD"
    assert "metadata_only" not in alpha.parse_warnings
    ghost = by_asin["B3333333333"]
    assert ghost.title == ""
    assert ghost.rank == 3
    assert "metadata_only" in ghost.parse_warnings
    assert [e.rank for e in sorted(entries, key=lambda e: e.rank)] == [1, 2, 3, 4]


def test_recs_rank_overrides_dom():
    entries = parse_list_page(
        SAMPLE.replace("#1", "#9").replace("#2", "#8"),
        "11060451", "beauty", 1, "2026-08-26T12:00:00+0900", "run_y",
    )
    by_asin = {e.asin: e for e in entries}
    assert by_asin["B1111111111"].rank == 1
    assert by_asin["B2222222222"].rank == 2


def test_no_recs_attr_still_parses():
    html = SAMPLE.split("data-client-recs-list")[0]
    entries = parse_list_page(html, "11060451", "beauty", 1, "2026-08-26T12:00:00+0900", "run_z")
    assert len(entries) == 2
