"""Unit tests for normalized scoring formula v2."""

import math

from src.scoring.score_niches import (
    opportunity_score,
    final_score,
    _trend_normalized,
    _competition_normalized,
    _freshness_normalized,
)


def test_opportunity_with_all_missing_is_neutral():
    # All missing, neutral competition (count=1000 -> log10/6 = 0.5) -> score 50
    s = opportunity_score(None, None, etsy_listing_count=1000, avg_age_days=None)
    assert math.isclose(s, 50.0, abs_tol=1e-3)


def test_missing_trend_is_neutral_not_penalizing():
    neutral = opportunity_score(None, None, etsy_listing_count=1000, avg_age_days=100)
    strong = opportunity_score(150.0, None, etsy_listing_count=1000, avg_age_days=100)
    assert strong > neutral


def test_competition_penalizes_logarithmically():
    low_comp = opportunity_score(0.0, None, etsy_listing_count=10, avg_age_days=100)
    high_comp = opportunity_score(0.0, None, etsy_listing_count=1_000_000, avg_age_days=100)
    assert low_comp > high_comp


def test_more_competition_lower_score():
    a = opportunity_score(0.0, None, etsy_listing_count=100, avg_age_days=200)
    b = opportunity_score(0.0, None, etsy_listing_count=100_000, avg_age_days=200)
    assert a > b


def test_younger_listings_score_higher():
    older = opportunity_score(0.0, None, etsy_listing_count=1000, avg_age_days=300)
    younger = opportunity_score(0.0, None, etsy_listing_count=1000, avg_age_days=10)
    assert younger > older


def test_score_bounded_to_100():
    s = opportunity_score(500.0, None, etsy_listing_count=1, avg_age_days=0)
    assert 0.0 <= s <= 100.0


def test_weights_applied():
    w = {"trend_weight": 1.0, "social_weight": 0.0, "competition_weight": 0.0, "freshness_weight": 0.0}
    s = opportunity_score(0.0, None, etsy_listing_count=50, avg_age_days=50, weights=w)
    assert math.isclose(s, _trend_normalized(0.0, 150.0), abs_tol=1e-4)


def test_final_score_multiplies_by_automation_fit():
    assert math.isclose(final_score(60.0, 1.0), 60.0)
    assert math.isclose(final_score(60.0, 0.5), 30.0)


def test_normalizers():
    assert math.isclose(_trend_normalized(0.0, 150.0), 50.0, abs_tol=1e-4)
    assert _trend_normalized(300.0, 150.0) > _trend_normalized(-100.0, 150.0)
    assert math.isclose(_competition_normalized(1, 6.0), 100.0, abs_tol=1e-4)
    assert math.isclose(_freshness_normalized(0.0, 365.0), 100.0, abs_tol=1e-4)
    assert math.isclose(_freshness_normalized(365.0, 365.0), 0.0, abs_tol=1e-4)


def test_deterministic_dry_run_no_network():
    from src.fetchers.etsy_client import EtsyClient

    c = EtsyClient(api_key=None)
    a = c.fetch(["custom star map"])
    b = c.fetch(["custom star map"])
    assert a == b
    assert a["total_count"] > 0
    assert "dry_run" in a