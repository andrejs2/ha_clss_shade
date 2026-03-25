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


def estimate_pv_power(
    sun_percent: float,
    solar_radiation: float | None,
    cloud_coverage: float | None = None,
    panel_capacity_wp: float = 5000.0,
    tilt_factor: float = 1.2,
    system_losses: float = 0.08,
) -> float | None:
    """Estimate PV power output combining shade analysis with solar radiation.

    Args:
        sun_percent: Percentage of direct sunlight on the PV zone (0-100).
        solar_radiation: Measured global horizontal radiation in W/m² from ARSO.
        cloud_coverage: Cloud coverage percentage (0-100) from ARSO.
            Used as fallback when solar_radiation is unavailable.
        panel_capacity_wp: Installed PV capacity in Wp.
        tilt_factor: Correction for tilted panels vs horizontal sensor.
            Tilted panels (~30°) receive more radiation than horizontal.
            Default 1.2 (~20% gain, typical for Slovenia at ~46°N).
        system_losses: System losses (inverter, wiring, temperature) as fraction.
            Default 0.08 (8%) for systems with optimizers (SolarEdge, Enphase).
            Use 0.14 for string inverters without optimizers.

    Returns:
        Estimated power output in Watts, or None if no data.
    """
    if sun_percent <= 0:
        return 0.0

    sun_fraction = sun_percent / 100.0

    if solar_radiation is not None and solar_radiation > 0:
        # ARSO measures global horizontal irradiance (GHI).
        # Tilted panels receive more radiation — apply tilt correction.
        tilted_radiation = solar_radiation * tilt_factor

        # Shade adjustment: in shade, only diffuse component reaches panels (~20%)
        effective_radiation = tilted_radiation * (sun_fraction * 0.8 + 0.2)

        # Standard test conditions: 1000 W/m²
        power = panel_capacity_wp * (effective_radiation / 1000.0) * (1 - system_losses)
        return round(max(0.0, power), 1)

    # Fallback: estimate from cloud coverage (rough approximation)
    if cloud_coverage is not None:
        cloud_factor = 1.0 - (cloud_coverage / 100.0) * 0.75
        estimated_radiation = 800.0 * cloud_factor * tilt_factor
        effective_radiation = estimated_radiation * (sun_fraction * 0.8 + 0.2)
        power = panel_capacity_wp * (effective_radiation / 1000.0) * (1 - system_losses)
        return round(max(0.0, power), 1)

    return None


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
