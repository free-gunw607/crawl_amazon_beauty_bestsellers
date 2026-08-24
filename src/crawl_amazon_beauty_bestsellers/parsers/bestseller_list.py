from __future__ import annotations

import re

from bs4 import BeautifulSoup, Tag

from ..models import ListEntry

RANK_PATTERN = re.compile(r"#(\d+)")
STARS_PATTERN = re.compile(r"([\d.]+) out of 5 stars", re.I)
COUNT_PATTERN = re.compile(r"^([\d,]+)$")
PRICE_PATTERN = re.compile(r"(?:US)?\$\s?([\d,]+\.\d{2})|[A-Z]{3}\s?([\d,]+(?:\.\d+)?)")
OFFERS_PATTERN = re.compile(r"\d+\s+offers?\s+from\s+.+", re.I)


def _item_containers(soup: BeautifulSoup) -> list[Tag]:
    containers: list[Tag] = []
    seen_asins: set[str] = set()
    for el in soup.select("div[data-asin]"):
        asin = (el.get("data-asin") or "").strip()
        if not asin:
            continue
        inner = el.select_one("div[data-asin]")
        if inner is not None:
            continue
        if asin in seen_asins:
            continue
        seen_asins.add(asin)
        containers.append(el)
    return containers


def _text(el: Tag | None) -> str:
    return el.get_text(" ", strip=True) if el is not None else ""


def _parse_rank(item: Tag) -> int | None:
    badge = item.select_one("span.zg-bdg-text")
    if badge is not None:
        match = RANK_PATTERN.search(_text(badge))
        if match:
            return int(match.group(1))
    return None


def _parse_title(item: Tag) -> tuple[str, str, str]:
    img = item.find("img", src=True)
    title = (img.get("alt") or "").strip() if img is not None else ""
    image_url = img["src"] if img is not None else ""
    if not title:
        for selector in (
            "a.a-link-normal span.zg-text-center-align ~ span",
            "span._cDEzb_p13n-sc-css-line-clamp-3",
            "span._cDEzb_p13n-sc-css-line-clamp-4",
            "a.a-link-normal > span",
        ):
            candidate = item.select_one(selector)
            if candidate is not None and _text(candidate):
                title = _text(candidate)
                break
    link = item.select_one("a.a-link-normal[href*='/dp/']")
    href = link["href"].split("?")[0] if link is not None and link.has_attr("href") else ""
    url = f"https://www.amazon.com{href}" if href.startswith("/") else href
    return title, image_url, url


def _parse_rating_and_count(item: Tag) -> tuple[float | None, int | None]:
    rating: float | None = None
    count: int | None = None
    alt = item.select_one("span.a-icon-alt")
    if alt is not None:
        match = STARS_PATTERN.search(_text(alt))
        if match:
            rating = float(match.group(1))
    if rating is None:
        star = item.select_one("i.a-icon-star-small") or item.select_one("i.a-icon-star")
        if star is not None:
            match = STARS_PATTERN.search(_text(star))
            if match:
                rating = float(match.group(1))
    for anchor in item.select("a.a-size-small.a-link-normal"):
        text = _text(anchor).replace("ratings", "").strip()
        match = COUNT_PATTERN.match(text)
        if match:
            count = int(match.group(1).replace(",", ""))
            break
    if count is None:
        for span in item.find_all(string=COUNT_PATTERN):
            count = int(span.strip().replace(",", ""))
            break
    return rating, count


def _extract_price(item: Tag) -> tuple[float | None, str | None, str]:
    for price_el in item.select(
        "span._cDEzb_p13n-sc-price_3mJ9Z, span.p13n-sc-price, span.a-price span.a-offscreen"
    ):
        raw = _text(price_el)
        if not raw:
            continue
        amount, currency = _price_from_raw(raw)
        if amount is not None:
            return amount, currency, raw
    whole = item.select_one("span.a-price-whole")
    frac = item.select_one("span.a-price-fraction")
    symbol_el = item.select_one("span.a-price-symbol")
    if whole is not None:
        try:
            value = float(whole.get_text(strip=True).replace(",", "") + "." + (_text(frac) or "0"))
            currency = _currency_from_symbol(_text(symbol_el))
            raw = _text(symbol_el) + _text(whole) + _text(frac)
            return value, currency, raw
        except ValueError:
            pass
    return None, None, ""


def _currency_from_symbol(symbol: str) -> str:
    return {"$": "USD", "₩": "KRW", "¥": "JPY", "£": "GBP", "€": "EUR"}.get(symbol.strip(), symbol.strip() or "")


def _price_from_raw(raw: str) -> tuple[float | None, str | None]:
    cleaned = raw.replace(",", "").strip()
    dollar_match = re.search(r"\$([\d.]+)", cleaned)
    if dollar_match:
        try:
            return float(dollar_match.group(1)), "USD"
        except ValueError:
            return None, None
    krw_match = re.search(r"KRW\s?([\d.]+)|₩\s?([\d,]+)", raw)
    if krw_match:
        value_str = (krw_match.group(1) or krw_match.group(2)).replace(",", "")
        try:
            return float(value_str), "KRW"
        except ValueError:
            return None, None
    return None, None


def parse_list_page(
    html: str,
    node_id: str,
    node_path: str,
    page: int,
    fetched_at: str,
    run_id: str,
) -> list[ListEntry]:
    soup = BeautifulSoup(html, "lxml")
    entries: dict[str, ListEntry] = {}
    fallback_rank = 0
    for item in _item_containers(soup):
        asin = (item.get("data-asin") or "").strip()
        if not asin:
            continue
        fallback_rank += 1
        warnings: list[str] = []
        title, image_url, url = _parse_title(item)
        if not title:
            warnings.append("title_missing")
        rank = _parse_rank(item)
        if rank is None:
            rank = fallback_rank + (page - 1) * 50
            warnings.append("rank_fallback")
        rating, count = _parse_rating_and_count(item)
        if rating is None:
            warnings.append("rating_missing")
        amount, currency, raw = _extract_price(item)
        if amount is None:
            warnings.append("price_missing")
        offers_text = ""
        for string in item.stripped_strings:
            if OFFERS_PATTERN.fullmatch(string):
                offers_text = string
                break
        entry = ListEntry(
            run_id=run_id,
            fetched_at=fetched_at,
            node_id=node_id,
            node_path=node_path,
            page=page,
            rank=rank,
            asin=asin,
            title=title,
            url=url,
            image_url=image_url,
            rating=rating,
            ratings_count=count,
            price_amount=amount,
            price_currency=currency,
            price_raw=raw,
            offers_text=offers_text,
            parse_warnings=warnings,
        )
        entries.setdefault(asin, entry)
    return sorted(entries.values(), key=lambda e: e.rank)


def detect_max_pages(html: str) -> int:
    pages = {1}
    for anchor in BeautifulSoup(html, "lxml").find_all("a", href=True):
        match = re.search(r"[?&]pg=(\d+)", anchor["href"])
        if match:
            pages.add(int(match.group(1)))
    return max(pages)
