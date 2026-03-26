"""Bridge to slovenian_weather_integration — reads ARSO weather entities from HA."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Entity ID patterns from slovenian_weather_integration
# Weather sensors: sensor.arso_weather_{location}_{sensor_name}
# Agrometeo overview: sensor.arso_agrometeo_{station} (has 'dnevi' attribute)
# Agrometeo value: sensor.arso_agrometeo_{station}_{field}

ARSO_DOMAIN = "slovenian_weather_integration"


@dataclass
class AgroDayData:
    """Single day of agrometeo data."""

    datum: str = ""
    tip: str = ""  # "meritev", "danes", "napoved"
    evapotranspiracija_mm: float | None = None
    vodna_bilanca_mm: float | None = None
    padavine_24h_mm: float | None = None
    povprecna_temperatura_C: float | None = None
    trajanje_sonca_h: float | None = None


@dataclass
class ArsoWeatherData:
    """Current weather data from ARSO sensors."""

    solar_radiation: float | None = None  # W/m² (global)
    diffuse_radiation: float | None = None  # W/m²
    cloud_coverage: float | None = None  # %
    temperature: float | None = None  # °C
    humidity: float | None = None  # %
    evapotranspiration: float | None = None  # mm (today or best available)
    water_balance: float | None = None  # mm (today or best available)
    precipitation_forecast: float | None = None  # mm
    # Multi-day agrometeo data for attributes
    agro_days: list[AgroDayData] = field(default_factory=list)
    agro_source: str = ""  # "meritev", "napoved", etc.


def find_arso_entities(hass: HomeAssistant) -> dict[str, str]:
    """Find available ARSO weather entities in HA.

    Searches for slovenian_weather_integration entities and returns
    a mapping of data type to entity_id.
    """
    found: dict[str, str] = {}
    states = hass.states.async_all("sensor")

    # Weather sensor patterns (Slovenian names)
    weather_patterns = {
        "solar_radiation": "globalno_soncno_sevanje",
        "diffuse_radiation": "difuzno_soncno_sevanje",
        "cloud_coverage": "oblacnost",
        "temperature": "temperatura",
        "humidity": "relativna_vlaznost",
    }

    for state in states:
        eid = state.entity_id
        if "arso" not in eid:
            continue

        # Weather sensors
        for key, pattern in weather_patterns.items():
            if pattern in eid and key not in found:
                found[key] = eid

        # Agrometeo overview sensor (has 'dnevi' attribute)
        if "arso_agrometeo_" in eid and "agrometeo_overview" not in found:
            attrs = state.attributes or {}
            if "dnevi" in attrs:
                found["agrometeo_overview"] = eid
                _LOGGER.debug("Found agrometeo overview: %s", eid)

        # Fallback: individual agrometeo value sensors
        if "evapotranspiracija" in eid and "evapotranspiration" not in found:
            found["evapotranspiration"] = eid
        if "vodna_bilanca" in eid and "water_balance" not in found:
            found["water_balance"] = eid

    if found:
        _LOGGER.info("Found %d ARSO weather entities", len(found))
    else:
        _LOGGER.info("No ARSO weather entities found — weather bridge disabled")

    return found


def _parse_agro_days(dnevi: list[dict]) -> list[AgroDayData]:
    """Parse the 'dnevi' attribute array into AgroDayData objects."""
    result = []
    for day in dnevi:
        if not isinstance(day, dict):
            continue
        result.append(
            AgroDayData(
                datum=day.get("datum", ""),
                tip=day.get("tip", ""),
                evapotranspiracija_mm=_safe_float(day.get("evapotranspiracija_mm")),
                vodna_bilanca_mm=_safe_float(day.get("vodna_bilanca_mm")),
                padavine_24h_mm=_safe_float(day.get("padavine_24h_mm")),
                povprecna_temperatura_C=_safe_float(day.get("povprecna_temperatura_C")),
                trajanje_sonca_h=_safe_float(day.get("trajanje_sonca_h")),
            )
        )
    return result


def _safe_float(val: Any) -> float | None:
    """Convert to float or return None."""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _find_best_agro_day(
    days: list[AgroDayData], target_date: str
) -> tuple[AgroDayData | None, str]:
    """Find the best agrometeo day data.

    Priority:
    1. Today's measurement ("danes" or matching date with "meritev")
    2. Today's forecast (matching date with "napoved")
    3. Most recent forecast
    4. Most recent measurement

    Returns:
        Tuple of (day_data, source_description).
    """
    today_measurement = None
    today_forecast = None
    latest_forecast = None
    latest_measurement = None

    for day in days:
        is_today = day.datum == target_date
        has_etp = day.evapotranspiracija_mm is not None

        if not has_etp:
            continue

        if day.tip == "danes" or (is_today and day.tip == "meritev"):
            today_measurement = day
        elif is_today and day.tip == "napoved":
            today_forecast = day
        elif day.tip == "napoved":
            latest_forecast = day  # last one wins (they're chronological)
        elif day.tip == "meritev":
            latest_measurement = day

    if today_measurement:
        return today_measurement, f"meritev ({target_date})"
    if today_forecast:
        return today_forecast, f"napoved ({target_date})"
    if latest_forecast:
        return latest_forecast, f"napoved ({latest_forecast.datum})"
    if latest_measurement:
        return latest_measurement, f"meritev ({latest_measurement.datum})"

    return None, ""


def _find_agrometeo_overview(hass: HomeAssistant) -> tuple[list[AgroDayData], str]:
    """Find and read agrometeo overview sensor with 'dnevi' attribute.

    Scans all sensors every time to handle late-loading entities.
    """
    states = hass.states.async_all("sensor")
    for state in states:
        eid = state.entity_id
        if "arso_agrometeo" not in eid:
            continue
        attrs = state.attributes or {}
        dnevi = attrs.get("dnevi")
        if not isinstance(dnevi, list) or not dnevi:
            continue
        agro_days = _parse_agro_days(dnevi)
        if agro_days:
            _LOGGER.debug("Read agrometeo from %s: %d days", eid, len(agro_days))
            return agro_days, eid

    return [], ""


def read_arso_weather(
    hass: HomeAssistant,
    entity_map: dict[str, str],
) -> ArsoWeatherData:
    """Read current values from ARSO weather entities.

    Reads weather sensors directly and agrometeo data from the
    overview sensor's 'dnevi' attribute for multi-day data.
    """
    data = ArsoWeatherData()
    today_str = date.today().isoformat()

    # Read weather sensors (radiation, temperature, etc.)
    for key in ("solar_radiation", "diffuse_radiation", "cloud_coverage",
                "temperature", "humidity"):
        entity_id = entity_map.get(key)
        if not entity_id:
            continue
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            continue
        val = _safe_float(state.state)
        if val is not None:
            setattr(data, key, val)

    # Read agrometeo: scan for overview sensor every time (handles late loading)
    agro_days, overview_eid = _find_agrometeo_overview(hass)
    if agro_days:
        data.agro_days = agro_days
        best_day, source = _find_best_agro_day(agro_days, today_str)
        if best_day:
            data.evapotranspiration = best_day.evapotranspiracija_mm
            data.water_balance = best_day.vodna_bilanca_mm
            data.precipitation_forecast = best_day.padavine_24h_mm
            data.agro_source = source
            _LOGGER.debug(
                "Agrometeo [%s] %s: ETP=%.1f, wBal=%.1f",
                overview_eid, source,
                best_day.evapotranspiracija_mm or 0,
                best_day.vodna_bilanca_mm or 0,
            )

    # Fallback: read individual agrometeo value sensors
    if data.evapotranspiration is None:
        eid = entity_map.get("evapotranspiration")
        if eid:
            state = hass.states.get(eid)
            if state and state.state not in ("unknown", "unavailable"):
                data.evapotranspiration = _safe_float(state.state)
                data.agro_source = "value_sensor"

    if data.water_balance is None:
        eid = entity_map.get("water_balance")
        if eid:
            state = hass.states.get(eid)
            if state and state.state not in ("unknown", "unavailable"):
                data.water_balance = _safe_float(state.state)

    return data


def compute_poa_factor(
    sun_elevation: float,
    sun_azimuth: float,
    panel_tilt: float = 30.0,
    panel_azimuth: float = 180.0,
) -> float:
    """Compute Plane-of-Array factor: ratio of radiation on tilted panel vs horizontal.

    Args:
        sun_elevation: Sun elevation in degrees (0=horizon, 90=zenith).
        sun_azimuth: Sun azimuth in degrees (0=N, 90=E, 180=S, 270=W).
        panel_tilt: Panel tilt from horizontal in degrees (0=flat, 90=vertical).
        panel_azimuth: Panel facing direction in degrees (180=south).

    Returns:
        POA factor (typically 1.0-1.5 for well-oriented panels).
    """
    import math

    if sun_elevation <= 0:
        return 0.0

    sun_el_rad = math.radians(sun_elevation)
    sun_az_rad = math.radians(sun_azimuth)
    tilt_rad = math.radians(panel_tilt)
    panel_az_rad = math.radians(panel_azimuth)

    # Cosine of angle of incidence on tilted surface
    cos_incidence = (
        math.sin(sun_el_rad) * math.cos(tilt_rad)
        + math.cos(sun_el_rad) * math.sin(tilt_rad)
        * math.cos(sun_az_rad - panel_az_rad)
    )

    # Cosine of zenith angle (= sin of elevation)
    sin_elevation = math.sin(sun_el_rad)

    if sin_elevation <= 0.01:
        return 0.0

    # Direct component ratio
    direct_factor = max(0.0, cos_incidence / sin_elevation)

    # Diffuse component: isotropic model (view factor of tilted surface to sky)
    diffuse_factor = (1.0 + math.cos(tilt_rad)) / 2.0

    # Typical split: ~70% direct, ~30% diffuse (varies with clouds)
    poa_factor = direct_factor * 0.7 + diffuse_factor * 0.3

    # Clamp to reasonable range
    return max(0.0, min(poa_factor, 3.0))


def estimate_pv_power(
    sun_percent: float,
    solar_radiation: float | None,
    cloud_coverage: float | None = None,
    panel_capacity_wp: float = 5000.0,
    poa_factor: float = 1.2,
    system_losses: float = 0.08,
) -> float | None:
    """Estimate PV power output combining shade analysis with solar radiation.

    Args:
        sun_percent: Percentage of direct sunlight on the PV zone (0-100).
        solar_radiation: Measured global horizontal radiation in W/m² from ARSO.
        cloud_coverage: Cloud coverage percentage (0-100) from ARSO.
        panel_capacity_wp: Installed PV capacity in Wp.
        poa_factor: Plane-of-array factor from compute_poa_factor().
        system_losses: System losses (inverter, wiring, temperature) as fraction.

    Returns:
        Estimated power output in Watts, or None if no data.
    """
    if sun_percent <= 0:
        return 0.0

    sun_fraction = sun_percent / 100.0

    if solar_radiation is not None and solar_radiation > 0:
        # Apply POA correction: tilted panels vs horizontal measurement
        poa_radiation = solar_radiation * poa_factor

        # Shade adjustment: in shade, only diffuse reaches panels (~20%)
        effective_radiation = poa_radiation * (sun_fraction * 0.8 + 0.2)

        # Standard test conditions: 1000 W/m²
        power = panel_capacity_wp * (effective_radiation / 1000.0) * (1 - system_losses)
        return round(max(0.0, power), 1)

    # Fallback: estimate from cloud coverage
    if cloud_coverage is not None:
        cloud_factor = 1.0 - (cloud_coverage / 100.0) * 0.75
        estimated_radiation = 800.0 * cloud_factor * poa_factor
        effective_radiation = estimated_radiation * (sun_fraction * 0.8 + 0.2)
        power = panel_capacity_wp * (effective_radiation / 1000.0) * (1 - system_losses)
        return round(max(0.0, power), 1)

    return None


def find_weather_entity(hass: HomeAssistant) -> str:
    """Find the ARSO weather entity for forecast data.

    Searches for a weather.* entity from slovenian_weather_integration.

    Returns:
        Entity ID string, or empty string if not found.
    """
    for state in hass.states.async_all("weather"):
        if "arso" in state.entity_id:
            _LOGGER.info("Found ARSO weather entity for forecasts: %s", state.entity_id)
            return state.entity_id
    _LOGGER.debug("No ARSO weather entity found for forecasts")
    return ""


async def fetch_weather_forecast(
    hass: HomeAssistant,
    weather_entity_id: str,
) -> list[dict]:
    """Fetch hourly weather forecast via weather.get_forecasts service.

    Uses the HA weather.get_forecasts service (available since HA 2023.12).
    The slovenian_weather_integration provides 3-hour interval forecasts
    for 6 days via this service.

    Returns:
        List of forecast entries with keys: datetime, condition, temperature,
        cloud_coverage, precipitation.
    """
    if not weather_entity_id:
        return []

    try:
        response = await hass.services.async_call(
            "weather",
            "get_forecasts",
            {"type": "hourly", "entity_id": weather_entity_id},
            blocking=True,
            return_response=True,
        )
    except Exception:
        _LOGGER.exception("Failed to call weather.get_forecasts for %s", weather_entity_id)
        return []

    # Response format: {entity_id: {"forecast": [...]}}
    entity_data = response.get(weather_entity_id, {})
    raw_forecast = entity_data.get("forecast", [])

    result = []
    for entry in raw_forecast:
        result.append({
            "datetime": entry.get("datetime"),
            "condition": entry.get("condition"),
            "temperature": _safe_float(entry.get("temperature")),
            "cloud_coverage": _safe_float(entry.get("cloud_coverage")),
            "precipitation": _safe_float(entry.get("precipitation")),
        })

    _LOGGER.debug("Weather forecast: %d entries from %s", len(result), weather_entity_id)
    return result


def estimate_irrigation_need(
    shade_percent: float,
    evapotranspiration: float | None,
    water_balance: float | None,
    precipitation_forecast: float | None,
    area_m2: float = 100.0,
) -> float | None:
    """Estimate irrigation need combining shade analysis with agrometeo data.

    Shaded areas need less water due to reduced evapotranspiration.

    Args:
        shade_percent: Average shade percentage for the zone (0-100).
        evapotranspiration: Daily ETP from ARSO agrometeo (mm).
        water_balance: Water balance from ARSO (mm). Negative = deficit.
        precipitation_forecast: Expected precipitation next 24h (mm).
        area_m2: Zone area in m².

    Returns:
        Estimated irrigation need in liters, or None if insufficient data.
    """
    if evapotranspiration is None:
        return None

    # Shade reduces evapotranspiration (empirical factor)
    shade_factor = 1.0 - (shade_percent / 100.0) * 0.4  # 40% reduction in full shade

    adjusted_etp = evapotranspiration * shade_factor

    # Subtract expected precipitation
    precip = precipitation_forecast or 0.0
    net_need_mm = max(0.0, adjusted_etp - precip)

    # If water balance is very negative, increase need
    if water_balance is not None and water_balance < -10:
        net_need_mm *= 1.2  # 20% boost for dry soil

    # Convert mm to liters (1 mm over 1 m² = 1 liter)
    liters = net_need_mm * area_m2
    return round(max(0.0, liters), 1)
