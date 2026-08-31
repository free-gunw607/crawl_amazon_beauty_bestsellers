from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass
class AmazonConfig:
    base_url: str = "https://www.amazon.com"
    delivery_zip: str = "10001"
    marketplace_country: str = "US"
    currency_pref: str = "USD"
    language: str = "en-US"


@dataclass
class MarketplaceProfile:
    code: str
    base_url: str
    timezone: str
    currency_pref: str = "KRW"
    language: str = "en-US"
    url_style: str = "gp"

    @staticmethod
    def from_dict(payload: dict[str, Any]) -> "MarketplaceProfile":
        return MarketplaceProfile(
            code=str(payload["code"]).lower(),
            base_url=str(payload["base_url"]),
            timezone=str(payload["timezone"]),
            currency_pref=str(payload.get("currency_pref", "KRW")),
            language=str(payload.get("language", "en-US")),
            url_style=str(payload.get("url_style", "gp")),
        )


DEFAULT_MARKETPLACES = [
    {"code": "us", "base_url": "https://www.amazon.com", "timezone": "America/New_York", "currency_pref": "USD"},
    {"code": "uk", "base_url": "https://www.amazon.co.uk", "timezone": "Europe/London", "currency_pref": "USD", "url_style": "legacy"},
    {"code": "de", "base_url": "https://www.amazon.de", "timezone": "Europe/Berlin", "currency_pref": "USD"},
    {"code": "fr", "base_url": "https://www.amazon.fr", "timezone": "Europe/Paris", "currency_pref": "USD"},
    {"code": "es", "base_url": "https://www.amazon.es", "timezone": "Europe/Madrid", "currency_pref": "USD"},
]


@dataclass
class PolitenessConfig:
    min_delay_seconds: float = 1.5
    max_delay_seconds: float = 4.0
    max_attempts: int = 3
    request_timeout_seconds: int = 30
    category_gap_seconds: float = 8.0
    detail_delay_seconds: float = 1.0


@dataclass
class CrawlerConfig:
    list_pages: int = 2
    detail_top: int = 100
    save_raw_html: bool = False


@dataclass
class StorageConfig:
    db_path: str = "artifacts/db/bestsellers.sqlite"
    snapshots_dir: str = "artifacts/snapshots"
    details_dir: str = "artifacts/details"
    exports_dir: str = "artifacts/exports/xlsx"
    raw_dir: str = "artifacts/raw"
    runs_dir: str = ".agent/runs"


@dataclass
class ScheduleConfig:
    interval_minutes: int = 60


@dataclass
class DriveConfig:
    enabled: bool = False
    folder_id: str = ""


@dataclass
class Settings:
    amazon: AmazonConfig = field(default_factory=AmazonConfig)
    politeness: PolitenessConfig = field(default_factory=PolitenessConfig)
    crawler: CrawlerConfig = field(default_factory=CrawlerConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    schedule: ScheduleConfig = field(default_factory=ScheduleConfig)
    drive: DriveConfig = field(default_factory=DriveConfig)
    marketplaces: list[MarketplaceProfile] = field(default_factory=lambda: [
        MarketplaceProfile.from_dict(m) for m in DEFAULT_MARKETPLACES
    ])

    def marketplace(self, code: str) -> MarketplaceProfile | None:
        code = (code or "").lower()
        for mp in self.marketplaces:
            if mp.code == code:
                return mp
        return None

    def resolve(self, relative: str) -> Path:
        path = Path(relative)
        if not path.is_absolute():
            path = REPO_ROOT / path
        return path


def load_settings(repo_root: Path | None = None) -> Settings:
    root = repo_root or REPO_ROOT
    config_path = root / "config" / "settings.yml"
    settings = Settings()
    if not config_path.exists():
        return settings
    raw: dict[str, Any] = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    for section_name, section_cls in (
        ("amazon", AmazonConfig),
        ("politeness", PolitenessConfig),
        ("crawler", CrawlerConfig),
        ("storage", StorageConfig),
        ("schedule", ScheduleConfig),
        ("drive", DriveConfig),
    ):
        section_data = raw.get(section_name) or {}
        current = getattr(settings, section_name)
        for key, value in section_data.items():
            if hasattr(current, key):
                setattr(current, key, value)
    if isinstance(raw.get("marketplaces"), list) and raw["marketplaces"]:
        settings.marketplaces = [MarketplaceProfile.from_dict(m) for m in raw["marketplaces"]]
    env_zip = os.environ.get("AMZ_BS_DELIVERY_ZIP")
    if env_zip:
        settings.amazon.delivery_zip = env_zip
    return settings
