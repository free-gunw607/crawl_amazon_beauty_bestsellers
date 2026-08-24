from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup, Tag

from ..models import ProductDetail

HISTOGRAM_PATTERN = re.compile(r"(\d+)\s+percent of reviews have\s+(\d)\s+star", re.I)
BSR_PATTERN = re.compile(r"#(\d[\d,]*)\s+in\s+([^(#\n]+)")
HIRES_PATTERN = re.compile(r'"hiRes"\s*:\s*"(https://[^"]+)"')
LARGE_IMG_PATTERN = re.compile(r'"large"\s*:\s*"(https://[^"]+)"')


def _text(el: Tag | None) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def _clean_brand(raw: str) -> str:
    cleaned = raw.strip()
    cleaned = re.sub(r"^Visit the\s+", "", cleaned)
    cleaned = re.sub(r"\s+Store$", "", cleaned)
    cleaned = re.sub(r"^Brand:\s*", "", cleaned)
    return cleaned.strip()


def _kv_from_table(table: Tag) -> dict[str, str]:
    result: dict[str, str] = {}
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"])
        if len(cells) >= 2:
            key = _text(cells[0]).rstrip(":")
            value = _text(cells[1])
            if key and value and key.lower() != "customer reviews":
                result.setdefault(key, value)
    return result


def _collect_spec_tables(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for table_id in (
        "productDetails_techSpec_section_1",
        "productDetails_techSpec_section_2",
        "productDetails_detailBullets_section1",
        "productDetails_detailBullets_section2",
    ):
        table = soup.find("table", id=table_id)
        if table is not None:
            specs.update(_kv_from_table(table))
    overview = soup.select_one("#productOverview_feature_div table")
    if overview is not None:
        specs.update(_kv_from_table(overview))
    for table in soup.select("table.a-keyvalue"):
        specs.update(_kv_from_table(table))
    prod_details = soup.select_one("#prodDetails")
    if prod_details is not None:
        for table in prod_details.find_all("table"):
            specs.update(_kv_from_table(table))
    return specs


def _collect_new_style_sections(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for section in soup.select("section#product-specification-section, section[class*='specification']"):
        heading = _text(section.select_one("h2, h3"))
        for row in section.select("div.a-keyvalue, table"):
            if row.name == "table":
                specs.update(_kv_from_table(row))
            else:
                items = list(row.select("div"))
                for i in range(0, len(items) - 1, 2):
                    key = _text(items[i]).rstrip(":")
                    value = _text(items[i + 1])
                    if key and value:
                        specs.setdefault(f"{heading}:{key}" if heading else key, value)
    generic_tables = soup.select("div#all-details table, div#detailBullets_feature_div table")
    for table in generic_tables:
        specs.update(_kv_from_table(table))
    return specs


def _collect_detail_bullets(soup: BeautifulSoup) -> dict[str, str]:
    bullets: dict[str, str] = {}
    container = soup.select_one("#detailBullets_feature_div")
    if container is not None:
        for li in container.select("li"):
            spans = li.find_all("span")
            if not spans:
                continue
            full_text = _text(spans[0])
            if ":" in full_text:
                key = full_text.split(":", 1)[0].strip()
                value = _text(spans[-1]) if len(spans) > 1 else full_text.split(":", 1)[1].strip()
            else:
                key, value = "", ""
            if key and value:
                bullets.setdefault(key, value)
    return bullets


def _parse_bsr(soup: BeautifulSoup) -> tuple[int | None, str, list[dict[str, Any]]]:
    text_block = ""
    for li in soup.select("#detailBullets_feature_div li"):
        if "Best Sellers Rank" in li.get_text():
            text_block = _text(li)
            break
    if not text_block:
        for row in soup.select("tr"):
            if "Best Sellers Rank" in _text(row):
                text_block = _text(row)
                break
    if not text_block:
        for el in soup.find_all(string=re.compile("Best Sellers Rank")):
            parent = el.find_parent(["div", "section", "td", "li"])
            if parent is not None:
                text_block = _text(parent)
                break
    matches = BSR_PATTERN.findall(text_block.replace(",", ""))
    if not matches:
        return None, "", []
    main_rank = int(matches[0][0])
    main_category = matches[0][1].strip()
    others = [
        {"rank": int(rank), "category": category.strip()}
        for rank, category in matches[1:]
    ]
    return main_rank, main_category, others


def _parse_price_blocks(soup: BeautifulSoup) -> tuple[float | None, str | None, str, float | None, str, str]:
    from .bestseller_list import _price_from_raw

    buy_amount: float | None = None
    buy_currency: str | None = None
    buy_raw = ""
    for container in soup.find_all(id=re.compile(r"corePriceDisplay_desktop_feature_div|corePrice_feature_div")):
        offscreen = container.select_one("span.a-price span.a-offscreen")
        if offscreen is None:
            offscreen = container.select_one(".aok-offscreen")
        if offscreen is not None:
            raw = _text(offscreen)
            amount, currency = _price_from_raw(raw.split(" with ")[0].strip())
            if amount is not None:
                buy_amount, buy_currency, buy_raw = amount, currency, raw
                break
    if buy_amount is None:
        inside = soup.select_one("#price_inside_buybox")
        if inside is not None:
            raw = _text(inside)
            amount, currency = _price_from_raw(raw)
            buy_amount, buy_currency, buy_raw = amount, currency, raw
    list_amount: float | None = None
    list_raw = ""
    for scope in (
        soup.select("#corePriceDisplay_desktop_feature_div [data-a-strike=true]")
        + soup.select("#corePrice_feature_div [data-a-strike=true]"),
        soup.select("[data-a-strike=true]"),
    ):
        for strike in scope:
            candidate = _text(strike).replace("List:", "").strip()
            if candidate.startswith("null") or not candidate:
                continue
            from .bestseller_list import _price_from_raw

            amount, _ = _price_from_raw(candidate)
            if amount is not None:
                list_amount, list_raw = amount, candidate
                break
        if list_amount is not None:
            break
    return buy_amount, buy_currency, buy_raw, list_amount, list_raw


def _parse_availability(soup: BeautifulSoup) -> str:
    availability = _text(soup.select_one("#availability"))
    return re.sub(r"\s+", " ", availability)


def _parse_variants(soup: BeautifulSoup) -> list[dict[str, Any]]:
    variants: dict[str, dict[str, Any]] = {}
    twister = soup.select_one("#twister, form#twister")
    if twister is not None:
        for link in twister.select("a[href*='/dp/']"):
            href = link["href"]
            asin_match = re.search(r"/dp/([A-Z0-9]{10})", href)
            if not asin_match:
                continue
            asin = asin_match.group(1)
            label = _text(link) or (link.get("title") or "")
            variants.setdefault(asin, {"asin": asin, "label": label})
    data_asins = re.findall(r'"dimensionValuesDisplayData"\s*:\s*(\{[^}]+\})', soup.decode())
    for block in data_asins:
        try:
            parsed = json.loads(block)
            for asin, dims in parsed.items():
                variants.setdefault(asin, {"asin": asin, "label": ", ".join(dims)})
        except (json.JSONDecodeError, AttributeError):
            continue
    return list(variants.values())


def _parse_histogram(soup: BeautifulSoup) -> dict[str, int]:
    histogram: dict[str, int] = {}
    container = soup.select_one("#histogramTable")
    if container is None:
        return histogram
    for anchor in container.find_all("a", attrs={"aria-label": True}):
        match = HISTOGRAM_PATTERN.search(anchor["aria-label"])
        if match:
            histogram[f"{match.group(2)}star"] = int(match.group(1))
    return histogram


def parse_product_detail(html: str, asin: str, fetched_at: str, run_id: str) -> ProductDetail:
    soup = BeautifulSoup(html, "lxml")
    warnings: list[str] = []

    title_el = soup.select_one("#productTitle")
    title = _text(title_el)
    if not title:
        warnings.append("title_missing")

    brand = ""
    byline = soup.select_one("#bylineInfo")
    if byline is not None:
        brand = _clean_brand(_text(byline))

    specs: dict[str, str] = {}
    specs.update(_collect_spec_tables(soup))
    specs.update(_collect_new_style_sections(soup))
    bullets = _collect_detail_bullets(soup)

    manufacturer = specs.get("Manufacturer", "") or bullets.get("Manufacturer", "")
    model_number = specs.get("Model Number", "") or bullets.get("Item model number", "")
    date_first_available = bullets.get("Date First Available", "") or specs.get("Date First Available", "")
    ships_from = ""

    bsr_main_rank, bsr_main_category, bsr_other = _parse_bsr(soup)
    if bsr_main_rank is None:
        warnings.append("bsr_missing")

    rating: float | None = None
    ratings_count: int | None = None
    acr_alt = soup.select_one("#averageCustomerReviews span.a-icon-alt") or soup.select_one(
        "#acrPopover span.a-icon-alt"
    )
    if acr_alt is not None:
        stars_match = re.search(r"([\d.]+) out of 5 stars", _text(acr_alt))
        if stars_match:
            rating = float(stars_match.group(1))
    acr_count = soup.select_one("#acrCustomerReviewText")
    if acr_count is not None:
        count_match = re.search(r"([\d,]+)", _text(acr_count))
        if count_match:
            ratings_count = int(count_match.group(1).replace(",", ""))

    buy_amount, buy_currency, buy_raw, list_amount, list_raw = _parse_price_blocks(soup)
    price_source = ""
    if buy_amount is not None:
        price_source = "buy_box"
    elif list_amount is not None:
        price_source = "list_price_only"

    features: list[str] = []
    feature_container = soup.select_one("#feature-bullets")
    if feature_container is not None:
        features = [_text(li) for li in feature_container.select("li span.a-list-item") if _text(li)]

    important_info: dict[str, str] = {}
    info_container = soup.select_one("#important-information")
    if info_container is None:
        info_container = soup.select_one("#importantInformation, div#important-information")
    if info_container is not None:
        for heading in info_container.select("h4, h5"):
            name = _text(heading)
            content = _text(heading.find_next_sibling(class_=re.compile("content"))) or _text(heading.find_next("div"))
            if name and content:
                important_info[name] = content

    description_head = ""
    desc_el = soup.select_one("#productDescription p")
    if desc_el is not None:
        description_head = _text(desc_el)[:1000]

    image_urls = HIRES_PATTERN.findall(html)
    if not image_urls:
        image_urls = LARGE_IMG_PATTERN.findall(html)[:6]

    variants = _parse_variants(soup)

    seller_name = ""
    seller_el = soup.select_one("#sellerProfileTriggerId")
    if seller_el is not None:
        seller_name = _text(seller_el)
    if not seller_name:
        for el in soup.find_all(attrs={"offer-display-feature-name": "desktop-merchant-info"}):
            classes = el.get("class") or []
            if "offer-display-feature-text" not in classes:
                continue
            candidate = _text(el)
            match = re.search(r"(?:Shipper\s*/\s*Seller|Sold by)\s*:?\s*(.+)", candidate, re.I)
            value = (match.group(1) if match else candidate).strip()
            if value and value.lower() not in ("shipper / seller", "sold by"):
                seller_name = value
                break
    merchant_el = soup.select_one("#merchant-info")
    if not seller_name and merchant_el is not None:
        sold_match = re.search(r"sold by ([^.(]+)", _text(merchant_el), re.I)
        if sold_match:
            seller_name = sold_match.group(1).strip()

    detail = ProductDetail(
        asin=asin,
        fetched_at=fetched_at,
        run_id=run_id,
        title=title,
        brand=brand,
        manufacturer=manufacturer,
        model_number=model_number,
        seller_name=seller_name,
        ships_from=ships_from,
        buy_box_price=buy_amount,
        buy_box_currency=buy_currency,
        buy_box_raw=buy_raw,
        list_price_amount=list_amount,
        list_price_raw=list_raw,
        availability=_parse_availability(soup),
        date_first_available=date_first_available,
        bsr_main_rank=bsr_main_rank,
        bsr_main_category=bsr_main_category,
        bsr_other=bsr_other,
        rating=rating,
        ratings_count=ratings_count,
        ratings_histogram=_parse_histogram(soup),
        overview={},
        specs=specs,
        features=features,
        ingredients=important_info.get("Ingredients", ""),
        safety_info=important_info.get("Safety Information", ""),
        directions=important_info.get("Directions", ""),
        description_head=description_head,
        image_urls=image_urls[:8],
        variants=variants,
        variants_count=len(variants),
        price_source=price_source,
        parse_warnings=warnings,
    )
    if specs.get("ASIN") and specs["ASIN"] != asin:
        warnings.append("asin_mismatch_in_specs")
    return detail
