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


def _median(values: list[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    if n % 2 == 1:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


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

    def fetch(self, keyword_phrases: list[str]) -> dict:
        """
        Fetch active listings stats for a list of keyword phrases.

        Each phrase is queried separately (Etsy joins multi-word keywords
        as a single long-tail match, which understates competition). Results
        are deduplicated by listing_id; per-phrase counts are returned.

        Returns:
            {
                "total_count": int,          # max count across phrases
                "per_phrase": {str: int},    # count per phrase
                "sample_size": int,
                "avg_price": float | None,
                "avg_age_days": float | None,
            }
        """
        if self.dry_run:
            return self._dry_run(keyword_phrases)
        return self._live_fetch(keyword_phrases)

    def _live_fetch(self, keyword_phrases: list[str]) -> dict:
        now = _dt.datetime.now(_dt.timezone.utc)
        all_listings: list[dict] = []
        per_phrase_count: dict[str, int] = {}

        for phrase in keyword_phrases:
            params = {
                "keywords": phrase,
                "limit": min(PAGE_LIMIT, self.max_listings),
                "offset": 0,
            }
            phrase_listings: list[dict] = []
            total = 0
            while len(phrase_listings) < self.max_listings:
                data = self._get_with_retry(DEFAULT_BASE, params)
                total = data.get("count", 0)
                results = data.get("results", [])
                phrase_listings.extend(results)
                params["offset"] += PAGE_LIMIT
                if params["offset"] >= total or not results:
                    break
                time.sleep(1.5)
            per_phrase_count[phrase] = total
            known_ids = {r.get("listing_id") for r in all_listings}
            for r in phrase_listings:
                if r.get("listing_id") not in known_ids:
                    all_listings.append(r)
                    known_ids.add(r.get("listing_id"))
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
            "total_count": max(per_phrase_count.values()) if per_phrase_count else 0,
            "per_phrase": per_phrase_count,
            "sample_size": len(all_listings),
            "avg_price": round(_median(prices), 2) if prices else None,
            "avg_age_days": round(_median(ages), 1) if ages else None,
        }

    @staticmethod
    def _dry_run(keyword_phrases: list[str]) -> dict:
        """Deterministic fake data based on phrase hashes (no network)."""
        per_phrase = {}
        for phrase in keyword_phrases:
            seed = int(hashlib.sha256(phrase.encode()).hexdigest(), 16) % 10_000
            per_phrase[phrase] = (seed % 1500) + 50
        count = max(per_phrase.values()) if per_phrase else 0
        agg_seed = int(hashlib.sha256("|".join(keyword_phrases).encode()).hexdigest(), 16) % 10_000
        return {
            "total_count": count,
            "per_phrase": per_phrase,
            "sample_size": min(count, DEFAULT_MAX_LISTINGS),
            "avg_price": round(15.0 + (agg_seed % 300) + (agg_seed % 100) / 100.0, 2),
            "avg_age_days": 60.0 + (agg_seed % 400),
            "dry_run": True,
        }