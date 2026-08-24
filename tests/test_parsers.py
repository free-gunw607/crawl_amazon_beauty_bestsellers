from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers.parsers import (
    extract_category_links,
    extract_current_path,
    parse_list_page,
    parse_product_detail,
)

LIST_HTML = """
<div id="zg"><div class="p13n-grid-content">
<div data-asin="B0TEST0001"><div>
<span class="zg-bdg-text">#1</span>
<a class="a-link-normal" href="/some-product/dp/B0TEST0001/ref=zg_bs_1?psc=1">
<img alt="Test Lotion 16 fl oz" src="https://m.media-amazon.com/images/I/61x._AC_UL300_.jpg"/>
<span>clamp text</span></a>
<i class="a-icon-star-small"><span class="a-icon-alt">4.5 out of 5 stars</span></i>
<a class="a-size-small a-link-normal" href="#"><span>12,345</span></a>
<span class="_cDEzb_p13n-sc-price_3mJ9Z">$9.97</span>
</div></div>
<div data-asin="B0TEST0002"><div>
<span class="zg-bdg-text">#2</span>
<a class="a-link-normal" href="/other/dp/B0TEST0002/ref=zg_bs_2">
<img alt="Test Serum" src="https://m.media-amazon.com/images/I/62y._AC_UL300_.jpg"/></a>
<i class="a-icon-star-small"><span class="a-icon-alt">4.0 out of 5 stars</span></i>
<a class="a-size-small a-link-normal" href="#"><span>999</span></a>
<span class="p13n-sc-price">KRW 20,905</span>
<span>1 offer from KRW 20,905</span>
</div></div>
</div></div>
"""

DETAIL_HTML = """
<div id="productTitle">Test Product Title Here</div>
<div id="bylineInfo">Visit the TestBrand Store</div>
<div id="averageCustomerReviews"><span class="a-icon-alt">4.6 out of 5 stars</span><span id="acrCustomerReviewText">30,486 ratings</span></div>
<div id="corePriceDisplay_desktop_feature_div" class="celwidget"><style>x{}</style>
<span class="a-price"><span class="a-offscreen">$9.97</span></span>
<span class="a-price a-text-price" data-a-strike="true"><span class="a-offscreen">$10.99</span></span>
</div>
<div id="availability"><span>In Stock</span></div>
<div id="detailBullets_feature_div"><ul>
<li><span class="a-list-item"><span>Manufacturer :
200e AmazonUs/TSTBRD</span><span>AmazonUs/TSTBRD</span></span></li>
<li><span class="a-list-item"><span>Date First Available :
200e January 5, 2024</span><span>January 5, 2024</span></span></li>
<li><span class="a-list-item"><span>Best Sellers Rank</span>
<span>#1 in Beauty & Personal Care (See Top 100) #2 in Body Lotions</span></span></li>
</ul></div>
<table class="a-keyvalue voyager-ns-desktop-table">
<tr><th>Brand Name</th><td>TestBrand</td></tr>
<tr><th>Item Weight</th><td>155 g</td></tr>
</table>
<div id="important-information"><h4>Ingredients</h4><div class="content">Water, Glycerin</div></div>
"""


def test_parse_list_page():
    entries = parse_list_page(LIST_HTML, "11060451", "Beauty > Skin Care", 1, "2026-08-25T00:00:00+0900", "r1")
    assert len(entries) == 2
    first = entries[0]
    assert first.asin == "B0TEST0001"
    assert first.rank == 1
    assert first.title == "Test Lotion 16 fl oz"
    assert first.price_amount == 9.97
    assert first.price_currency == "USD"
    assert first.rating == 4.5
    assert first.ratings_count == 12345
    second = entries[1]
    assert second.price_currency == "KRW"
    assert second.offers_text.startswith("1 offer from")
    assert second.parse_warnings == []


def test_parse_list_page_empty():
    entries = parse_list_page("<html><body>captcha api-services-support@amazon.com</body></html>", "n", "", 1, "t", "r")
    assert entries == []


def test_parse_product_detail():
    d = parse_product_detail(DETAIL_HTML, "B0TEST0999", "2026-08-25T00:00:00+0900", "r1")
    assert d.title == "Test Product Title Here"
    assert d.brand == "TestBrand"
    assert d.buy_box_price == 9.97 and d.buy_box_currency == "USD"
    assert d.list_price_amount == 10.99
    assert d.availability == "In Stock"
    assert d.manufacturer == "AmazonUs/TSTBRD"
    assert d.date_first_available.startswith("January 5, 2024")
    assert d.bsr_main_rank == 1
    assert d.bsr_main_category == "Beauty & Personal Care"
    assert d.bsr_other == [{"rank": 2, "category": "Body Lotions"}]
    assert d.rating == 4.6 and d.ratings_count == 30486
    assert d.ingredients == "Water, Glycerin"
    assert d.specs.get("Brand Name") == "TestBrand"


CATEGORY_HTML = """
<ul class="_p13n-zg-nav-tree-all_style_zg-browse-root__-jwNv">
<li><span class="a-list-item"><a href="/Best-Sellers/zgbs/ref=zg_bs_unv">Any Department</a></span></li>
<li><span class="a-list-item"><ul class="_p13n-zg-nav-tree-all_style_zg-browse-group__88fbz">
<li><span class="a-list-item"><a href="/Best-Sellers-Beauty/zgbs/beauty/ref=x">Beauty &amp; Personal Care</a></span></li>
<li><span class="a-list-item"><ul class="_p13n-zg-nav-tree-all_style_zg-browse-group__88fbz">
<li><span class="a-list-item"><span aria-current="page">Skin Care<span>(Current)</span></span></span></li>
<li><span class="a-list-item"><ul class="_p13n-zg-nav-tree-all_style_zg-browse-group__88fbz">
<li><span class="a-list-item"><a href="/Best-Sellers-Body/zgbs/beauty/11060521/ref=zg_bs_nav_2">Body</a></span></li>
<li><span class="a-list-item"><a href="/Best-Sellers-Eyes/zgbs/beauty/11061941/ref=zg_bs_nav_2">Eyes</a></span></li>
</ul></span></li>
</ul></span></li>
</ul></span></li>
</ul>
<a href="/same/zgbs/beauty/11060521/ref=zg_bs_pg_2?pg=2">Next page →</a>
"""


def test_extract_category_links():
    links = extract_category_links(CATEGORY_HTML)
    by_id = {c.node_id: c for c in links}
    assert set(by_id) == {"11060521", "11061941"}
    assert by_id["11060521"].path == "Beauty & Personal Care > Skin Care > Body"


def test_extract_current_path():
    assert extract_current_path(CATEGORY_HTML) == "Beauty & Personal Care > Skin Care"
