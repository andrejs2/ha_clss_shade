"""DataUpdateCoordinator for CLSS Shade integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clss_data.rasterizer import SiteModel, rasterize_laz
from .clss_data.slovenian_downloader import (
    ArsoLidarDownloader,
    DownloadError,
    TileNotFoundError,
)
from .const import (
    CONF_CUSTOM_ZONES,
    CONF_INCLUDE_NEIGHBORS,
    CONF_PV_PANEL_AZIMUTH,
    CONF_PV_PANEL_TILT,
    CONF_PV_REAL_ENTITY,
    CONF_PV_ZONES_CONFIG,
    CONF_RADIUS,
    DEFAULT_PV_PANEL_AZIMUTH,
    DEFAULT_PV_PANEL_TILT,
    DATA_DIR_NAME,
    DEFAULT_FORECAST_INTERVAL_MIN,
    DEFAULT_FORECAST_WEATHER_INTERVAL_MIN,
    DEFAULT_RADIUS_M,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
    FORECAST_DAYS,
    FORECAST_FAR_CACHE_HOURS,
    FORECAST_STEP_MINUTES,
    FORECAST_STEP_MINUTES_FAR,
    INCA_REFRESH_INTERVAL_MIN,
)
from .inca_client import fetch_inca_solar_radiation
from .forecast import (
    ForecastData,
    ShadowForecastStep,
    assemble_pv_forecast,
    compute_shadow_forecast,
    compute_time_windows,
    interpolate_weather,
    update_performance_ema,
)
from .shadow_engine import (
    ShadowResult,
    SunPosition,
    compute_shadow_map,
    compute_sun_position,
)
from .weather_bridge import (
    ArsoWeatherData,
    compute_poa_factor,
    estimate_irrigation_need,
    estimate_pv_power,
    fetch_weather_forecast,
    find_arso_entities,
    find_weather_entity,
    read_arso_weather,
)
from .zones import ZoneSet, auto_detect_zones, create_circular_zone, create_polygon_zone

_LOGGER = logging.getLogger(__name__)


@dataclass
class ZoneData:
    """Per-zone shade data."""

    shade_percent: float
    sun_percent: float
    area_m2: float
    cell_count: int


@dataclass
class ClssShadeData:
    """Data returned by the coordinator."""

    shadow: ShadowResult | None
    sun: SunPosition
    site: SiteModel | None
    shade_percent: float
    sun_percent: float
    sun_elevation: float
    sun_azimuth: float
    is_day: bool
    cloud_coverage: float | None = None
    zones: dict[str, ZoneData] = field(default_factory=dict)
    weather: ArsoWeatherData | None = None
    pv_power_estimate: float | None = None
    pv_power_real: float | None = None
    pv_performance_factor: float | None = None
    irrigation_need: float | None = None
    # Forecast fields
    pv_forecast_today_kwh: float | None = None
    pv_forecast_tomorrow_kwh: float | None = None
    pv_forecast_next_hour_w: float | None = None
    pv_forecast_5day_kwh: float | None = None
    pv_forecast_next_1h_wh: float | None = None
    pv_forecast_next_3h_wh: float | None = None
    pv_forecast_rest_of_today_kwh: float | None = None
    forecast: ForecastData | None = None


class ClssShadeCoordinator(DataUpdateCoordinator[ClssShadeData]):
    """Coordinator that computes shadow maps at regular intervals."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=DEFAULT_UPDATE_INTERVAL_MIN),
        )
        self.config_entry = entry
        self._lat: float = entry.data[CONF_LATITUDE]
        self._lon: float = entry.data[CONF_LONGITUDE]
        self._radius: float = entry.options.get(CONF_RADIUS, DEFAULT_RADIUS_M)
        self._include_neighbors: bool = entry.options.get(CONF_INCLUDE_NEIGHBORS, False)
        self._pv_zones_config = self._parse_pv_config(
            entry.options.get(CONF_PV_ZONES_CONFIG, "")
        )
        self._pv_panel_tilt: float = entry.options.get(CONF_PV_PANEL_TILT, DEFAULT_PV_PANEL_TILT)
        self._pv_panel_azimuth: float = entry.options.get(CONF_PV_PANEL_AZIMUTH, DEFAULT_PV_PANEL_AZIMUTH)
        self._pv_real_entity: str = entry.options.get(CONF_PV_REAL_ENTITY, "")

        # Data directory for this entry
        self._data_dir = Path(hass.config.path(DATA_DIR_NAME, entry.entry_id))
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Site model and zones (loaded once, reused)
        self._site: SiteModel | None = None
        self._zones: ZoneSet | None = None
        self._site_path = self._data_dir / "site_model.npz"

        # ARSO weather entity mapping (discovered once)
        self._arso_entities: dict[str, str] | None = None

        # Forecast state
        self._shadow_forecast_cache: dict[str, list[ShadowForecastStep]] = {}
        self._shadow_forecast_computed_at: datetime | None = None
        self._shadow_forecast_day_computed: dict[str, datetime] = {}
        self._weather_forecast_cache: list[dict] = []
        self._weather_forecast_fetched_at: datetime | None = None
        self._forecast_data: ForecastData | None = None
        self._performance_factor_ema: float = 1.0
        self._shadow_forecast_task: asyncio.Task | None = None
        self._weather_entity_id: str = ""

        # INCA nowcasting state
        self._inca_ghi: float | None = None
        self._inca_timestamp: str | None = None
        self._inca_fetched_at: datetime | None = None

    @property
    def latitude(self) -> float:
        return self._lat

    @property
    def longitude(self) -> float:
        return self._lon

    @property
    def zone_names(self) -> list[str]:
        """List of detected zone names."""
        if self._zones is None:
            return []
        return self._zones.names

    def zone_type(self, name: str) -> str:
        """Get zone type by name."""
        if self._zones is None:
            return "custom"
        zone = self._zones.get(name)
        return zone.zone_type if zone else "custom"

    async def async_setup(self) -> None:
        """Set up the site model — download LiDAR and rasterize."""
        # Try to load cached site model
        if self._site_path.exists():
            _LOGGER.info("Loading cached site model from %s", self._site_path)
            self._site = await self.hass.async_add_executor_job(
                SiteModel.load, self._site_path
            )
        else:
            _LOGGER.info(
                "First run: downloading LiDAR data for (%.4f, %.4f) r=%dm",
                self._lat, self._lon, self._radius,
            )
            try:
                downloader = ArsoLidarDownloader(
                    cache_dir=self._data_dir / "laz",
                )
                try:
                    laz_paths = await downloader.download_location(
                        self._lat,
                        self._lon,
                        include_neighbors=self._include_neighbors,
                    )
                finally:
                    await downloader.close()

                self._site = await self.hass.async_add_executor_job(
                    rasterize_laz,
                    laz_paths,
                    self._lat,
                    self._lon,
                    self._radius,
                )

                await self.hass.async_add_executor_job(
                    self._site.save, self._site_path
                )
                _LOGGER.info("Site model saved to %s", self._site_path)

            except (TileNotFoundError, DownloadError, ValueError) as err:
                _LOGGER.error("Failed to set up site model: %s", err)
                raise UpdateFailed(f"LiDAR data setup failed: {err}") from err

        # Auto-detect zones from classification
        if self._site is not None:
            self._zones = await self.hass.async_add_executor_job(
                auto_detect_zones, self._site
            )
            _LOGGER.info("Auto-detected zones: %s", self._zones.names)

            # Load custom zones from options
            custom_zone_configs = self.config_entry.options.get(CONF_CUSTOM_ZONES, [])
            for zconf in custom_zone_configs:
                try:
                    zone = await self.hass.async_add_executor_job(
                        self._create_custom_zone, zconf
                    )
                    self._zones.add(zone)
                    _LOGGER.info(
                        "Loaded custom zone '%s' (%s): %d cells",
                        zone.name,
                        zone.zone_type,
                        zone.cell_count,
                    )
                except Exception:
                    _LOGGER.exception(
                        "Failed to create custom zone '%s'", zconf.get("name", "?")
                    )

            _LOGGER.info("All zones: %s", self._zones.names)

        # Discover ARSO weather entities
        self._arso_entities = find_arso_entities(self.hass)

        # Discover ARSO weather entity for forecasts
        self._weather_entity_id = find_weather_entity(self.hass)

    def _calc_pv_estimate(
        self,
        zone_data: dict[str, ZoneData],
        mean_sun: float,
        weather: ArsoWeatherData,
        sun: SunPosition | None = None,
    ) -> float | None:
        """Calculate total PV estimate from per-zone capacities."""
        pv_config = self._pv_zones_config

        # Compute dynamic POA factor from current sun position + panel orientation
        poa = compute_poa_factor(
            sun_elevation=sun.elevation if sun else 45.0,
            sun_azimuth=sun.azimuth if sun else 180.0,
            panel_tilt=self._pv_panel_tilt,
            panel_azimuth=self._pv_panel_azimuth,
        )

        if not pv_config:
            roof_sun = zone_data["roof"].sun_percent if "roof" in zone_data else mean_sun
            return estimate_pv_power(
                sun_percent=roof_sun,
                solar_radiation=weather.solar_radiation,
                cloud_coverage=weather.cloud_coverage,
                panel_capacity_wp=5000.0,
                poa_factor=poa,
                inca_solar_radiation=weather.inca_solar_radiation,
            )

        total_power = 0.0
        any_result = False

        for zone_name, capacity_wp in pv_config.items():
            sun_pct = zone_data[zone_name].sun_percent if zone_name in zone_data else mean_sun
            cap = capacity_wp if capacity_wp > 0 else 5000
            result = estimate_pv_power(
                sun_percent=sun_pct,
                solar_radiation=weather.solar_radiation,
                cloud_coverage=weather.cloud_coverage,
                panel_capacity_wp=cap,
                poa_factor=poa,
                inca_solar_radiation=weather.inca_solar_radiation,
            )
            if result is not None:
                total_power += result
                any_result = True

        return round(total_power, 1) if any_result else None

    @staticmethod
    def _parse_pv_config(config_str: str) -> dict[str, int]:
        """Parse PV zones config string into {zone_name: capacity_wp}.

        Format: "pv_visja:5000, pv_nizja:6000"
        Fallback for old format: "roof" or "pv_visja,pv_nizja" (uses 0 = auto)
        """
        result = {}
        if not config_str or not config_str.strip():
            return result

        for part in config_str.split(","):
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                name, cap_str = part.split(":", 1)
                name = name.strip()
                try:
                    cap = int(cap_str.strip())
                except ValueError:
                    cap = 0
                result[name] = cap
            else:
                # Old format: just zone name, no capacity
                result[part.strip()] = 0
        return result

    def _create_custom_zone(self, zconf: dict):
        """Create a custom zone from config dict (runs in executor)."""
        shape = zconf.get("shape", "circle")
        if shape == "polygon":
            vertices = [tuple(v) for v in zconf["vertices"]]
            # Detect coordinate type: if values look like lat/lng (>10) vs meter offsets
            # Vertices from the map panel are [lat, lng], from config flow are [east, north]
            coords_type = "offset"
            if vertices and abs(vertices[0][0]) > 10:
                coords_type = "latlng"
            return create_polygon_zone(
                self._site,
                name=zconf["name"],
                vertices=vertices,
                zone_type=zconf.get("zone_type", "custom"),
                coords_type=coords_type,
            )
        # Circle
        return create_circular_zone(
            self._site,
            name=zconf["name"],
            offset_e=zconf.get("offset_e", 0.0),
            offset_n=zconf.get("offset_n", 0.0),
            radius_m=zconf.get("radius", 10.0),
            zone_type=zconf.get("zone_type", "custom"),
        )

    # ------------------------------------------------------------------
    # Forecast helpers
    # ------------------------------------------------------------------

    async def _async_refresh_shadow_forecast(self) -> None:
        """Recompute shadow forecast for N days in background executor.

        Days 0-1 use 30-min steps, days 2+ use 60-min steps.
        Far days (2+) reuse cached data if less than FORECAST_FAR_CACHE_HOURS old.
        Total ~2.7 min for 5 days, runs in executor thread every ~1 hour.
        """
        if self._site is None or self._zones is None:
            return

        now = datetime.now(tz=timezone.utc)
        today = now.date()

        site = self._site
        zones = self._zones
        lat, lon = self._lat, self._lon
        existing_cache = dict(self._shadow_forecast_cache)
        existing_timestamps = dict(self._shadow_forecast_day_computed)

        def _compute() -> dict[str, list[ShadowForecastStep]]:
            result: dict[str, list[ShadowForecastStep]] = {}
            for day_offset in range(FORECAST_DAYS):
                target = today + timedelta(days=day_offset)
                key = target.isoformat()
                step = FORECAST_STEP_MINUTES if day_offset < 2 else FORECAST_STEP_MINUTES_FAR

                # Reuse cached far-day data if recent enough
                if day_offset >= 2 and key in existing_cache:
                    cached_at = existing_timestamps.get(key)
                    if cached_at and (now - cached_at).total_seconds() < FORECAST_FAR_CACHE_HOURS * 3600:
                        result[key] = existing_cache[key]
                        continue

                result[key] = compute_shadow_forecast(site, zones, lat, lon, target, step)
            return result

        try:
            result = await self.hass.async_add_executor_job(_compute)

            # Clean up old days from cache
            valid_keys = {(today + timedelta(days=i)).isoformat() for i in range(FORECAST_DAYS)}
            self._shadow_forecast_cache = {k: v for k, v in result.items() if k in valid_keys}
            self._shadow_forecast_computed_at = datetime.now(tz=timezone.utc)

            # Track per-day computation timestamps
            for key in result:
                if key not in existing_timestamps or key not in existing_cache:
                    self._shadow_forecast_day_computed[key] = now
            # Clean old timestamps
            self._shadow_forecast_day_computed = {
                k: v for k, v in self._shadow_forecast_day_computed.items() if k in valid_keys
            }

            step_counts = [len(result.get((today + timedelta(days=i)).isoformat(), [])) for i in range(FORECAST_DAYS)]
            _LOGGER.info("Shadow forecast computed: %s time steps", "+".join(str(n) for n in step_counts))
        except Exception:
            _LOGGER.exception("Shadow forecast computation failed")

    async def _async_refresh_weather_forecast(self) -> None:
        """Fetch hourly weather forecast from HA weather entity."""
        # Lazy discovery: retry if weather entity wasn't found at setup
        # (handles race condition when slovenian_weather_integration loads after us)
        if not self._weather_entity_id:
            self._weather_entity_id = find_weather_entity(self.hass)
            if not self._weather_entity_id:
                return

        try:
            result = await fetch_weather_forecast(self.hass, self._weather_entity_id)
            self._weather_forecast_cache = result
            self._weather_forecast_fetched_at = datetime.now(tz=timezone.utc)
            _LOGGER.debug("Weather forecast fetched: %d entries", len(result))
        except Exception:
            _LOGGER.exception("Weather forecast fetch failed")

    def _assemble_forecast(self, now: datetime) -> ForecastData | None:
        """Assemble PV forecast from cached shadow and weather data."""
        if not self._shadow_forecast_cache:
            return None

        today = now.date()
        days: list = []

        for day_offset in range(FORECAST_DAYS):
            target_date = today + timedelta(days=day_offset)
            shadow_steps = self._shadow_forecast_cache.get(target_date.isoformat())
            if not shadow_steps:
                continue

            interval = FORECAST_STEP_MINUTES if day_offset < 2 else FORECAST_STEP_MINUTES_FAR
            weather_aligned = interpolate_weather(shadow_steps, self._weather_forecast_cache)

            result = assemble_pv_forecast(
                shadow_steps=shadow_steps,
                weather_interpolated=weather_aligned,
                pv_zones_config=self._pv_zones_config,
                panel_tilt=self._pv_panel_tilt,
                panel_azimuth=self._pv_panel_azimuth,
                performance_factor=self._performance_factor_ema,
                interval_minutes=interval,
            )
            days.append(result)

        if not days:
            return None

        # Find next-hour power
        next_hour_w = 0.0
        today_forecast = days[0] if days else None
        if today_forecast:
            next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
            for pt in today_forecast.hourly:
                if abs((pt.dt - next_hour).total_seconds()) < FORECAST_STEP_MINUTES * 60:
                    next_hour_w = pt.power_w
                    break

        # Time windows
        next_1h, next_3h, rest_today = compute_time_windows(
            today_forecast, now, FORECAST_STEP_MINUTES,
        )

        return ForecastData(
            days=days,
            next_hour_w=next_hour_w,
            next_1h_wh=next_1h,
            next_3h_wh=next_3h,
            rest_of_today_kwh=rest_today,
            performance_factor_ema=self._performance_factor_ema,
        )

    async def _async_update_data(self) -> ClssShadeData:
        """Compute current shadow state."""
        now = datetime.now(tz=timezone.utc)
        sun = compute_sun_position(self._lat, self._lon, now)

        # Site model not loaded yet
        if self._site is None:
            return ClssShadeData(
                shadow=None,
                sun=sun,
                site=None,
                shade_percent=0.0,
                sun_percent=100.0,
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                is_day=sun.is_above_horizon,
            )

        # Night time — no shadow computation, but return sensible values
        if not sun.is_above_horizon:
            # Zone data: all zones 100% shade at night
            zone_data: dict[str, ZoneData] = {}
            if self._zones:
                res2 = self._site.resolution ** 2
                for name in self._zones.names:
                    zone = self._zones.get(name)
                    if zone and zone.cell_count > 0:
                        zone_data[name] = ZoneData(
                            shade_percent=100.0,
                            sun_percent=0.0,
                            area_m2=round(zone.cell_count * res2, 1),
                            cell_count=zone.cell_count,
                        )

            # Still read weather data (useful for cloud coverage, irrigation)
            weather = None
            irrigation = None
            if not self._arso_entities:
                self._arso_entities = find_arso_entities(self.hass)
            if self._arso_entities:
                weather = read_arso_weather(self.hass, self._arso_entities)
                if weather and "garden" in zone_data:
                    garden = zone_data["garden"]
                    irrigation = estimate_irrigation_need(
                        shade_percent=garden.shade_percent,
                        evapotranspiration=weather.evapotranspiration,
                        water_balance=weather.water_balance,
                        precipitation_forecast=weather.precipitation_forecast,
                        area_m2=garden.area_m2,
                    )

            # Forecast refresh at night too (tomorrow's forecast is useful)
            shadow_stale = (
                self._shadow_forecast_computed_at is None
                or (now - self._shadow_forecast_computed_at)
                > timedelta(minutes=DEFAULT_FORECAST_INTERVAL_MIN)
            )
            if shadow_stale and self._shadow_forecast_task is None:
                self._shadow_forecast_task = self.hass.async_create_task(
                    self._async_refresh_shadow_forecast(),
                    f"{DOMAIN}_shadow_forecast",
                )
                self._shadow_forecast_task.add_done_callback(
                    lambda _: setattr(self, "_shadow_forecast_task", None)
                )

            weather_stale = (
                self._weather_forecast_fetched_at is None
                or (now - self._weather_forecast_fetched_at)
                > timedelta(minutes=DEFAULT_FORECAST_WEATHER_INTERVAL_MIN)
            )
            if weather_stale:
                await self._async_refresh_weather_forecast()

            forecast = self._assemble_forecast(now)

            return ClssShadeData(
                shadow=None,
                sun=sun,
                site=self._site,
                shade_percent=100.0,
                sun_percent=0.0,
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                is_day=False,
                cloud_coverage=weather.cloud_coverage if weather else None,
                zones=zone_data,
                weather=weather,
                pv_power_estimate=0.0,
                pv_power_real=0.0,
                irrigation_need=irrigation,
                pv_forecast_today_kwh=round(forecast.today.total_kwh, 2) if forecast and forecast.today else None,
                pv_forecast_tomorrow_kwh=round(forecast.tomorrow.total_kwh, 2) if forecast and forecast.tomorrow else None,
                pv_forecast_next_hour_w=0.0,
                pv_forecast_5day_kwh=round(sum(d.total_kwh for d in forecast.days), 2) if forecast and forecast.days else None,
                pv_forecast_next_1h_wh=0.0,
                pv_forecast_next_3h_wh=0.0,
                pv_forecast_rest_of_today_kwh=0.0,
                forecast=forecast,
            )

        try:
            # Shadow computation (CPU-bound, ~1-2s)
            result = await self.hass.async_add_executor_job(
                compute_shadow_map, self._site, sun, now.date(),
            )

            mean_shade = float(np.mean(result.shadow_map) * 100)
            mean_sun = 100.0 - mean_shade

            # Per-zone data
            zone_data: dict[str, ZoneData] = {}
            if self._zones:
                res2 = self._site.resolution ** 2
                for name in self._zones.names:
                    zone = self._zones.get(name)
                    if zone and zone.cell_count > 0:
                        zone_data[name] = ZoneData(
                            shade_percent=round(zone.shade_percent(result), 1),
                            sun_percent=round(zone.sun_percent(result), 1),
                            area_m2=round(zone.cell_count * res2, 1),
                            cell_count=zone.cell_count,
                        )

            # Refresh INCA solar radiation (every 10 min)
            inca_stale = (
                self._inca_fetched_at is None
                or (now - self._inca_fetched_at)
                > timedelta(minutes=INCA_REFRESH_INTERVAL_MIN)
            )
            if inca_stale:
                session = async_get_clientsession(self.hass)
                ghi, ts = await fetch_inca_solar_radiation(
                    session, self._lat, self._lon
                )
                if ghi is not None:
                    self._inca_ghi = ghi
                    self._inca_timestamp = ts
                self._inca_fetched_at = now

            # Read ARSO weather data
            weather = None
            pv_estimate = None
            irrigation = None

            if not self._arso_entities:
                self._arso_entities = find_arso_entities(self.hass)
            if self._arso_entities:
                weather = read_arso_weather(self.hass, self._arso_entities)

                # Inject INCA GHI into weather data
                if self._inca_ghi is not None:
                    weather.inca_solar_radiation = self._inca_ghi

                # PV estimate — per-zone capacity with POA
                pv_estimate = self._calc_pv_estimate(
                    zone_data, mean_sun, weather, sun
                )

                # Irrigation estimate using garden zone shade
                if "garden" in zone_data:
                    garden = zone_data["garden"]
                    irrigation = estimate_irrigation_need(
                        shade_percent=garden.shade_percent,
                        evapotranspiration=weather.evapotranspiration,
                        water_balance=weather.water_balance,
                        precipitation_forecast=weather.precipitation_forecast,
                        area_m2=garden.area_m2,
                    )

            # Read real PV power and calculate performance factor
            pv_real = None
            pv_perf = None
            if self._pv_real_entity:
                state = self.hass.states.get(self._pv_real_entity)
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        pv_real = round(float(state.state), 1)
                    except (ValueError, TypeError):
                        pass
                if pv_real is not None and pv_estimate and pv_estimate > 50:
                    pv_perf = round(pv_real / pv_estimate, 3)

            # --- Forecast refresh ---
            shadow_stale = (
                self._shadow_forecast_computed_at is None
                or (now - self._shadow_forecast_computed_at)
                > timedelta(minutes=DEFAULT_FORECAST_INTERVAL_MIN)
            )
            if shadow_stale and self._shadow_forecast_task is None:
                self._shadow_forecast_task = self.hass.async_create_task(
                    self._async_refresh_shadow_forecast(),
                    f"{DOMAIN}_shadow_forecast",
                )
                self._shadow_forecast_task.add_done_callback(
                    lambda _: setattr(self, "_shadow_forecast_task", None)
                )

            weather_stale = (
                self._weather_forecast_fetched_at is None
                or (now - self._weather_forecast_fetched_at)
                > timedelta(minutes=DEFAULT_FORECAST_WEATHER_INTERVAL_MIN)
            )
            if weather_stale:
                await self._async_refresh_weather_forecast()

            # Update performance factor EMA (only with reliable daytime data)
            if pv_perf is not None and sun.elevation > 10.0:
                self._performance_factor_ema = update_performance_ema(
                    self._performance_factor_ema, pv_perf
                )

            # Assemble forecast from cached data
            forecast = self._assemble_forecast(now)

            return ClssShadeData(
                shadow=result,
                sun=sun,
                site=self._site,
                shade_percent=round(mean_shade, 1),
                sun_percent=round(mean_sun, 1),
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                is_day=True,
                cloud_coverage=weather.cloud_coverage if weather else None,
                zones=zone_data,
                weather=weather,
                pv_power_estimate=pv_estimate,
                pv_power_real=pv_real,
                pv_performance_factor=pv_perf,
                irrigation_need=irrigation,
                pv_forecast_today_kwh=round(forecast.today.total_kwh, 2) if forecast and forecast.today else None,
                pv_forecast_tomorrow_kwh=round(forecast.tomorrow.total_kwh, 2) if forecast and forecast.tomorrow else None,
                pv_forecast_next_hour_w=round(forecast.next_hour_w, 1) if forecast else None,
                pv_forecast_5day_kwh=round(sum(d.total_kwh for d in forecast.days), 2) if forecast and forecast.days else None,
                pv_forecast_next_1h_wh=round(forecast.next_1h_wh, 0) if forecast else None,
                pv_forecast_next_3h_wh=round(forecast.next_3h_wh, 0) if forecast else None,
                pv_forecast_rest_of_today_kwh=round(forecast.rest_of_today_kwh, 2) if forecast else None,
                forecast=forecast,
            )

        except Exception as err:
            raise UpdateFailed(f"Shadow computation failed: {err}") from err
