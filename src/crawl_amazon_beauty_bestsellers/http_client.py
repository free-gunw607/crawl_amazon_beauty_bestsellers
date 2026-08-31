from __future__ import annotations

import random
import re
import time
import uuid
from pathlib import Path

from .config import Settings

try:
    from curl_cffi import requests as curl_requests

    HAS_CURL_CFFI = True
except ImportError:
    curl_requests = None
    HAS_CURL_CFFI = False

import requests

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
]

CAPTCHA_MARKERS = (
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "captchacharacters",
    "Robot Check",
)

CSRF_PATTERN = re.compile(r'"anti-csrftoken-a2z"\s*:\s*"([^"]+)"')

DELIVERY_ZIPS = {
    "us": "10001",
    "uk": "EC1A 1BB",
    "de": "10115",
    "fr": "75001",
    "es": "28001",
}


class CaptchaBlocked(RuntimeError):
    def __init__(self, url: str):
        super().__init__(f"captcha or block page detected: {url}")
        self.url = url


class FetchResult:
    def __init__(self, text: str, status_code: int, url: str):
        self.text = text
        self.status_code = status_code
        self.url = url


class AmazonClient:
    def __init__(self, settings: Settings, repo_root: Path | None = None, marketplace=None):
        self.settings = settings
        self.repo_root = repo_root or Path(__file__).resolve().parents[2]
        self.transport = "curl_cffi" if HAS_CURL_CFFI else "requests"
        self.session = None
        self.us_location_pinned = False
        self.request_count = 0
        self.marketplace = marketplace
        self._build_session()

    def _cookie_domain(self) -> str:
        if self.marketplace is not None:
            from urllib.parse import urlparse

            host = urlparse(self.marketplace.base_url).hostname or "www.amazon.com"
            return "." + ".".join(host.split(".")[-2:])
        return ".amazon.com"

    def _build_session(self):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": self.marketplace.language if self.marketplace else "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": random.choice(USER_AGENTS),
        }
        currency = self.marketplace.currency_pref if self.marketplace else self.settings.amazon.currency_pref
        language = self.marketplace.language if self.marketplace else self.settings.amazon.language
        cookies = {
            "lc-main": language,
            "i18n-prefs": currency,
        }
        if HAS_CURL_CFFI:
            self.session = curl_requests.Session(impersonate="chrome")
        else:
            self.session = requests.Session()
        self.session.headers.update(headers)
        for name, value in cookies.items():
            self.session.cookies.set(name, value, domain=self._cookie_domain())

    def close(self):
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass
            self.session = None

    def _polite_delay(self):
        delay = random.uniform(
            self.settings.politeness.min_delay_seconds,
            self.settings.politeness.max_delay_seconds,
        )
        time.sleep(delay)

    @staticmethod
    def _is_captcha(text: str) -> bool:
        lowered = text[:20000].lower()
        return any(marker.lower() in lowered for marker in CAPTCHA_MARKERS)

    def get(self, url: str, **kwargs) -> FetchResult:
        attempts = self.settings.politeness.max_attempts
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            if attempt > 1:
                time.sleep(min(2**attempt, 8))
            try:
                kwargs.setdefault("allow_redirects", True)
                response = self.session.get(
                    url,
                    timeout=self.settings.politeness.request_timeout_seconds,
                    **kwargs,
                )
                self.request_count += 1
                text = response.text
                status = getattr(response, "status_code", 0)
                if status in (503, 429) or (status == 200 and self._is_captcha(text)):
                    raise CaptchaBlocked(url)
                if status >= 500:
                    last_error = RuntimeError(f"http {status} for {url}")
                    continue
                self._polite_delay()
                return FetchResult(text=text, status_code=status, url=str(response.url))
            except CaptchaBlocked:
                raise
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"failed after {attempts} attempts: {url}") from last_error

    def post(self, url: str, data=None, headers=None) -> FetchResult:
        response = self.session.post(
            url,
            data=data or {},
            timeout=self.settings.politeness.request_timeout_seconds,
            headers=headers or {},
        )
        self.request_count += 1
        return FetchResult(text=response.text, status_code=response.status_code, url=url)

    def bootstrap_us_location(self) -> dict[str, object]:
        mp_code = self.marketplace.code if self.marketplace else "us"
        base_url = self.marketplace.base_url if self.marketplace else self.settings.amazon.base_url
        delivery_zip = DELIVERY_ZIPS.get(mp_code, self.settings.amazon.delivery_zip)
        info: dict[str, object] = {
            "transport": self.transport,
            "marketplace": mp_code,
            "delivery_zip": delivery_zip,
            "pinned": False,
            "method": "",
        }
        home = self.get(base_url + "/", allow_redirects=True)
        match = CSRF_PATTERN.search(home.text)
        csrf_token = match.group(1) if match else ""
        change_url = base_url + "/portal-migration/hz/glow/address-change?actionSource=glow"
        form = {
            "locationType": "LOCATION_INPUT",
            "zipCode": delivery_zip,
            "deviceType": "web",
            "pageType": "Gateway",
            "storeContext": "generic",
            "addressType": "ZIP_CODE",
        }
        request_headers = {}
        if csrf_token:
            form["anti-csrftoken-a2z"] = csrf_token
            request_headers["anti-csrftoken-a2z"] = csrf_token
        result = self.post(change_url, data=form, headers=request_headers)
        pinned_ok = result.status_code == 200
        info["method"] = "glow-address-change" if csrf_token else "cookie-only"
        info["http_status"] = result.status_code
        self.us_location_pinned = pinned_ok
        info["pinned"] = pinned_ok
        return info

    def save_raw(self, html: str, kind: str, key: str) -> Path | None:
        if not self.settings.crawler.save_raw_html:
            return None
        raw_dir = self.settings.resolve(self.settings.storage.raw_dir) / kind
        raw_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M%S")
        path = raw_dir / f"{stamp}_{key.replace('/', '_')}_{uuid.uuid4().hex[:6]}.html"
        path.write_text(html, encoding="utf-8")
        return path
