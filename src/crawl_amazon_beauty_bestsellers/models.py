from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ListEntry:
    run_id: str
    fetched_at: str
    node_id: str
    node_path: str
    page: int
    rank: int
    asin: str
    title: str
    url: str
    image_url: str = ""
    rating: float | None = None
    ratings_count: int | None = None
    price_amount: float | None = None
    price_currency: str | None = None
    price_raw: str = ""
    offers_text: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProductDetail:
    asin: str
    fetched_at: str
    run_id: str
    marketplace: str = "us"
    title: str = ""
    brand: str = ""
    manufacturer: str = ""
    model_number: str = ""
    seller_name: str = ""
    ships_from: str = ""
    buy_box_price: float | None = None
    buy_box_currency: str | None = None
    buy_box_raw: str = ""
    list_price_amount: float | None = None
    list_price_raw: str = ""
    availability: str = ""
    date_first_available: str = ""
    bsr_main_rank: int | None = None
    bsr_main_category: str = ""
    bsr_other: list[dict[str, Any]] = field(default_factory=list)
    rating: float | None = None
    ratings_count: int | None = None
    ratings_histogram: dict[str, int] = field(default_factory=dict)
    overview: dict[str, str] = field(default_factory=dict)
    specs: dict[str, str] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    ingredients: str = ""
    safety_info: str = ""
    directions: str = ""
    description_head: str = ""
    image_urls: list[str] = field(default_factory=list)
    variants: list[dict[str, Any]] = field(default_factory=list)
    variants_count: int = 0
    price_source: str = ""
    parse_warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CategoryNode:
    node_id: str
    name: str
    path: str
    parent_id: str | None = None


def dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, default=str)
