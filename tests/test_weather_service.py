"""Comprehensive Tests for WeatherAPI.com Integration and Service.

Covers:
- Secret redaction (never leak API keys in URLs or logs)
- Coordinate and query string validation
- Coordinate normalization and spatial cache sharing
- In-memory cache TTL and cache hits
- In-flight request deduplication
- Stale-on-error fallback resilience
- Response parsing and normalized WeatherObservation schema
- FastAPI HTTP endpoints (/api/weather/current, /api/weather/health, /api/weather/snapshot)
- Deterministic simulation boundary (SimEngine isolation)
"""

import asyncio
import datetime
from pathlib import Path
import sys
import pytest
import httpx
from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from backend.app.main import app
from backend.app.weather_service import (
    WeatherService,
    WeatherObservation,
    redact_secrets,
    weather_service,
)
from backend.app.engine import SimEngine


@pytest.fixture
def client():
    return TestClient(app)


def test_secret_redaction():
    secret_key = "abcdef1234567890abcdef"
    url1 = f"https://api.weatherapi.com/v1/current.json?key={secret_key}&q=Delhi"
    redacted1 = redact_secrets(url1, secret_key)
    assert secret_key not in redacted1
    assert "key=[REDACTED]" in redacted1

    url2 = f"https://example.com/api?lat=20&lon=78&key={secret_key}"
    redacted2 = redact_secrets(url2, secret_key)
    assert secret_key not in redacted2
    assert "&key=[REDACTED]" in redacted2

    err_text = f"Connection failed to host with token {secret_key} timed out"
    redacted_err = redact_secrets(err_text, secret_key)
    assert secret_key not in redacted_err
    assert "[REDACTED]" in redacted_err


def test_coordinate_validation():
    srv = WeatherService(api_key="dummy_key")
    # Valid
    srv._validate_coordinates(28.61, 77.20)
    srv._validate_coordinates(-90.0, -180.0)
    srv._validate_coordinates(90.0, 180.0)

    # Invalid latitude
    with pytest.raises(ValueError, match="Latitude"):
        srv._validate_coordinates(91.5, 77.0)
    with pytest.raises(ValueError, match="Latitude"):
        srv._validate_coordinates(-91.0, 77.0)

    # Invalid longitude
    with pytest.raises(ValueError, match="Longitude"):
        srv._validate_coordinates(20.0, 181.0)
    with pytest.raises(ValueError, match="Longitude"):
        srv._validate_coordinates(20.0, -185.0)


def test_query_validation():
    srv = WeatherService(api_key="dummy_key")
    assert srv._validate_query("  New Delhi  ") == "New Delhi"

    with pytest.raises(ValueError, match="empty"):
        srv._validate_query("   ")

    with pytest.raises(ValueError, match="maximum length"):
        srv._validate_query("A" * 105)

    with pytest.raises(ValueError, match="invalid characters"):
        srv._validate_query("http://evil.com/leak")


def test_coordinate_normalization():
    srv = WeatherService(api_key="dummy_key")
    # ~1.1km grid resolution
    assert srv._normalize_coord_key(28.6139, 77.2090) == "coord:28.61:77.21"
    assert srv._normalize_coord_key(28.6111, 77.2089) == "coord:28.61:77.21"
    assert srv._normalize_query_key("  MUMBAI ") == "q:mumbai"


@pytest.mark.asyncio
async def test_weather_service_caching_and_mock_response():
    # Mock upstream response
    mock_payload = {
        "location": {
            "name": "New Delhi",
            "region": "Delhi",
            "country": "India",
            "lat": 28.61,
            "lon": 77.21,
            "tz_id": "Asia/Kolkata",
            "localtime": "2026-10-14 11:30",
        },
        "current": {
            "last_updated_epoch": 1791958200,
            "temp_c": 31.0,
            "temp_f": 87.8,
            "feelslike_c": 34.0,
            "feelslike_f": 93.2,
            "is_day": 1,
            "condition": {
                "text": "Clear",
                "icon": "//cdn.weatherapi.com/weather/64x64/day/113.png",
                "code": 1000,
            },
            "wind_mph": 8.1,
            "wind_kph": 13.0,
            "wind_degree": 300,
            "wind_dir": "WNW",
            "pressure_mb": 1012.0,
            "precip_mm": 0.0,
            "humidity": 45,
            "cloud": 0,
            "vis_km": 6.0,
            "uv": 6.0,
            "gust_kph": 18.0,
        },
    }

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, json=mock_payload)

    mock_transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        srv = WeatherService(api_key="mock_secret_key", cache_ttl_seconds=60)

        # 1. First fetch -> cache miss, calls provider
        obs1 = await srv.get_current_weather(lat=28.6139, lon=77.2090, client=client)
        assert call_count == 1
        assert obs1.resolved_name == "New Delhi"
        assert obs1.temp_c == 31.0
        assert obs1.temp_f == 87.8
        assert obs1.humidity_pct == 45
        assert obs1.condition_text == "Clear"
        assert obs1.provenance == "REAL_OBSERVATION"
        assert obs1.is_cached is False

        # 2. Second fetch nearby coords within same ~1.1km cell -> cache hit
        obs2 = await srv.get_current_weather(lat=28.6140, lon=77.2091, client=client)
        assert call_count == 1  # No upstream HTTP call
        assert obs2.is_cached is True
        assert obs2.provenance == "CACHED_REAL_DATA"

        # 3. Third fetch with force_refresh -> calls provider again
        obs3 = await srv.get_current_weather(lat=28.6139, lon=77.2090, force_refresh=True, client=client)
        assert call_count == 2
        assert obs3.is_cached is False


@pytest.mark.asyncio
async def test_weather_service_inflight_deduplication():
    """Verify concurrent requests for the same location only invoke 1 upstream call."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(
            200,
            json={
                "location": {"name": "Bengaluru", "lat": 12.97, "lon": 77.59},
                "current": {"temp_c": 26.5, "condition": {"text": "Partly Cloudy"}},
            },
        )

    mock_transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        srv = WeatherService(api_key="mock_key", cache_ttl_seconds=60)
        # Launch 5 concurrent fetches
        tasks = [
            srv.get_current_weather(lat=12.9716, lon=77.5946, client=client)
            for _ in range(5)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 5
        assert call_count == 1
        for r in results:
            assert r.resolved_name == "Bengaluru"


@pytest.mark.asyncio
async def test_weather_service_stale_fallback_on_error():
    """Verify that if the upstream provider fails, an existing cached entry is served stale."""
    should_fail = False

    def handler(request: httpx.Request) -> httpx.Response:
        if should_fail:
            return httpx.Response(503, json={"error": {"message": "Provider outage"}})
        return httpx.Response(
            200,
            json={
                "location": {"name": "Jaipur", "lat": 26.91, "lon": 75.78},
                "current": {"temp_c": 35.0, "condition": {"text": "Sunny"}},
            },
        )

    mock_transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=mock_transport) as client:
        srv = WeatherService(api_key="mock_key", cache_ttl_seconds=1)

        # Populate cache
        obs_initial = await srv.get_current_weather(lat=26.9124, lon=75.7873, client=client)
        assert obs_initial.freshness == "fresh"

        # Now simulate provider failure and force refresh
        should_fail = True
        obs_stale = await srv.get_current_weather(
            lat=26.9124, lon=75.7873, force_refresh=True, client=client
        )
        assert obs_stale.freshness == "stale"
        assert obs_stale.is_cached is True
        assert obs_stale.stale_warning is not None
        assert "Upstream provider failure" in obs_stale.stale_warning


def test_api_weather_endpoints(client):
    # 1. Invalid coordinates
    resp = client.get("/api/weather/current?lat=95&lon=77")
    assert resp.status_code == 400
    assert "out of bounds" in resp.json()["detail"]

    # 2. Missing longitude
    resp = client.get("/api/weather/current?lat=20")
    assert resp.status_code == 400

    # 3. Health check diagnostics
    resp = client.get("/api/weather/health")
    assert resp.status_code == 200
    diag = resp.json()["diagnostics"]
    assert "service" in diag
    assert "is_configured" in diag
    assert "cache_total_entries" in diag
    assert "metrics" in diag
    # Ensure raw secret is not in diagnostics
    assert "key" not in diag
    assert "WEATHER_API_KEY" not in diag

    # 4. Snapshot endpoint
    resp = client.get("/api/weather/snapshot")
    assert resp.status_code == 200
    snap = resp.json()
    assert snap["ok"] is True
    assert snap["subcontinent"] == "India"
    assert snap["stations_count"] >= 6
    assert "STN-LEH" in snap["stations"]


def test_weather_deterministic_boundary():
    """Ensure weather queries never mutate SimEngine or break simulation math."""
    engine = SimEngine()
    evs1 = engine.start(seed=8841, scenario_id="SC-2")
    step1 = engine.step()

    # Query weather service diagnostics and cache
    diag = weather_service.get_diagnostics()
    assert diag["service"] == "WeatherAPI.com Integration"

    # Step simulation again
    step2 = engine.step()
    assert len(step2) > 0
    # Engine state ticks properly without interference
    assert engine.tick == 2
