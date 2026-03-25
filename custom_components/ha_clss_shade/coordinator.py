"""DataUpdateCoordinator for CLSS Shade integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
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
    CONF_RADIUS,
    DATA_DIR_NAME,
    DEFAULT_RADIUS_M,
    DEFAULT_UPDATE_INTERVAL_MIN,
    DOMAIN,
)
from .shadow_engine import (
    ShadowResult,
    SunPosition,
    compute_shadow_map,
    compute_sun_position,
)
from .weather_bridge import (
    ArsoWeatherData,
    estimate_irrigation_need,
    estimate_pv_power,
    find_arso_entities,
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
    irrigation_need: float | None = None


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

        # Data directory for this entry
        self._data_dir = Path(hass.config.path(DATA_DIR_NAME, entry.entry_id))
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # Site model and zones (loaded once, reused)
        self._site: SiteModel | None = None
        self._zones: ZoneSet | None = None
        self._site_path = self._data_dir / "site_model.npz"

        # ARSO weather entity mapping (discovered once)
        self._arso_entities: dict[str, str] | None = None

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

    async def _async_update_data(self) -> ClssShadeData:
        """Compute current shadow state."""
        now = datetime.now(tz=timezone.utc)
        sun = compute_sun_position(self._lat, self._lon, now)

        # Night time — return minimal data
        if self._site is None or not sun.is_above_horizon:
            return ClssShadeData(
                shadow=None,
                sun=sun,
                site=self._site,
                shade_percent=100.0 if not sun.is_above_horizon else 0.0,
                sun_percent=0.0 if not sun.is_above_horizon else 100.0,
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                is_day=sun.is_above_horizon,
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

            # Read ARSO weather data
            weather = None
            pv_estimate = None
            irrigation = None

            if self._arso_entities:
                weather = read_arso_weather(self.hass, self._arso_entities)

                # PV estimate using roof zone shade
                roof_sun = zone_data["roof"].sun_percent if "roof" in zone_data else mean_sun
                pv_estimate = estimate_pv_power(
                    sun_percent=roof_sun,
                    solar_radiation=weather.solar_radiation,
                    cloud_coverage=weather.cloud_coverage,
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
                irrigation_need=irrigation,
            )

        except Exception as err:
            raise UpdateFailed(f"Shadow computation failed: {err}") from err
