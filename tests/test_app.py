import copy
import subprocess

import pytest
from fastapi.testclient import TestClient

from app import main
from app.models import ExploreRequest
from app.providers import (
    ProviderError,
    TrendsService,
    TTLCache,
    normalize_explore,
    run_worker,
)

client = TestClient(main.app)


@pytest.fixture
def single():
    return {
        "fetched_at": "2026-09-24T00:00:00Z",
        "interest_over_time": [
            {"date": "2026-09-01", "value": 43, "is_partial": False},
            {"date": "2026-09-08", "value": 71, "is_partial": True},
        ],
        "related_queries": {
            "top": [],
            "rising": [
                {"query": "coffee beans", "formatted_value": "Breakout", "value": 999}
            ],
        },
        "interest_by_region": [
            {"geo_code": "US-CA", "geo_name": "California", "value": 100}
        ],
    }


def test_keyword_normalization():
    req = ExploreRequest(keywords=["  咖啡   机 ", "咖啡 机", "Coffee", "coffee"])
    assert req.keywords == ["咖啡 机", "Coffee"]


@pytest.mark.parametrize(
    "body",
    [
        {"keywords": []},
        {"keywords": [" "]},
        {"keywords": ["x" * 101]},
        {"keywords": list("abcdef")},
        {"keywords": ["coffee"], "geo": "not-a-country"},
        {"keywords": ["coffee"], "timeframe": "arbitrary"},
        {"keywords": ["coffee"], "gprop": "invalid"},
        {"keywords": ["coffee"], "mode": "unknown"},
        {"keywords": ["coffee"], "url": "http://example.com"},
    ],
)
def test_invalid_requests_return_useful_errors(body):
    response = client.post("/api/explore", json=body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation"


def test_demo_explicit_and_keyword_escaped_as_data():
    word = '<script>alert("x")</script>'
    data = client.post("/api/explore", json={"keywords": [word], "mode": "demo"}).json()
    assert data["source"] == "synthetic-demo"
    assert data["request"]["keywords"] == [word]
    assert len(data["series"]) > 10
    assert data["related_available"]


def test_single_normalization(single):
    result = normalize_explore(single, ExploreRequest(keywords=["coffee"], mode="live"))
    assert result["series"][1] == {
        "date": "2026-09-08",
        "values": {"coffee": 71},
        "is_partial": True,
    }
    assert result["regions"][0]["values"] == {"coffee": 100}
    assert result["related"]["rising"][0]["formatted_value"] == "Breakout"


@pytest.mark.parametrize(
    "field,value",
    [
        ("related_queries", ["bad"]),
        ("related_queries", {"rising": "bad"}),
        ("interest_by_region", "bad"),
    ],
)
def test_changed_optional_schema_is_reported(single, field, value):
    single[field] = value
    with pytest.raises(ProviderError) as error:
        normalize_explore(single, ExploreRequest(keywords=["coffee"]))
    assert error.value.code == "invalid_upstream"


def test_demo_obeys_normalization_semantics():
    data = client.post(
        "/api/explore", json={"keywords": ["a", "b", "c"], "mode": "demo"}
    ).json()
    assert max(v for p in data["series"] for v in p["values"].values()) == 100
    assert all(sum(row["values"].values()) == 100 for row in data["regions"])


def test_comparison_keeps_shared_scale():
    raw = {
        "interest_over_time": [
            {"date": "2026-09-01", "values": {"coffee": 90, "tea": 12}}
        ],
        "interest_by_region": [
            {"geo_name": "Japan", "geo_code": "JP", "values": {"coffee": 60, "tea": 40}}
        ],
    }
    result = normalize_explore(
        raw, ExploreRequest(keywords=["coffee", "tea"], mode="live")
    )
    assert result["series"][0]["values"] == {"coffee": 90, "tea": 12}
    assert not result["related_available"]
    assert result["regions"][0]["values"]["tea"] == 40


@pytest.mark.parametrize("value", [None, -1, 101, float("nan"), "50", True])
def test_invalid_values_are_not_fabricated(single, value):
    single["interest_over_time"][0]["value"] = value
    with pytest.raises(ProviderError, match="数据"):
        normalize_explore(single, ExploreRequest(keywords=["coffee"]))


@pytest.mark.parametrize(
    "raw",
    [
        {},
        {"interest_over_time": []},
        {"interest_over_time": [{"date": "2026-09-01", "value": 0}]},
    ],
)
def test_empty_or_changed_upstream_is_not_a_zero_chart(raw):
    with pytest.raises(ProviderError):
        normalize_explore(raw, ExploreRequest(keywords=["coffee"]))


def test_cache_retains_observation_time_and_isolation():
    clock = [0]
    cache = TTLCache(ttl=10, maxsize=2, clock=lambda: clock[0])
    cache.put("a", {"fetched_at": "yesterday", "rows": [1]})
    found = cache.get("a")
    found["rows"].append(2)
    assert cache.get("a")["rows"] == [1]
    assert cache.get("a")["fetched_at"] == "yesterday"
    cache.put("b", {})
    cache.put("c", {})
    assert cache.get("a") is None
    clock[0] = 11
    assert cache.get("b") is None


def test_service_reuses_success_and_limits_requests(single):
    calls = []
    service = TrendsService(
        runner=lambda *args: calls.append(args) or single, clock=lambda: 100
    )
    req = ExploreRequest(keywords=["coffee"], mode="live")
    assert not service.explore(req)["cached"]
    assert service.explore(req)["cached"]
    assert len(calls) == 1
    with pytest.raises(ProviderError) as exc:
        service.explore(req.model_copy(update={"geo": "JP"}))
    assert exc.value.code == "cooldown"


def test_rate_limit_has_no_demo_fallback(monkeypatch):
    def failed(*args):
        raise ProviderError("rate_limited", "Google 限流", 429)

    service = TrendsService(runner=failed, clock=lambda: 100)
    monkeypatch.setattr(main, "service", service)
    response = client.post(
        "/api/explore", json={"keywords": ["coffee"], "mode": "live"}
    )
    assert response.status_code == 429
    assert "series" not in response.json()
    assert service.next_explore == 400


def test_busy_request_does_not_start_second_worker():
    service = TrendsService(runner=lambda *args: pytest.fail("worker must not start"))
    service.explore_lock.acquire()
    with pytest.raises(ProviderError) as exc:
        service.explore(ExploreRequest(keywords=["coffee"], mode="live"))
    assert exc.value.code == "busy"
    service.explore_lock.release()


def test_worker_timeout_cleans_up(monkeypatch):
    from app import providers

    class Process:
        calls = 0

        def communicate(self, *args, **kwargs):
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired("worker", 1)
            return "", ""

        def poll(self):
            return 1

    process = Process()
    killed = []
    monkeypatch.setattr(providers.subprocess, "Popen", lambda *a, **kw: process)
    monkeypatch.setattr(providers, "kill_worker", lambda p: killed.append(p))
    with pytest.raises(ProviderError) as exc:
        run_worker("rss", {"geo": "US"}, 1)
    assert exc.value.code == "timeout"
    assert killed == [process]


def test_rss_cache_and_mode_separation():
    raw = {
        "fetched_at": "2026-09-24T00:00:00Z",
        "trends": [{"keyword": "coffee", "news": []}],
    }
    calls = []
    service = TrendsService(
        runner=lambda *args: calls.append(args) or copy.deepcopy(raw)
    )
    assert service.trending("US", "demo")["mode"] == "demo"
    assert not calls
    assert service.trending("US", "live")["source"] == "google-trends-rss"
    assert service.trending("US", "live")["cached"]
    assert len(calls) == 1


def test_rss_rejects_global():
    assert client.get("/api/trending?geo=&mode=demo").status_code == 422


def test_local_origin_and_static():
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/docs").status_code == 200
    assert client.get("/api/health").json()["status"] == "ok"
    assert (
        client.post(
            "/api/explore",
            json={"keywords": ["coffee"]},
            headers={"Origin": "https://evil.example"},
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/trending?mode=demo", headers={"Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert (
        client.get("/api/health", headers={"Host": "evil.example"}).status_code == 400
    )
