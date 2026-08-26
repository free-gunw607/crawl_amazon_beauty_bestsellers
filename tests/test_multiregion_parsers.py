from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from crawl_amazon_beauty_bestsellers.parsers.bestseller_list import (
    STARS_PATTERN,
    _price_from_raw,
)
from crawl_amazon_beauty_bestsellers.parsers.product_detail import _parse_bsr
from bs4 import BeautifulSoup


def test_stars_multilocale():
    assert STARS_PATTERN.search("4.6 out of 5 stars").group(1) == "4.6"
    assert STARS_PATTERN.search("4,7 sur 5 étoiles").group(1).replace(",", ".") == "4.7"
    assert STARS_PATTERN.search("4,4 von 5 Sternen").group(1).replace(",", ".") == "4.4"
    assert STARS_PATTERN.search("4,3 de 5 estrellas").group(1).replace(",", ".") == "4.3"


def test_price_formats():
    assert _price_from_raw("KRW 20,923") == (20923.0, "KRW")
    assert _price_from_raw("31.454 KRW") == (31454.0, "KRW")
    assert _price_from_raw("13 083 KRW") == (13083.0, "KRW")
    assert _price_from_raw("€19.45")[1] == "EUR"
    assert _price_from_raw("12,34 €") == (12.34, "EUR")
    assert _price_from_raw("£8.99") == (8.99, "GBP")
    assert _price_from_raw("$12.99") == (12.99, "USD")


def _bsr_soup(label: str) -> BeautifulSoup:
    html = f'<div id="detailBullets_feature_div"><li><span class="a-list-item">{label}</span></li></div>'
    return BeautifulSoup(html, "lxml")


def test_bsr_english():
    rank, cat, others = _parse_bsr(_bsr_soup(
        "Best Sellers Rank: #1,245 in Beauty & Personal Care (#12 in Skin Care)"
    ))
    assert rank == 1245
    assert cat.startswith("Beauty")


def test_bsr_german():
    rank, cat, _ = _parse_bsr(_bsr_soup(
        "Amazon Bestseller-Rang: Nr. 1.245 in Beauty (Nr. 12 in Hautpflege)"
    ))
    assert rank == 1245
    assert "Beauty" in cat


def test_bsr_french():
    rank, cat, _ = _parse_bsr(_bsr_soup(
        "Classement des meilleures ventes d'Amazon : 5.432 en Beauté et Parfum"
    ))
    assert rank == 5432
    assert "Beauté" in cat


def test_bsr_spanish():
    rank, _, _ = _parse_bsr(_bsr_soup(
        "Clasificación en los más vendidos de Amazon: nº1.234 en Belleza"
    ))
    assert rank == 1234
