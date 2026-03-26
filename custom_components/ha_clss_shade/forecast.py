"""PV production forecast — shadow + weather + POA → hourly power estimate."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone

from .shadow_engine import ShadowResult, SunPosition, compute_shadow_map, compute_sun_position
from .weather_bridge import compute_poa_factor

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clss_data.rasterizer import SiteModel
    from .zones import ZoneSet

_LOGGER = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ShadowForecastStep:
    """Shadow data for a single time step."""

    dt: datetime  # UTC
    sun_elevation: float
    sun_azimuth: float
    zone_sun_pct: dict[str, float]  # {zone_name: sun_percent}


@dataclass
class PvForecastHour:
    """Single time step in the PV forecast."""

    dt: datetime
    power_w: float  # final estimated power
    sun_elevation: float
    poa_factor: float
    cloud_coverage: float | None
    cloud_factor: float
    shadow_factor: float  # weighted sun% across PV zones


@dataclass
class PvForecastDay:
    """One day's PV forecast."""

    date: date
    total_kwh: float
    hourly: list[PvForecastHour]
    computed_at: datetime


@dataclass
class ForecastData:
    """Aggregate forecast — attached to ClssShadeData."""

    today: PvForecastDay | None = None
    tomorrow: PvForecastDay | None = None
    next_hour_w: float = 0.0
    performance_factor_ema: float = 1.0


# ---------------------------------------------------------------------------
# Shadow forecast (CPU-bound, runs in executor)
# ---------------------------------------------------------------------------


def compute_shadow_forecast(
    site: SiteModel,
    zones: ZoneSet,
    lat: float,
    lon: float,
    target_date: date,
    interval_minutes: int = 30,
) -> list[ShadowForecastStep]:
    """Compute per-zone sun percentages for each time step of a day.

    For each interval from 4:00 to 22:00 UTC, computes sun position and
    shadow map, then extracts per-zone sun percentages.

    Takes ~1.3s per step × 36 steps = ~47s total (runs in executor thread).
    """
    steps: list[ShadowForecastStep] = []

    for hour in range(4, 22):
        for minute in range(0, 60, interval_minutes):
            dt = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, minute, 0,
                tzinfo=timezone.utc,
            )
            sun = compute_sun_position(lat, lon, dt)

            if not sun.is_above_horizon:
                steps.append(ShadowForecastStep(
                    dt=dt,
                    sun_elevation=sun.elevation,
                    sun_azimuth=sun.azimuth,
                    zone_sun_pct={name: 0.0 for name in zones.names},
                ))
                continue

            result = compute_shadow_map(site, sun, target_date)

            zone_sun: dict[str, float] = {}
            for name in zones.names:
                zone = zones.get(name)
                if zone and zone.cell_count > 0:
                    zone_sun[name] = round(zone.sun_percent(result), 1)
                else:
                    zone_sun[name] = 0.0

            steps.append(ShadowForecastStep(
                dt=dt,
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                zone_sun_pct=zone_sun,
            ))

    _LOGGER.info(
        "Shadow forecast for %s: %d steps, %d daytime",
        target_date, len(steps),
        sum(1 for s in steps if s.sun_elevation > 0),
    )
    return steps


# ---------------------------------------------------------------------------
# Weather interpolation
# ---------------------------------------------------------------------------


def interpolate_weather(
    shadow_steps: list[ShadowForecastStep],
    weather_entries: list[dict],
) -> list[dict]:
    """Interpolate 3-hour weather forecast to match shadow forecast time steps.

    Args:
        shadow_steps: Shadow forecast steps with .dt attribute.
        weather_entries: Weather forecast entries with 'datetime', 'cloud_coverage',
            'temperature', 'precipitation' keys.

    Returns:
        List of dicts (one per shadow step) with interpolated cloud_coverage,
        temperature, and precipitation.
    """
    if not weather_entries:
        return [{"cloud_coverage": None, "temperature": None, "precipitation": None}
                for _ in shadow_steps]

    # Parse weather datetimes
    wx_times: list[datetime] = []
    for entry in weather_entries:
        dt_str = entry.get("datetime", "")
        if isinstance(dt_str, str):
            try:
                wx_times.append(datetime.fromisoformat(dt_str))
            except ValueError:
                continue
        elif isinstance(dt_str, datetime):
            wx_times.append(dt_str)

    if not wx_times:
        return [{"cloud_coverage": None, "temperature": None, "precipitation": None}
                for _ in shadow_steps]

    result = []
    for step in shadow_steps:
        t = step.dt
        interp = _interpolate_at(t, wx_times, weather_entries)
        result.append(interp)

    return result


def _interpolate_at(
    t: datetime,
    wx_times: list[datetime],
    weather_entries: list[dict],
) -> dict:
    """Linearly interpolate weather values at time t."""
    # Ensure t is timezone-aware
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)

    # Find bracketing entries
    before_idx = None
    after_idx = None

    for i, wt in enumerate(wx_times):
        wt_aware = wt if wt.tzinfo else wt.replace(tzinfo=timezone.utc)
        if wt_aware <= t:
            before_idx = i
        if wt_aware >= t and after_idx is None:
            after_idx = i

    # Edge cases: clamp to nearest
    if before_idx is None and after_idx is not None:
        return _extract_weather(weather_entries[after_idx])
    if after_idx is None and before_idx is not None:
        return _extract_weather(weather_entries[before_idx])
    if before_idx is None and after_idx is None:
        return {"cloud_coverage": None, "temperature": None, "precipitation": None}

    if before_idx == after_idx:
        return _extract_weather(weather_entries[before_idx])

    # Linear interpolation
    t0 = wx_times[before_idx]
    t1 = wx_times[after_idx]
    t0_aware = t0 if t0.tzinfo else t0.replace(tzinfo=timezone.utc)
    t1_aware = t1 if t1.tzinfo else t1.replace(tzinfo=timezone.utc)

    span = (t1_aware - t0_aware).total_seconds()
    if span <= 0:
        return _extract_weather(weather_entries[before_idx])

    frac = (t - t0_aware).total_seconds() / span

    e0 = weather_entries[before_idx]
    e1 = weather_entries[after_idx]

    def _lerp(key: str) -> float | None:
        v0 = e0.get(key)
        v1 = e1.get(key)
        if v0 is None or v1 is None:
            return v0 if v0 is not None else v1
        try:
            return float(v0) * (1 - frac) + float(v1) * frac
        except (ValueError, TypeError):
            return None

    return {
        "cloud_coverage": _lerp("cloud_coverage"),
        "temperature": _lerp("temperature"),
        "precipitation": _lerp("precipitation"),
    }


def _extract_weather(entry: dict) -> dict:
    """Extract weather values from a forecast entry."""
    return {
        "cloud_coverage": entry.get("cloud_coverage"),
        "temperature": entry.get("temperature"),
        "precipitation": entry.get("precipitation"),
    }


# ---------------------------------------------------------------------------
# PV forecast assembly
# ---------------------------------------------------------------------------


def assemble_pv_forecast(
    shadow_steps: list[ShadowForecastStep],
    weather_interpolated: list[dict],
    pv_zones_config: dict[str, int],
    panel_tilt: float,
    panel_azimuth: float,
    performance_factor: float = 1.0,
    interval_minutes: int = 30,
) -> PvForecastDay:
    """Combine shadow + weather into a PV production forecast.

    For each time step:
    1. POA factor from sun position + panel orientation
    2. Cloud factor from cloud_coverage (fallback path from estimate_pv_power)
    3. Per-zone: sun% × cloud_factor × POA × capacity
    4. Apply performance_factor calibration
    """
    if not shadow_steps:
        return PvForecastDay(
            date=date.today(),
            total_kwh=0.0,
            hourly=[],
            computed_at=datetime.now(tz=timezone.utc),
        )

    target_date = shadow_steps[0].dt.date()
    interval_hours = interval_minutes / 60.0
    system_losses = 0.08

    hourly: list[PvForecastHour] = []
    total_wh = 0.0

    for i, step in enumerate(shadow_steps):
        wx = weather_interpolated[i] if i < len(weather_interpolated) else {}

        # Skip nighttime
        if step.sun_elevation <= 0:
            hourly.append(PvForecastHour(
                dt=step.dt,
                power_w=0.0,
                sun_elevation=step.sun_elevation,
                poa_factor=0.0,
                cloud_coverage=wx.get("cloud_coverage"),
                cloud_factor=0.0,
                shadow_factor=0.0,
            ))
            continue

        # POA factor
        poa = compute_poa_factor(
            sun_elevation=step.sun_elevation,
            sun_azimuth=step.sun_azimuth,
            panel_tilt=panel_tilt,
            panel_azimuth=panel_azimuth,
        )

        # Cloud factor
        cloud_cov = wx.get("cloud_coverage")
        if cloud_cov is not None:
            cloud_factor = 1.0 - (cloud_cov / 100.0) * 0.75
        else:
            cloud_factor = 0.75  # assume partly cloudy if no data

        # Estimated radiation from cloud model (no measured GHI for forecast)
        estimated_radiation = 800.0 * cloud_factor * poa

        # Per-zone power calculation
        total_power = 0.0
        total_sun_pct = 0.0
        total_capacity = 0

        if not pv_zones_config:
            # Default: use "roof" zone with 5000 Wp
            sun_pct = step.zone_sun_pct.get("roof", 50.0)
            capacity = 5000
            sun_frac = sun_pct / 100.0
            effective = estimated_radiation * (sun_frac * 0.8 + 0.2)
            total_power = capacity * (effective / 1000.0) * (1 - system_losses)
            total_sun_pct = sun_pct
            total_capacity = capacity
        else:
            for zone_name, capacity_wp in pv_zones_config.items():
                cap = capacity_wp if capacity_wp > 0 else 5000
                sun_pct = step.zone_sun_pct.get(zone_name, 50.0)
                sun_frac = sun_pct / 100.0
                effective = estimated_radiation * (sun_frac * 0.8 + 0.2)
                power = cap * (effective / 1000.0) * (1 - system_losses)
                total_power += max(0.0, power)
                total_sun_pct += sun_pct * cap
                total_capacity += cap

        # Weighted average sun% across PV zones
        shadow_factor = total_sun_pct / total_capacity if total_capacity > 0 else 0.0

        # Apply performance factor calibration
        calibrated_power = max(0.0, total_power * performance_factor)

        hourly.append(PvForecastHour(
            dt=step.dt,
            power_w=round(calibrated_power, 1),
            sun_elevation=step.sun_elevation,
            poa_factor=round(poa, 3),
            cloud_coverage=cloud_cov,
            cloud_factor=round(cloud_factor, 3),
            shadow_factor=round(shadow_factor, 1),
        ))

        total_wh += calibrated_power * interval_hours

    total_kwh = round(total_wh / 1000.0, 2)

    _LOGGER.info(
        "PV forecast %s: %.1f kWh, %d steps, perf_factor=%.3f",
        target_date, total_kwh, len(hourly), performance_factor,
    )

    return PvForecastDay(
        date=target_date,
        total_kwh=total_kwh,
        hourly=hourly,
        computed_at=datetime.now(tz=timezone.utc),
    )


# ---------------------------------------------------------------------------
# Performance factor EMA
# ---------------------------------------------------------------------------


def update_performance_ema(
    current_ema: float,
    new_sample: float,
    alpha: float = 0.1,
) -> float:
    """Update exponential moving average of performance factor.

    Args:
        current_ema: Current EMA value.
        new_sample: New pv_real / pv_estimate ratio.
        alpha: Smoothing factor (0.1 = ~10 samples to converge).

    Returns:
        Updated EMA value.
    """
    # Clamp extreme values
    if new_sample <= 0 or new_sample > 3.0:
        return current_ema

    return alpha * new_sample + (1 - alpha) * current_ema
