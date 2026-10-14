"""WeatherAPI.com Current-Weather Client and Caching Service for DOIP.

Features:
- Secure credential management: reads WEATHER_API_KEY from environment only.
- Strict secret redaction: credentials are never logged, exposed in exceptions, or returned in APIs.
- Location-aware bounded in-memory cache with configurable TTL (default 15 minutes).
- In-flight request deduplication for concurrent lookups of the same location.
- Stale-on-error resilience: returns clearly marked stale observations on provider outage.
- Normalized internal schema matching DOIP environmental architecture.
- Provenance tagging: REAL_OBSERVATION, CACHED_REAL_DATA, SYNTHETIC_ENVIRONMENT.
- Strict deterministic separation: strictly isolated from SimEngine tick loop.
"""

from __future__ import annotations

import asyncio
import datetime
import logging
import os
from pathlib import Path
import re
from typing import Any, Literal
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
    load_dotenv()
    _root_env = Path(__file__).resolve().parent.parent.parent / ".env"
    if _root_env.exists():
        load_dotenv(_root_env)
except ImportError:
    pass

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger(__name__)

FreshnessType = Literal["fresh", "stale", "fallback"]
ProvenanceType = Literal["REAL_OBSERVATION", "CACHED_REAL_DATA", "SYNTHETIC_ENVIRONMENT"]

DEFAULT_CACHE_TTL_SECONDS = 900  # 15 minutes
MAX_CACHE_ENTRIES = 500
REQUEST_TIMEOUT_SECONDS = 3.5
WEATHERAPI_BASE_URL = "https://api.weatherapi.com/v1/current.json"


def redact_secrets(text: str, key: str | None = None) -> str:
    """Sanitize strings, URLs, and errors to prevent secret leakage."""
    if not text:
        return text
    # Redact URL query parameter ?key=... or &key=...
    sanitized = re.sub(r"([?&]key=)[^&]+", r"\1[REDACTED]", text)
    if key and len(key) >= 6:
        sanitized = sanitized.replace(key, "[REDACTED]")
    return sanitized


class WeatherObservation(BaseModel):
    """Normalized internal weather observation model for DOIP."""

    provider: str = "WeatherAPI.com"
    location_query: str
    resolved_name: str | None = None
    region: str | None = None
    country: str | None = None
    lat: float
    lon: float
    timezone_id: str | None = None
    provider_localtime: str | None = None
    provider_observation_time_epoch: int | None = None
    provider_observation_time_utc: str | None = None
    fetch_timestamp_utc: str
    temp_c: float | None = None
    feelslike_c: float | None = None
    temp_f: float | None = None
    feelslike_f: float | None = None
    humidity_pct: float | None = None
    wind_kph: float | None = None
    wind_mph: float | None = None
    wind_degree: int | None = None
    wind_dir: str | None = None
    gust_kph: float | None = None
    precip_mm: float | None = None
    cloud_pct: int | None = None
    visibility_km: float | None = None
    pressure_mb: float | None = None
    uv_index: float | None = None
    is_day: bool | None = None
    condition_text: str | None = None
    condition_icon: str | None = None
    condition_code: int | None = None
    provenance: ProvenanceType = "REAL_OBSERVATION"
    freshness: FreshnessType = "fresh"
    is_cached: bool = False
    cache_age_seconds: float = 0.0
    stale_warning: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class CacheEntry:
    """Internal cache entry holding observation and timestamps."""

    def __init__(self, observation: WeatherObservation, fetched_at: datetime.datetime, ttl: float) -> None:
        self.observation = observation
        self.fetched_at = fetched_at
        self.expires_at = fetched_at + datetime.timedelta(seconds=ttl)

    def is_fresh(self, now: datetime.datetime) -> bool:
        return now < self.expires_at

    def age_seconds(self, now: datetime.datetime) -> float:
        return max(0.0, (now - self.fetched_at).total_seconds())


class WeatherService:
    """Production client for WeatherAPI.com with caching, deduplication, and resilience."""

    def __init__(
        self,
        api_key: str | None = None,
        cache_ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_cache_size: int = MAX_CACHE_ENTRIES,
        timeout_seconds: float = REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        self._explicit_key = api_key
        self.cache_ttl = cache_ttl_seconds
        self.max_cache_size = max_cache_size
        self.timeout = timeout_seconds
        self._cache: dict[str, CacheEntry] = {}
        self._inflight_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Operational metrics
        self._metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_serves": 0,
            "provider_errors": 0,
            "last_error": None,
            "last_success_utc": None,
        }

    @property
    def api_key(self) -> str:
        """Retrieve key dynamically from environment or constructor."""
        if self._explicit_key:
            return self._explicit_key.strip()
        return os.getenv("WEATHER_API_KEY", "").strip()

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _normalize_coord_key(self, lat: float, lon: float) -> str:
        """Round coordinates to 2 decimal places (~1.1km resolution) for spatial cache sharing."""
        return f"coord:{lat:.2f}:{lon:.2f}"

    def _normalize_query_key(self, q: str) -> str:
        return f"q:{q.strip().lower()}"

    def _validate_coordinates(self, lat: float, lon: float) -> None:
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90, got {lat}")
        if not (-180.0 <= lon <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180, got {lon}")

    def _validate_query(self, q: str) -> str:
        cleaned = q.strip()
        if not cleaned:
            raise ValueError("Location query cannot be empty")
        if len(cleaned) > 100:
            raise ValueError("Location query exceeds maximum length of 100 characters")
        if re.search(r"[:/\\]", cleaned):
            raise ValueError("Location query contains invalid characters or URL schemes")
        return cleaned

    def _evict_if_needed(self) -> None:
        if len(self._cache) <= self.max_cache_size:
            return
        now = datetime.datetime.now(datetime.timezone.utc)
        # Evict expired entries first
        expired_keys = [k for k, entry in self._cache.items() if not entry.is_fresh(now)]
        for k in expired_keys:
            del self._cache[k]
        # If still over limit, evict oldest
        if len(self._cache) > self.max_cache_size:
            sorted_keys = sorted(self._cache.keys(), key=lambda k: self._cache[k].fetched_at)
            excess = len(self._cache) - self.max_cache_size
            for k in sorted_keys[:excess]:
                del self._cache[k]

    def _parse_provider_json(
        self, data: dict[str, Any], location_query: str, fetch_time: datetime.datetime
    ) -> WeatherObservation:
        """Safely normalize WeatherAPI.com current.json response into internal schema."""
        loc = data.get("location") or {}
        cur = data.get("current") or {}
        cond = cur.get("condition") or {}

        # Parse provider timestamps
        epoch = cur.get("last_updated_epoch")
        utc_ts = None
        if epoch:
            try:
                utc_ts = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()
            except Exception:
                pass

        lat_val = float(loc.get("lat", 0.0))
        lon_val = float(loc.get("lon", 0.0))

        return WeatherObservation(
            provider="WeatherAPI.com",
            location_query=location_query,
            resolved_name=loc.get("name"),
            region=loc.get("region"),
            country=loc.get("country"),
            lat=lat_val,
            lon=lon_val,
            timezone_id=loc.get("tz_id"),
            provider_localtime=loc.get("localtime"),
            provider_observation_time_epoch=epoch,
            provider_observation_time_utc=utc_ts,
            fetch_timestamp_utc=fetch_time.isoformat(),
            temp_c=float(cur["temp_c"]) if "temp_c" in cur and cur["temp_c"] is not None else None,
            feelslike_c=float(cur["feelslike_c"]) if "feelslike_c" in cur and cur["feelslike_c"] is not None else None,
            temp_f=float(cur["temp_f"]) if "temp_f" in cur and cur["temp_f"] is not None else None,
            feelslike_f=float(cur["feelslike_f"]) if "feelslike_f" in cur and cur["feelslike_f"] is not None else None,
            humidity_pct=float(cur["humidity"]) if "humidity" in cur and cur["humidity"] is not None else None,
            wind_kph=float(cur["wind_kph"]) if "wind_kph" in cur and cur["wind_kph"] is not None else None,
            wind_mph=float(cur["wind_mph"]) if "wind_mph" in cur and cur["wind_mph"] is not None else None,
            wind_degree=int(cur["wind_degree"]) if "wind_degree" in cur and cur["wind_degree"] is not None else None,
            wind_dir=cur.get("wind_dir"),
            gust_kph=float(cur["gust_kph"]) if "gust_kph" in cur and cur["gust_kph"] is not None else None,
            precip_mm=float(cur["precip_mm"]) if "precip_mm" in cur and cur["precip_mm"] is not None else None,
            cloud_pct=int(cur["cloud"]) if "cloud" in cur and cur["cloud"] is not None else None,
            visibility_km=float(cur["vis_km"]) if "vis_km" in cur and cur["vis_km"] is not None else None,
            pressure_mb=float(cur["pressure_mb"]) if "pressure_mb" in cur and cur["pressure_mb"] is not None else None,
            uv_index=float(cur["uv"]) if "uv" in cur and cur["uv"] is not None else None,
            is_day=bool(cur["is_day"]) if "is_day" in cur and cur["is_day"] is not None else None,
            condition_text=cond.get("text"),
            condition_icon=cond.get("icon"),
            condition_code=int(cond["code"]) if "code" in cond and cond["code"] is not None else None,
            provenance="REAL_OBSERVATION",
            freshness="fresh",
            is_cached=False,
            cache_age_seconds=0.0,
            stale_warning=None,
        )

    async def get_current_weather(
        self,
        lat: float | None = None,
        lon: float | None = None,
        query: str | None = None,
        force_refresh: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> WeatherObservation:
        """Fetch current weather with caching, deduplication, and resilient fallback."""
        now = datetime.datetime.now(datetime.timezone.utc)
        self._metrics["total_requests"] += 1

        # Determine location query string and cache key
        if lat is not None and lon is not None:
            self._validate_coordinates(lat, lon)
            loc_param = f"{lat:.4f},{lon:.4f}"
            cache_key = self._normalize_coord_key(lat, lon)
        elif query:
            cleaned = self._validate_query(query)
            loc_param = cleaned
            cache_key = self._normalize_query_key(cleaned)
        else:
            raise ValueError("Either lat/lon coordinates or a query string must be provided")

        # Check existing fresh cache
        if not force_refresh and cache_key in self._cache:
            entry = self._cache[cache_key]
            if entry.is_fresh(now):
                self._metrics["cache_hits"] += 1
                obs = entry.observation.model_copy()
                obs.is_cached = True
                obs.cache_age_seconds = round(entry.age_seconds(now), 1)
                obs.freshness = "fresh"
                obs.provenance = "CACHED_REAL_DATA"
                return obs

        # Check configuration
        key = self.api_key
        if not key:
            # Service not configured -> fallback or error
            cached_stale = self._cache.get(cache_key)
            if cached_stale:
                self._metrics["stale_serves"] += 1
                obs = cached_stale.observation.model_copy()
                obs.is_cached = True
                obs.freshness = "stale"
                obs.provenance = "CACHED_REAL_DATA"
                obs.cache_age_seconds = round(cached_stale.age_seconds(now), 1)
                obs.stale_warning = "API key unconfigured; serving cached observation"
                return obs

            raise RuntimeError("WeatherAPI.com is not configured (WEATHER_API_KEY missing)")

        # Request deduplication: acquire or create key-specific lock
        async with self._global_lock:
            if cache_key not in self._inflight_locks:
                self._inflight_locks[cache_key] = asyncio.Lock()
            lock = self._inflight_locks[cache_key]

        async with lock:
            # Check cache again inside lock in case another concurrent coroutine resolved it
            now_inside = datetime.datetime.now(datetime.timezone.utc)
            if not force_refresh and cache_key in self._cache:
                entry = self._cache[cache_key]
                if entry.is_fresh(now_inside):
                    self._metrics["cache_hits"] += 1
                    obs = entry.observation.model_copy()
                    obs.is_cached = True
                    obs.cache_age_seconds = round(entry.age_seconds(now_inside), 1)
                    obs.freshness = "fresh"
                    obs.provenance = "CACHED_REAL_DATA"
                    return obs

            self._metrics["cache_misses"] += 1

            # Prepare request with parameter encoding
            params = {"key": key, "q": loc_param, "aqi": "no"}
            url = WEATHERAPI_BASE_URL

            # Safe client usage
            owns_client = False
            http_client = client
            if http_client is None:
                http_client = httpx.AsyncClient(timeout=self.timeout)
                owns_client = True

            try:
                resp = await http_client.get(url, params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    obs = self._parse_provider_json(data, loc_param, now_inside)
                    self._cache[cache_key] = CacheEntry(obs, now_inside, self.cache_ttl)
                    self._evict_if_needed()
                    self._metrics["last_success_utc"] = now_inside.isoformat()
                    return obs

                # Provider non-200 response
                err_msg = f"WeatherAPI error HTTP {resp.status_code}"
                try:
                    err_json = resp.json()
                    if "error" in err_json and "message" in err_json["error"]:
                        err_msg += f": {err_json['error']['message']}"
                except Exception:
                    pass

                sanitized_err = redact_secrets(err_msg, key)
                log.warning("WeatherAPI fetch failed: %s", sanitized_err)
                self._metrics["provider_errors"] += 1
                self._metrics["last_error"] = sanitized_err

                # Try stale cache fallback
                if cache_key in self._cache:
                    cached = self._cache[cache_key]
                    self._metrics["stale_serves"] += 1
                    obs = cached.observation.model_copy()
                    obs.is_cached = True
                    obs.freshness = "stale"
                    obs.provenance = "CACHED_REAL_DATA"
                    obs.cache_age_seconds = round(cached.age_seconds(now_inside), 1)
                    obs.stale_warning = f"Upstream provider failure ({resp.status_code}); serving stale cached data"
                    return obs

                raise RuntimeError(sanitized_err)

            except Exception as exc:
                sanitized_exc = redact_secrets(str(exc), key)
                log.warning("WeatherAPI exception: %s", sanitized_exc)
                self._metrics["provider_errors"] += 1
                self._metrics["last_error"] = sanitized_exc

                # Return stale cache if available
                if cache_key in self._cache:
                    cached = self._cache[cache_key]
                    self._metrics["stale_serves"] += 1
                    obs = cached.observation.model_copy()
                    obs.is_cached = True
                    obs.freshness = "stale"
                    obs.provenance = "CACHED_REAL_DATA"
                    obs.cache_age_seconds = round(cached.age_seconds(now_inside), 1)
                    obs.stale_warning = f"Upstream connection failed: {sanitized_exc}; serving stale cached data"
                    return obs

                raise RuntimeError(f"Weather service unavailable: {sanitized_exc}") from None

            finally:
                if owns_client:
                    await http_client.aclose()

    def get_diagnostics(self) -> dict[str, Any]:
        """Return non-sensitive operational health and diagnostics."""
        now = datetime.datetime.now(datetime.timezone.utc)
        fresh_count = sum(1 for e in self._cache.values() if e.is_fresh(now))
        return {
            "service": "WeatherAPI.com Integration",
            "is_configured": self.is_configured,
            "cache_ttl_seconds": self.cache_ttl,
            "cache_total_entries": len(self._cache),
            "cache_fresh_entries": fresh_count,
            "metrics": dict(self._metrics),
        }

    def clear_cache(self) -> None:
        self._cache.clear()


# Singleton
weather_service = WeatherService()
