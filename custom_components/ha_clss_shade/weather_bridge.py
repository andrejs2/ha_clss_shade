"""Bridge to slovenian_weather_integration — reads ARSO weather entities from HA."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

# Entity ID patterns from slovenian_weather_integration
# Weather sensors: sensor.arso_weather_{location}_{sensor_name}
# Agrometeo sensors: sensor.arso_agrometeo_{station}_{field}

ARSO_DOMAIN = "slovenian_weather_integration"


@dataclass
class ArsoWeatherData:
    """Current weather data from ARSO sensors."""

    solar_radiation: float | None = None  # W/m² (global)
    diffuse_radiation: float | None = None  # W/m²
    cloud_coverage: float | None = None  # %
    temperature: float | None = None  # °C
    humidity: float | None = None  # %
    evapotranspiration: float | None = None  # mm
    water_balance: float | None = None  # mm
    precipitation_forecast: float | None = None  # mm


def find_arso_entities(hass: HomeAssistant) -> dict[str, str]:
    """Find available ARSO weather entities in HA.

    Searches for slovenian_weather_integration entities and returns
    a mapping of data type to entity_id.
    """
    found: dict[str, str] = {}
    states = hass.states.async_all("sensor")

    # Patterns to search for (Slovenian sensor names)
    patterns = {
        "solar_radiation": "globalno_soncno_sevanje",
        "diffuse_radiation": "difuzno_soncno_sevanje",
        "cloud_coverage": "oblacnost",
        "temperature": "temperatura",
        "humidity": "relativna_vlaznost",
        "evapotranspiration": "evapotranspiracija",
        "water_balance": "vodna_bilanca",
    }

    for state in states:
        eid = state.entity_id
        if "arso" not in eid:
            continue

        for key, pattern in patterns.items():
            if pattern in eid and key not in found:
                found[key] = eid
                _LOGGER.debug("Found ARSO entity: %s -> %s", key, eid)

    if found:
        _LOGGER.info("Found %d ARSO weather entities", len(found))
    else:
        _LOGGER.info("No ARSO weather entities found — weather bridge disabled")

    return found


def read_arso_weather(
    hass: HomeAssistant,
    entity_map: dict[str, str],
) -> ArsoWeatherData:
    """Read current values from ARSO weather entities.

    Args:
        hass: Home Assistant instance.
        entity_map: Mapping from data type to entity_id
            (from find_arso_entities).

    Returns:
        ArsoWeatherData with available values.
    """
    data = ArsoWeatherData()

    for key, entity_id in entity_map.items():
        state = hass.states.get(entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            continue

        try:
            value = float(state.state)
            setattr(data, key, value)
        except (ValueError, TypeError):
            _LOGGER.debug("Could not parse %s state: %s", entity_id, state.state)

    return data


def estimate_pv_power(
    sun_percent: float,
    solar_radiation: float | None,
    panel_capacity_wp: float = 5000.0,
    panel_efficiency: float = 0.18,
    system_losses: float = 0.14,
) -> float | None:
    """Estimate PV power output combining shade analysis with solar radiation.

    Args:
        sun_percent: Percentage of direct sunlight on the roof zone (0-100).
        solar_radiation: Measured global solar radiation in W/m².
            If None, uses a theoretical clear-sky estimate.
        panel_capacity_wp: Installed PV capacity in Wp.
        panel_efficiency: Panel efficiency factor (0.0-1.0).
        system_losses: System losses (inverter, wiring, etc.) as fraction.

    Returns:
        Estimated power output in Watts, or None if no data.
    """
    if sun_percent <= 0:
        return 0.0

    sun_fraction = sun_percent / 100.0

    if solar_radiation is not None and solar_radiation > 0:
        # Direct estimate from measured radiation
        # Adjust radiation by shade fraction (diffuse light still arrives in shade)
        effective_radiation = solar_radiation * (sun_fraction * 0.85 + 0.15)
        # Standard test conditions: 1000 W/m²
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
