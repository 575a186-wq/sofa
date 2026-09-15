"""Etsy Open API v3 read-only client for findAllListingsActive."""

import datetime as _dt
import hashlib
import logging
import math
import os
import time

import requests

logger = logging.getLogger(__name__)

DEFAULT_BASE = "https://openapi.etsy.com/v3/application/listings/active"
PAGE_LIMIT = 100
DEFAULT_MAX_LISTINGS = 300
RETRY_ATTEMPTS = 4
BASE_DELAY = 5.0


class EtsyClient:
    """Read-only client for Etsy Open API v3 findAllListingsActive."""

    def __init__(self, api_key: str | None = None, max_listings: int = DEFAULT_MAX_LISTINGS):
        self.api_key = api_key or os.getenv("ETSY_API_KEY") or None
        self.dry_run = self.api_key is None
        self.max_listings = max_listings

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key}

    def _get_with_retry(self, url: str, params: dict) -> dict:
        """GET with exponential retry on 429/5xx, capped by RETRY_ATTEMPTS."""
        for attempt in range(RETRY_ATTEMPTS):
            resp = requests.get(url, params=params, headers=self._headers(), timeout=30)
            if resp.status_code < 400:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                delay = BASE_DELAY * math.pow(2, attempt)
                logger.warning(
                    "Etsy %d, retrying in %.0fs (attempt %d/%d)",
                    resp.status_code, delay, attempt + 1, RETRY_ATTEMPTS,
                )
                time.sleep(delay)
                continue
            resp.raise_for_status()
        raise RuntimeError(f"Etsy API failed after {RETRY_ATTEMPTS} attempts")

    def fetch(self, keywords: list[str]) -> dict:
        """
        Fetch active listings stats for a keyword set.

        Returns:
            {
                "total_count": int,
                "sample_size": int,
                "avg_price": float | None,
                "avg_age_days": float | None,
            }
        """
        if self.dry_run:
            return self._dry_run(keywords)
        return self._live_fetch(keywords)

    def _live_fetch(self, keywords: list[str]) -> dict:
        now = _dt.datetime.now(_dt.timezone.utc)
        params = {
            "keywords": " ".join(keywords),
            "limit": min(PAGE_LIMIT, self.max_listings),
            "offset": 0,
        }
        all_listings: list[dict] = []
        total_count = 0

        while len(all_listings) < self.max_listings:
            data = self._get_with_retry(DEFAULT_BASE, params)
            total_count = data.get("count", 0)
            results = data.get("results", [])
            all_listings.extend(results)
            params["offset"] += PAGE_LIMIT
            if params["offset"] >= total_count or not results:
                break
            time.sleep(1.5)

        prices: list[float] = []
        ages: list[float] = []
        for r in all_listings:
            price_info = r.get("price")
            if price_info and "amount" in price_info and "divisor" in price_info:
                prices.append(float(price_info["amount"]) / float(price_info["divisor"]))
            created_ts = r.get("created_timestamp")
            if created_ts:
                created_dt = _dt.datetime.fromtimestamp(created_ts, tz=_dt.timezone.utc)
                ages.append((now - created_dt).days)

        return {
            "total_count": total_count,
            "sample_size": len(all_listings),
            "avg_price": round(sum(prices) / len(prices), 2) if prices else None,
            "avg_age_days": round(sum(ages) / len(ages), 1) if ages else None,
        }

    @staticmethod
    def _dry_run(keywords: list[str]) -> dict:
        """Deterministic fake data based on keyword hash (no network)."""
        seed_str = "|".join(keywords)
        seed = int(hashlib.sha256(seed_str.encode()).hexdigest(), 16) % 10_000
        fake_count = (seed % 1500) + 50
        fake_price = 15.0 + (seed % 300) + (seed % 100) / 100.0
        fake_age = 60.0 + (seed % 400)
        return {
            "total_count": fake_count,
            "sample_size": min(fake_count, DEFAULT_MAX_LISTINGS),
            "avg_price": round(fake_price, 2),
            "avg_age_days": fake_age,
            "dry_run": True,
        }