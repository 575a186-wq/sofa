"""Tests for Etsy client including dry-run determinism and live request behavior."""

import json

from src.fetchers.etsy_client import EtsyClient


def _fake_response(count=150, results=None, pages=1):
    results = results or [{
        "listing_id": 1,
        "title": "test listing",
        "price": {"amount": 2999, "divisor": 100},
        "created_timestamp": 1_600_000_000,
    }]
    return json.dumps({"count": count, "results": results})


def test_dry_run_is_deterministic(monkeypatch):
    calls = []
    monkeypatch.setattr("src.fetchers.etsy_client.requests.get",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in dry-run")))
    c = EtsyClient(api_key=None)
    r1 = c.fetch(["kw a", "kw b"])
    r2 = c.fetch(["kw a", "kw b"])
    assert r1 == r2
    assert r1["total_count"] > 0
    assert r1["avg_price"] > 0
    assert r1["avg_age_days"] > 0
    assert len(calls) == 0


def test_live_uses_x_api_key_header(monkeypatch):
    captured = {}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"count": 1, "results": [{
                "listing_id": 1,
                "price": {"amount": 1999, "divisor": 100},
                "created_timestamp": 1_600_000_000,
            }]}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        return FakeResp()

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get", fake_get)
    c = EtsyClient(api_key="abc:secret", max_listings=100)
    out = c.fetch(["star map"])
    assert captured["headers"]["x-api-key"] == "abc:secret"
    assert "keywords" in captured["params"]
    assert out["total_count"] == 1
    assert out["avg_price"] == 19.99


def test_retry_on_429(monkeypatch):
    calls = {"n": 0}

    class Fake429:
        status_code = 429

        def raise_for_status(self):
            raise AssertionError("should not call raise_for_status on retryable")

    class FakeOk:
        status_code = 200

        def json(self):
            return {"count": 0, "results": []}

    def fake_get(*a, **k):
        calls["n"] += 1
        return Fake429() if calls["n"] < 3 else FakeOk()

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get", fake_get)
    monkeypatch.setattr("src.fetchers.etsy_client.time.sleep", lambda _s: None)
    c = EtsyClient(api_key="abc:secret")
    out = c.fetch(["kw"])
    assert calls["n"] == 3
    assert out["sample_size"] == 0