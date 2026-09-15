"""Google Trends fetcher backed by trendspyg (requires Chrome for interest-over-time)."""

import logging

logger = logging.getLogger(__name__)

TRENDSPYG_IMPORT_ERROR = "trendspyg not installed (pip install trendspyg)"


def _compute_growth(values: list[int]) -> float | None:
    """Growth % = (avg last 3mo - avg prev 9mo) / avg prev 9mo * 100."""
    if not values or len(values) < 6:
        return None
    split = len(values) * 3 // 12
    if split == 0:
        split = 1
    prev_avg = sum(values[: len(values) - split]) / max(len(values) - split, 1)
    recent_avg = sum(values[len(values) - split:]) / max(split, 1)
    if prev_avg == 0:
        return 100.0 if recent_avg > 0 else 0.0
    return (recent_avg - prev_avg) / prev_avg * 100


def get_trend_growth(keyword: str, geo: str = "US") -> dict:
    """
    Fetch interest over time for the last 12 months and compute growth %.

    Returns:
        {
            "trend_growth_pct": float | None,
            "points": int,
            "method": "trendspyg",
            "error": str | None,
        }
    """
    try:
        from trendspyg import download_google_trends_interest_over_time
    except ImportError:
        return {"trend_growth_pct": None, "points": 0, "method": "trendspyg", "error": TRENDSPYG_IMPORT_ERROR}

    try:
        series = download_google_trends_interest_over_time(
            keyword, geo=geo, timeframe="today 12-m", cache="disk"
        )
    except Exception as exc:  # Chrome missing, rate-limited, etc.
        return {"trend_growth_pct": None, "points": 0, "method": "trendspyg", "error": str(exc)}

    if not series:
        return {"trend_growth_pct": None, "points": 0, "method": "trendspyg", "error": "series too short"}

    values = [p.get("value", 0) for p in series]
    growth = _compute_growth(values)
    return {
        "trend_growth_pct": round(growth, 2) if growth is not None else None,
        "points": len(values),
        "method": "trendspyg",
        "error": None if growth is not None else "series too short",
    }