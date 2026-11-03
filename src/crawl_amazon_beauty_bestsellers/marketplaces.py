"""Canonical marketplace metadata used by collectors and delivery surfaces.

Add or retire a country here first. Exporters and scheduled runners derive their
country codes from this registry; public-site display metadata is emitted in the
existing market objects so older feed fields remain unchanged.
"""
from __future__ import annotations

from copy import deepcopy


MARKETPLACE_DEFINITIONS = (
    {"code": "us", "name": "United States", "flag": "🇺🇸", "display_order": 1, "base_url": "https://www.amazon.com",
     "timezone": "America/New_York", "currency_pref": "USD", "language": "en-US", "url_style": "gp"},
    {"code": "de", "name": "Germany", "flag": "🇩🇪", "display_order": 3, "base_url": "https://www.amazon.de",
     "timezone": "Europe/Berlin", "currency_pref": "USD", "language": "en-US", "url_style": "gp"},
    {"code": "uk", "name": "United Kingdom", "flag": "🇬🇧", "display_order": 2, "base_url": "https://www.amazon.co.uk",
     "timezone": "Europe/London", "currency_pref": "USD", "language": "en-US", "url_style": "legacy"},
    {"code": "fr", "name": "France", "flag": "🇫🇷", "display_order": 4, "base_url": "https://www.amazon.fr",
     "timezone": "Europe/Paris", "currency_pref": "USD", "language": "en-US", "url_style": "gp"},
    {"code": "es", "name": "Spain", "flag": "🇪🇸", "display_order": 5, "base_url": "https://www.amazon.es",
     "timezone": "Europe/Madrid", "currency_pref": "USD", "language": "en-US", "url_style": "gp"},
    {"code": "it", "name": "Italy", "flag": "🇮🇹", "display_order": 6, "base_url": "https://www.amazon.it",
     "timezone": "Europe/Rome", "currency_pref": "EUR", "language": "it-IT", "url_style": "gp"},
)

MARKETPLACE_CODES = tuple(item["code"] for item in MARKETPLACE_DEFINITIONS)
MARKETPLACE_META = {item["code"]: item for item in MARKETPLACE_DEFINITIONS}
# Keep old cross-market macro tabs scoped to the original five until owners
# approve a separate schema/analyst migration.
LEGACY_AGGREGATE_MARKETS = ("us", "de", "uk", "fr", "es")


def default_marketplaces() -> list[dict[str, str]]:
    """Return independent dicts so callers can safely customize settings."""
    return deepcopy(list(MARKETPLACE_DEFINITIONS))
