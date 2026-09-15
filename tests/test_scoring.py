"""Unit tests for scoring formula."""

import math

from src.scoring.score_niches import opportunity_score, final_score


def test_opportunity_baseline_zero_data():
    s = opportunity_score(None, None, etsy_listing_count=0, avg_age_days=None)
    assert math.isclose(s, 0.0, abs_tol=1e-6)


def test_missing_trend_does_not_penalize():
    low = opportunity_score(None, None, etsy_listing_count=100, avg_age_days=200)
    high = opportunity_score(50.0, None, etsy_listing_count=100, avg_age_days=200)
    assert high > low


def test_competition_penalizes_logarithmically():
    low_comp = opportunity_score(0, None, etsy_listing_count=10, avg_age_days=100)
    high_comp = opportunity_score(0, None, etsy_listing_count=100_000, avg_age_days=100)
    assert low_comp > high_comp


def test_component_weights_applied():
    w = {"trend_weight": 1.0, "social_weight": 0, "competition_weight": 0, "freshness_weight": 0}
    s = opportunity_score(25.0, None, etsy_listing_count=999_999, avg_age_days=1, weights=w)
    assert math.isclose(s, 25.0, abs_tol=1e-4)


def test_final_score_multiplies_by_automation_fit():
    assert math.isclose(final_score(10.0, 1.0), 10.0)
    assert math.isclose(final_score(10.0, 0.5), 5.0)


def test_deterministic_dry_run_no_network():
    from src.fetchers.etsy_client import EtsyClient

    c = EtsyClient(api_key=None)
    a = c.fetch(["custom star map"])
    b = c.fetch(["custom star map"])
    assert a == b
    assert a["total_count"] > 0
    assert "dry_run" in a