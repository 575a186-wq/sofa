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
    monkeypatch.setattr("src.fetchers.etsy_client.requests.get",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in dry-run")))
    c = EtsyClient(api_key=None)
    r1 = c.fetch(["kw a", "kw b"])
    r2 = c.fetch(["kw a", "kw b"])
    assert r1 == r2
    assert r1["total_count"] > 0
    assert r1["avg_price"] > 0
    assert r1["avg_age_days"] > 0
    assert len(r1["per_phrase"]) == 2


def test_dry_run_count_is_max_of_phrases():
    c = EtsyClient(api_key=None)
    r1 = c.fetch(["alpha phrase"])
    r2 = c.fetch(["beta phrase that is different"])
    r3 = c.fetch(["alpha phrase", "beta phrase that is different"])
    assert r3["total_count"] == max(r1["total_count"], r2["total_count"])


def test_live_queries_each_phrase_with_x_api_key(monkeypatch):
    captured = {"calls": []}

    class FakeResp:
        status_code = 200

        def json(self):
            return {"count": 5, "results": [{
                "listing_id": 1,
                "price": {"amount": 1999, "divisor": 100},
                "created_timestamp": 1_600_000_000,
            }]}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["calls"].append(params["keywords"])
        return FakeResp()

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get", fake_get)
    c = EtsyClient(api_key="abc:secret", max_listings=100)
    out = c.fetch(["star map", "birthday star map"])
    assert captured["calls"] == ["star map", "birthday star map"]
    assert out["total_count"] == 5
    assert out["per_phrase"] == {"star map": 5, "birthday star map": 5}
    assert out["avg_price"] == 19.99


def test_live_dedupes_listings_across_phrases(monkeypatch):
    responses = iter([
        {"count": 2, "results": [
            {"listing_id": 11, "price": {"amount": 1000, "divisor": 100},
             "created_timestamp": 1_600_000_000},
            {"listing_id": 12, "price": {"amount": 2000, "divisor": 100},
             "created_timestamp": 1_600_000_000},
        ]},
        {"count": 2, "results": [
            {"listing_id": 12, "price": {"amount": 2000, "divisor": 100},
             "created_timestamp": 1_600_000_000},
            {"listing_id": 13, "price": {"amount": 3000, "divisor": 100},
             "created_timestamp": 1_600_000_000},
        ]},
    ])

    class FakeResp:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params=None, headers=None, timeout=None):
        return FakeResp(next(responses))

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get", fake_get)
    monkeypatch.setattr("src.fetchers.etsy_client.time.sleep", lambda _s: None)
    c = EtsyClient(api_key="abc:secret", max_listings=100)
    out = c.fetch(["phrase one", "phrase two"])
    assert out["sample_size"] == 3  # deduplicated 11,12,13
    assert out["avg_price"] == 20.00  # (10 + 20 + 30) / 3
    assert out["total_count"] == 2


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


def test_fetch_top_dry_run_returns_empty(monkeypatch):
    monkeypatch.setattr("src.fetchers.etsy_client.requests.get",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network in dry-run")))
    c = EtsyClient(api_key=None)
    assert c.fetch_top("some phrase", limit=30) == []


def test_fetch_top_parses_price_age_and_shop_id(monkeypatch):
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc)
    old_ts = int(now.timestamp()) - 60 * 60 * 24 * 45  # 45 days ago

    class FakeResp:
        status_code = 200

        def json(self):
            return {"count": 1, "results": [{
                "listing_id": 7,
                "title": "Poster A",
                "price": {"amount": 2999, "divisor": 100},
                "created_timestamp": old_ts,
                "shop_id": 42,
            }]}

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get",
                        lambda *a, **k: FakeResp())
    c = EtsyClient(api_key="abc:secret")
    rows = c.fetch_top("some phrase", limit=30)
    assert len(rows) == 1
    assert rows[0]["listing_id"] == 7
    assert rows[0]["price"] == 29.99
    assert 44 <= rows[0]["age_days"] <= 46
    assert rows[0]["shop_id"] == 42


def test_shop_names_maps_ids_and_skips_dry_run(monkeypatch):
    class FakeResp:
        status_code = 200
        shop_name = "CoolShop"

        def json(self):
            return {"shop_id": 42, "shop_name": self.shop_name}

    def fake_get(url, params=None, headers=None, timeout=None):
        shop_id = int(url.rsplit("/", 1)[1])
        return type("R", (), {"status_code": 200, "json": lambda self, sid=shop_id: {
            "shop_id": sid, "shop_name": f"Shop{sid}"}})()

    monkeypatch.setattr("src.fetchers.etsy_client.requests.get", fake_get)
    monkeypatch.setattr("src.fetchers.etsy_client.time.sleep", lambda _s: None)
    c = EtsyClient(api_key="abc:secret")
    names = c.shop_names({42, 43, 42})
    assert names == {42: "Shop42", 43: "Shop43"}
    c_dry = EtsyClient(api_key=None)
    assert c_dry.shop_names({1}) == {}