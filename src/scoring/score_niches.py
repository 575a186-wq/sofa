"""Scoring formula from concept doc 4.7."""

import math

DEFAULT_WEIGHTS = {
    "trend_weight": 0.4,
    "social_weight": 0.0,
    "competition_weight": 0.3,
    "freshness_weight": 0.3,
}


def opportunity_score(
    trend_growth_pct: float | None,
    social_growth_pct: float | None,
    etsy_listing_count: int,
    avg_age_days: float | None,
    weights: dict | None = None,
) -> float:
    """
    Compute opportunity_score.

    formula:
        opportunity = trend_weight * trend_growth_pct
                    + social_weight * social_growth_pct
                    - competition_weight * log10(etsy_listing_count)
                    + freshness_weight * (1 / avg_age_days)

    Missing data is treated as 0 for that component (never penalizes).
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    trend_term = (w["trend_weight"] * trend_growth_pct) if trend_growth_pct is not None else 0.0
    social_term = (w["social_weight"] * social_growth_pct) if social_growth_pct is not None else 0.0
    competition_term = -w["competition_weight"] * math.log10(max(etsy_listing_count, 1))
    freshness_term = (w["freshness_weight"] * (1.0 / avg_age_days)) if avg_age_days and avg_age_days > 0 else 0.0
    return round(trend_term + social_term + competition_term + freshness_term, 4)


def final_score(opportunity: float, automation_fit: float) -> float:
    """final = opportunity * automation_fit (1.0 for Type B, 0.3-0.5 for Type A)."""
    return round(opportunity * automation_fit, 4)