"""Tests for the trends_client (graceful degradation + growth math)."""

from src.fetchers.trends_client import get_trend_growth, _compute_growth


def test_growth_missing_series_returns_none():
    assert _compute_growth([]) is None
    assert _compute_growth([1, 2, 3]) is None


def test_growth_positive_rising():
    values = [10] * 9 + [20] * 3
    g = _compute_growth(values)
    assert g is not None and g > 0


def test_growth_negative_falling():
    values = [20] * 9 + [10] * 3
    g = _compute_growth(values)
    assert g is not None and g < 0


def test_get_trend_growth_graceful_without_package(monkeypatch):
    monkeypatch.setitem(__import__("sys").modules, "trendspyg", None)
    # Simulate ImportError by removing the fake module then calling the wrapper.
    sys_mod = __import__("sys")
    monkeypatch.delitem(sys_mod.modules, "trendspyg")
    import builtins
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name == "trendspyg":
            raise ImportError("not installed")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = get_trend_growth("test keyword")
    assert out["trend_growth_pct"] is None
    assert out["error"] is not None


def test_get_trend_growth_calls_trendspyg(monkeypatch):
    import sys
    sys.modules["trendspyg"] = type(sys)("trendspyg")

    def fake_iot(kw, geo=None, timeframe=None, cache=None):
        return [{"date": f"2026-0{m}-01T00:00:00Z", "value": 10} for m in range(1, 10)] + [
            {"date": f"2026-10-0{m}T00:00:00Z", "value": 20} for m in range(1, 4)
        ]

    sys.modules["trendspyg"].download_google_trends_interest_over_time = fake_iot
    out = get_trend_growth("kw", geo="US")
    assert out["error"] is None
    assert out["trend_growth_pct"] is not None
    assert out["points"] == 12