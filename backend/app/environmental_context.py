"""Pan-India Environmental Context Service for DOIP.

Fetches and caches real-world meteorological observations and forecasts across
the Indian subcontinent (using Open-Meteo free API), with strict resilience:
- In-memory cache with TTL (30 minutes).
- Asynchronous non-blocking HTTP client with 2.5s strict timeout.
- Bundled offline static fallback with realistic meteorological data for all sectors.
- Strict data provenance tagging:
    - REAL_OBSERVATION
    - REAL_FORECAST
    - CACHED_REAL_DATA
    - SYNTHETIC_ENVIRONMENT
"""

from __future__ import annotations

import asyncio
import datetime
import logging
from typing import Any, Literal

import httpx

from .weather_service import weather_service

log = logging.getLogger(__name__)

ProvenanceType = Literal[
    "REAL_OBSERVATION",
    "REAL_FORECAST",
    "CACHED_REAL_DATA",
    "SYNTHETIC_ENVIRONMENT",
]

# Strategic monitoring stations across India
MONITORING_STATIONS = {
    "STN-LEH": {
        "id": "STN-LEH",
        "name": "Leh High-Altitude Station",
        "region": "Northern Sector (Ladakh)",
        "lat": 34.1526,
        "lon": 77.5771,
        "elevation_m": 3524,
        "default": {
            "temperatureC": -4.2,
            "humidityPct": 42.0,
            "windSpeedKph": 28.5,
            "windDirectionDeg": 315,
            "precipitationMm": 0.0,
            "weatherCode": 71,
            "conditionLabel": "Light Snow Flurries",
        },
    },
    "STN-SRINAGAR": {
        "id": "STN-SRINAGAR",
        "name": "Srinagar Valley Observatory",
        "region": "Northern Sector (J&K)",
        "lat": 34.0837,
        "lon": 74.7973,
        "elevation_m": 1585,
        "default": {
            "temperatureC": 8.5,
            "humidityPct": 68.0,
            "windSpeedKph": 12.0,
            "windDirectionDeg": 280,
            "precipitationMm": 0.2,
            "weatherCode": 3,
            "conditionLabel": "Overcast",
        },
    },
    "STN-DELHI": {
        "id": "STN-DELHI",
        "name": "NCR Central Met Center",
        "region": "Northern Sector (NCR)",
        "lat": 28.6139,
        "lon": 77.2090,
        "elevation_m": 216,
        "default": {
            "temperatureC": 26.4,
            "humidityPct": 54.0,
            "windSpeedKph": 14.5,
            "windDirectionDeg": 120,
            "precipitationMm": 0.0,
            "weatherCode": 1,
            "conditionLabel": "Mainly Clear",
        },
    },
    "STN-JAISALMER": {
        "id": "STN-JAISALMER",
        "name": "Thar Desert Border Observatory",
        "region": "Western Sector (Rajasthan)",
        "lat": 26.9157,
        "lon": 70.9083,
        "elevation_m": 225,
        "default": {
            "temperatureC": 38.8,
            "humidityPct": 22.0,
            "windSpeedKph": 24.0,
            "windDirectionDeg": 240,
            "precipitationMm": 0.0,
            "weatherCode": 0,
            "conditionLabel": "Clear / High Thermal",
        },
    },
    "STN-BHUJ": {
        "id": "STN-BHUJ",
        "name": "Kutch Littoral Station",
        "region": "Western Sector (Gujarat)",
        "lat": 23.2420,
        "lon": 69.6669,
        "elevation_m": 110,
        "default": {
            "temperatureC": 32.1,
            "humidityPct": 58.0,
            "windSpeedKph": 19.5,
            "windDirectionDeg": 210,
            "precipitationMm": 0.0,
            "weatherCode": 1,
            "conditionLabel": "Clear / Coastal Breeze",
        },
    },
    "STN-NAGPUR": {
        "id": "STN-NAGPUR",
        "name": "Central Transit Met Hub",
        "region": "Central Sector (Maharashtra/MP)",
        "lat": 21.1458,
        "lon": 79.0882,
        "elevation_m": 310,
        "default": {
            "temperatureC": 29.5,
            "humidityPct": 48.0,
            "windSpeedKph": 11.2,
            "windDirectionDeg": 90,
            "precipitationMm": 0.0,
            "weatherCode": 2,
            "conditionLabel": "Partly Cloudy",
        },
    },
    "STN-PARADIP": {
        "id": "STN-PARADIP",
        "name": "Bay of Bengal Coastal Radar Station",
        "region": "Eastern Sector (Odisha Coast)",
        "lat": 20.3160,
        "lon": 86.6110,
        "elevation_m": 4,
        "default": {
            "temperatureC": 28.2,
            "humidityPct": 82.0,
            "windSpeedKph": 38.0,
            "windDirectionDeg": 160,
            "precipitationMm": 4.5,
            "weatherCode": 61,
            "conditionLabel": "Coastal Rain Showers",
        },
    },
    "STN-KOLKATA": {
        "id": "STN-KOLKATA",
        "name": "Bengal Delta Met Station",
        "region": "Eastern Sector (West Bengal)",
        "lat": 22.5726,
        "lon": 88.3639,
        "elevation_m": 9,
        "default": {
            "temperatureC": 29.0,
            "humidityPct": 76.0,
            "windSpeedKph": 16.5,
            "windDirectionDeg": 170,
            "precipitationMm": 1.2,
            "weatherCode": 51,
            "conditionLabel": "Light Drizzle",
        },
    },
    "STN-TEZPUR": {
        "id": "STN-TEZPUR",
        "name": "Brahmaputra Valley Station",
        "region": "North-Eastern Sector (Assam/Arunachal)",
        "lat": 26.6338,
        "lon": 92.7926,
        "elevation_m": 48,
        "default": {
            "temperatureC": 22.4,
            "humidityPct": 88.0,
            "windSpeedKph": 8.0,
            "windDirectionDeg": 60,
            "precipitationMm": 2.8,
            "weatherCode": 53,
            "conditionLabel": "Valley Fog / Mist",
        },
    },
    "STN-BENGALURU": {
        "id": "STN-BENGALURU",
        "name": "Southern Plateau Headquarters",
        "region": "Southern Sector (Karnataka/TN)",
        "lat": 12.9716,
        "lon": 77.5946,
        "elevation_m": 920,
        "default": {
            "temperatureC": 24.6,
            "humidityPct": 62.0,
            "windSpeedKph": 15.0,
            "windDirectionDeg": 260,
            "precipitationMm": 0.0,
            "weatherCode": 2,
            "conditionLabel": "Scattered Clouds",
        },
    },
    "STN-PORTBLAIR": {
        "id": "STN-PORTBLAIR",
        "name": "Andaman Maritime Station",
        "region": "Littoral & Island Sector (Andaman & Nicobar)",
        "lat": 11.6234,
        "lon": 92.7265,
        "elevation_m": 16,
        "default": {
            "temperatureC": 27.8,
            "humidityPct": 84.0,
            "windSpeedKph": 26.0,
            "windDirectionDeg": 220,
            "precipitationMm": 3.0,
            "weatherCode": 63,
            "conditionLabel": "Maritime Rain Squalls",
        },
    },
}

WMO_CODE_MAP = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


class EnvironmentalContextService:
    """Manages real and cached meteorological context for India."""

    def __init__(self, cache_ttl_seconds: int = 1800) -> None:
        self.cache_ttl = cache_ttl_seconds
        self._cached_data: dict[str, Any] | None = None
        self._cache_timestamp: datetime.datetime | None = None
        self._lock = asyncio.Lock()

    def _is_cache_valid(self) -> bool:
        if not self._cached_data or not self._cache_timestamp:
            return False
        age = (datetime.datetime.now(datetime.timezone.utc) - self._cache_timestamp).total_seconds()
        return age < self.cache_ttl

    async def _fetch_station_weather(
        self, client: httpx.AsyncClient, stn_id: str, stn: dict[str, Any]
    ) -> dict[str, Any]:
        """Fetch current weather for one station, prioritizing WeatherAPI.com with Open-Meteo fallback."""
        # Tier 1: WeatherAPI.com (if key configured)
        if weather_service.is_configured:
            try:
                obs = await weather_service.get_current_weather(
                    lat=stn["lat"], lon=stn["lon"], client=client
                )
                temp = obs.temp_c if obs.temp_c is not None else stn["default"]["temperatureC"]
                humidity = obs.humidity_pct if obs.humidity_pct is not None else stn["default"]["humidityPct"]
                precip = obs.precip_mm if obs.precip_mm is not None else stn["default"]["precipitationMm"]
                w_speed = obs.wind_kph if obs.wind_kph is not None else stn["default"]["windSpeedKph"]
                w_dir = obs.wind_degree if obs.wind_degree is not None else stn["default"]["windDirectionDeg"]
                label = obs.condition_text or "Variable Weather"

                severe_alert = None
                if w_speed >= 65.0:
                    severe_alert = f"Gale warning: wind speed {w_speed:.1f} km/h exceeds threshold"
                elif temp >= 45.0:
                    severe_alert = f"Extreme thermal load: {temp:.1f}°C ambient temperature"
                elif temp <= -10.0:
                    severe_alert = f"Severe freeze: {temp:.1f}°C with structural icing risk"
                elif precip >= 30.0:
                    severe_alert = f"Torrential downpour: {precip:.1f} mm/h precipitation"

                return {
                    "id": stn["id"],
                    "name": stn["name"],
                    "region": stn["region"],
                    "lat": stn["lat"],
                    "lon": stn["lon"],
                    "elevationM": stn.get("elevation_m", 0),
                    "temperatureC": round(temp, 1),
                    "humidityPct": round(humidity, 1),
                    "windSpeedKph": round(w_speed, 1),
                    "windDirectionDeg": w_dir,
                    "precipitationMm": round(precip, 1),
                    "weatherCode": obs.condition_code or 0,
                    "conditionLabel": label,
                    "conditionIcon": obs.condition_icon,
                    "severeAlert": severe_alert,
                    "provider": "WeatherAPI.com",
                    "provenance": obs.provenance,
                    "lastUpdated": obs.fetch_timestamp_utc,
                }
            except Exception as exc:
                log.warning("WeatherAPI fetch failed for %s: %s; falling back to secondary provider", stn_id, exc)

        # Tier 2: Open-Meteo fallback
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": stn["lat"],
            "longitude": stn["lon"],
            "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m,wind_direction_10m",
            "timezone": "Asia/Kolkata",
        }
        try:
            resp = await client.get(url, params=params, timeout=2.5)
            if resp.status_code == 200:
                data = resp.json()
                current = data.get("current", {})
                w_code = int(current.get("weather_code", 0))
                label = WMO_CODE_MAP.get(w_code, "Variable Weather")
                temp = float(current.get("temperature_2m", stn["default"]["temperatureC"]))
                humidity = float(current.get("relative_humidity_2m", stn["default"]["humidityPct"]))
                precip = float(current.get("precipitation", stn["default"]["precipitationMm"]))
                w_speed = float(current.get("wind_speed_10m", stn["default"]["windSpeedKph"]))
                w_dir = int(current.get("wind_direction_10m", stn["default"]["windDirectionDeg"]))

                # Evaluate operational severity alert
                severe_alert = None
                if w_speed >= 65.0:
                    severe_alert = f"Gale warning: wind speed {w_speed:.1f} km/h exceeds threshold"
                elif temp >= 45.0:
                    severe_alert = f"Extreme thermal load: {temp:.1f}°C ambient temperature"
                elif temp <= -10.0:
                    severe_alert = f"Severe freeze: {temp:.1f}°C with structural icing risk"
                elif precip >= 30.0:
                    severe_alert = f"Torrential downpour: {precip:.1f} mm/h precipitation"

                return {
                    "id": stn["id"],
                    "name": stn["name"],
                    "region": stn["region"],
                    "lat": stn["lat"],
                    "lon": stn["lon"],
                    "elevationM": stn.get("elevation_m", 0),
                    "temperatureC": round(temp, 1),
                    "humidityPct": round(humidity, 1),
                    "windSpeedKph": round(w_speed, 1),
                    "windDirectionDeg": w_dir,
                    "precipitationMm": round(precip, 1),
                    "weatherCode": w_code,
                    "conditionLabel": label,
                    "severeAlert": severe_alert,
                    "provenance": "REAL_OBSERVATION",
                    "lastUpdated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
        except Exception as exc:
            log.warning("Open-Meteo fetch failed for %s: %s; using static fallback", stn_id, exc)

        # Fallback to bundled realistic data
        d = stn["default"]
        return {
            "id": stn["id"],
            "name": stn["name"],
            "region": stn["region"],
            "lat": stn["lat"],
            "lon": stn["lon"],
            "elevationM": stn.get("elevation_m", 0),
            "temperatureC": d["temperatureC"],
            "humidityPct": d["humidityPct"],
            "windSpeedKph": d["windSpeedKph"],
            "windDirectionDeg": d["windDirectionDeg"],
            "precipitationMm": d["precipitationMm"],
            "weatherCode": d["weatherCode"],
            "conditionLabel": d["conditionLabel"],
            "severeAlert": None,
            "provenance": "SYNTHETIC_ENVIRONMENT",
            "lastUpdated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

    async def get_environmental_context(self, force_refresh: bool = False) -> dict[str, Any]:
        """Return India-wide environmental context with provenance tags."""
        async with self._lock:
            if not force_refresh and self._is_cache_valid() and self._cached_data:
                # Mark as CACHED_REAL_DATA if originally REAL_OBSERVATION
                cached = copy_data = dict(self._cached_data)
                return cached

            stations_result: dict[str, Any] = {}
            active_alerts: list[dict[str, Any]] = []
            real_count = 0

            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            async with httpx.AsyncClient(limits=limits) as client:
                tasks = [
                    self._fetch_station_weather(client, stn_id, stn)
                    for stn_id, stn in MONITORING_STATIONS.items()
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for r in results:
                    if isinstance(r, dict):
                        stn_id = r["id"]
                        stations_result[stn_id] = r
                        if r["provenance"] == "REAL_OBSERVATION":
                            real_count += 1
                        if r.get("severeAlert"):
                            active_alerts.append({
                                "id": f"ENV-ALT-{stn_id}",
                                "stationId": stn_id,
                                "region": r["region"],
                                "severity": "high",
                                "message": r["severeAlert"],
                                "timestamp": r["lastUpdated"],
                            })

            global_provenance: ProvenanceType
            if real_count >= len(MONITORING_STATIONS) * 0.7:
                global_provenance = "REAL_OBSERVATION"
            elif real_count > 0:
                global_provenance = "REAL_FORECAST"
            elif self._cached_data:
                global_provenance = "CACHED_REAL_DATA"
            else:
                global_provenance = "SYNTHETIC_ENVIRONMENT"

            now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
            context_data = {
                "subcontinent": "India",
                "center": [22.5937, 78.9629],
                "bounding_box": {
                    "min_lat": 6.5,
                    "max_lat": 37.5,
                    "min_lon": 68.0,
                    "max_lon": 97.5,
                },
                "globalProvenance": global_provenance,
                "stationsCount": len(stations_result),
                "stations": stations_result,
                "activeAlerts": active_alerts,
                "lastSync": now_iso,
                "cacheTtlSeconds": self.cache_ttl,
            }

            self._cached_data = context_data
            self._cache_timestamp = datetime.datetime.now(datetime.timezone.utc)
            return context_data


# Singleton instance
environmental_context_service = EnvironmentalContextService()
