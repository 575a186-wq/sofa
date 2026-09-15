"""Scoring formula v2 - normalized components on a comparable 0..100 scale.

Concept doc 4.7 defines a weighted raw sum with mixed units (% growth, log10
count, 1/age) which makes components non-comparable and lets missing data
crush the score. v2 keeps the same four components and weights but normalizes
each onto 0..100:

    trend_norm       = 50 + 30 * tanh(growth% / trend_ref)
    competition_norm = 100 * (1 - clamp(log10(count), 0, comp_max_log10) / comp_max_log10)
    freshness_norm   = 100 * (1 - clamp(age_days, 0, fresh_max_days) / fresh_max_days)

Missing data is treated as neutral (50) - never 0, never a penalty.
Score range [0, 100]; final = opportunity * automation_fit.
"""

import math

DEFAULT_WEIGHTS = {
    "trend_weight": 0.4,
    "social_weight": 0.0,
    "competition_weight": 0.3,
    "freshness_weight": 0.3,
}

DEFAULT_TREND_REF = 150.0
DEFAULT_COMP_MAX_LOG10 = 6.0
DEFAULT_FRESH_MAX_DAYS = 365.0
NEUTRAL = 50.0


def _trend_normalized(growth_pct: float, trend_ref: float) -> float:
    """Map growth % (say +100%, -50%) onto 25..75 band centered at 50."""
    return NEUTRAL + 30.0 * math.tanh(growth_pct / trend_ref)


def _competition_normalized(count: int, comp_max_log10: float) -> float:
    logc = min(math.log10(max(count, 1)), comp_max_log10)
    return 100.0 * (1.0 - logc / comp_max_log10)


def _freshness_normalized(age_days: float, fresh_max_days: float) -> float:
    clamped = min(max(age_days, 0.0), fresh_max_days)
    return 100.0 * (1.0 - clamped / fresh_max_days)


def opportunity_score(
    trend_growth_pct: float | None,
    social_growth_pct: float | None,
    etsy_listing_count: int,
    avg_age_days: float | None,
    weights: dict | None = None,
    trend_ref: float = DEFAULT_TREND_REF,
    comp_max_log10: float = DEFAULT_COMP_MAX_LOG10,
    fresh_max_days: float = DEFAULT_FRESH_MAX_DAYS,
) -> float:
    """Normalized opportunity score in [0, 100]; missing inputs are neutral (50)."""
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    trend = _trend_normalized(trend_growth_pct, trend_ref) if trend_growth_pct is not None else NEUTRAL
    social = _trend_normalized(social_growth_pct, trend_ref) if social_growth_pct is not None else NEUTRAL
    competition = _competition_normalized(etsy_listing_count, comp_max_log10)
    freshness = _freshness_normalized(avg_age_days, fresh_max_days) if avg_age_days is not None else NEUTRAL
    total = (
        w["trend_weight"] * trend
        + w["social_weight"] * social
        + w["competition_weight"] * competition
        + w["freshness_weight"] * freshness
    )
    return round(max(0.0, min(100.0, total)), 4)


def final_score(opportunity: float, automation_fit: float) -> float:
    """final = opportunity * automation_fit (1.0 for Type B, 0.3-0.5 for Type A)."""
    return round(opportunity * automation_fit, 4)