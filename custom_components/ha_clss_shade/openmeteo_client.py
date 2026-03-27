"""Open-Meteo client — fetch current GHI and hourly forecast."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiohttp

_LOGGER = logging.getLogger(__name__)

OPENMETEO_URL = "https://api.open-meteo.com/v1/forecast"


async def fetch_openmeteo_forecast(
    session: aiohttp.ClientSession,
    lat: float,
    lon: float,
    forecast_days: int = 5,
) -> list[dict]:
    """Fetch hourly GHI + temperature + cloud forecast from Open-Meteo.

    Free, no API key, global coverage, 1-hour resolution.
    Uses the same Copernicus/ECMWF models as professional weather services.

    Returns:
        List of dicts with keys: datetime, ghi, temperature, cloud_coverage.
        Empty list on failure.
    """
    try:
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "hourly": "shortwave_radiation,temperature_2m,cloud_cover",
            "forecast_days": forecast_days,
            "timezone": "UTC",
        }
        async with session.get(
            OPENMETEO_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("Open-Meteo forecast fetch failed: HTTP %d", resp.status)
                return []
            data = await resp.json()

        hourly = data.get("hourly", {})
        times = hourly.get("time", [])
        ghi_values = hourly.get("shortwave_radiation", [])
        temp_values = hourly.get("temperature_2m", [])
        cloud_values = hourly.get("cloud_cover", [])

        if not times:
            return []

        result = []
        for i, t_str in enumerate(times):
            result.append({
                "datetime": t_str,
                "ghi": ghi_values[i] if i < len(ghi_values) else None,
                "temperature": temp_values[i] if i < len(temp_values) else None,
                "cloud_coverage": cloud_values[i] if i < len(cloud_values) else None,
            })

        _LOGGER.info(
            "Open-Meteo forecast: %d hourly entries for %d days",
            len(result), forecast_days,
        )
        return result

    except Exception:
        _LOGGER.exception("Open-Meteo forecast fetch failed")
        return []


async def fetch_openmeteo_ghi(
    session: aiohttp.ClientSession,
    lat: float,
    lon: float,
) -> tuple[float | None, str | None]:
    """Fetch current GHI from Open-Meteo (free, no API key, global).

    Requests the closest 15-minute shortwave radiation instant value.
    Used as fallback when INCA does not cover the location.

    Returns:
        Tuple of (ghi_wm2, timestamp_iso) or (None, None) on failure.
    """
    try:
        params = {
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "minutely_15": "shortwave_radiation_instant",
            "forecast_minutely_15": 4,
            "timezone": "UTC",
        }
        async with session.get(
            OPENMETEO_URL,
            params=params,
            timeout=aiohttp.ClientTimeout(total=10),
        ) as resp:
            if resp.status != 200:
                _LOGGER.warning("Open-Meteo fetch failed: HTTP %d", resp.status)
                return None, None
            data = await resp.json()

        minutely = data.get("minutely_15", {})
        times = minutely.get("time", [])
        values = minutely.get("shortwave_radiation_instant", [])

        if not times or not values:
            return None, None

        # Find the value closest to now
        now = datetime.now(tz=timezone.utc)
        best_idx = 0
        best_diff = float("inf")
        for i, t_str in enumerate(times):
            try:
                t = datetime.fromisoformat(t_str).replace(tzinfo=timezone.utc)
                diff = abs((t - now).total_seconds())
                if diff < best_diff:
                    best_diff = diff
                    best_idx = i
            except ValueError:
                continue

        ghi = values[best_idx]
        timestamp = times[best_idx]

        if ghi is not None and ghi >= 0:
            _LOGGER.debug(
                "Open-Meteo GHI at (%.4f,%.4f): %.1f W/m² @ %s",
                lat, lon, ghi, timestamp,
            )
            return round(float(ghi), 1), timestamp

        return None, None

    except Exception:
        _LOGGER.exception("Open-Meteo fetch failed")
        return None, None
