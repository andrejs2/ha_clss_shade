"""DataUpdateCoordinator for CLSS Shade integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .clss_data.geo import wgs84_to_d96tm
from .clss_data.rasterizer import SiteModel, rasterize_laz
from .clss_data.slovenian_downloader import (
    ArsoLidarDownloader,
    DownloadError,
    TileNotFoundError,
)
from .const import (
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

_LOGGER = logging.getLogger(__name__)


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

        # Site model (loaded once, reused)
        self._site: SiteModel | None = None
        self._site_path = self._data_dir / "site_model.npz"

    @property
    def latitude(self) -> float:
        """Location latitude."""
        return self._lat

    @property
    def longitude(self) -> float:
        """Location longitude."""
        return self._lon

    async def async_setup(self) -> None:
        """Set up the site model — download LiDAR and rasterize.

        Called once during integration setup. This may take a while
        on first run (LAZ download ~30-50 MB).
        """
        # Try to load cached site model
        if self._site_path.exists():
            _LOGGER.info("Loading cached site model from %s", self._site_path)
            self._site = await self.hass.async_add_executor_job(
                SiteModel.load, self._site_path
            )
            return

        # Download and rasterize
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

            # Rasterize in executor (CPU-bound)
            self._site = await self.hass.async_add_executor_job(
                rasterize_laz,
                laz_paths,
                self._lat,
                self._lon,
                self._radius,
            )

            # Cache the site model
            await self.hass.async_add_executor_job(
                self._site.save, self._site_path
            )
            _LOGGER.info("Site model saved to %s", self._site_path)

        except (TileNotFoundError, DownloadError, ValueError) as err:
            _LOGGER.error("Failed to set up site model: %s", err)
            raise UpdateFailed(f"LiDAR data setup failed: {err}") from err

    async def _async_update_data(self) -> ClssShadeData:
        """Compute current shadow state."""
        now = datetime.now(tz=timezone.utc)

        # Compute sun position
        sun = compute_sun_position(self._lat, self._lon, now)

        # If no site model or sun is below horizon, return minimal data
        if self._site is None or not sun.is_above_horizon:
            return ClssShadeData(
                shadow=None,
                sun=sun,
                site=self._site,
                shade_percent=100.0 if not sun.is_above_horizon else 0.0,
                sun_percent=0.0 if not sun.is_above_horizon else 100.0,
                sun_elevation=sun.elevation,
                sun_azimuth=sun.azimuth,
                is_day=sun.is_above_horizon,
            )

        try:
            # Compute shadow map in executor (CPU-bound, ~1-2s)
            result = await self.hass.async_add_executor_job(
                compute_shadow_map,
                self._site,
                sun,
                now.date(),
            )

            import numpy as np

            mean_shade = float(np.mean(result.shadow_map) * 100)
            mean_sun = 100.0 - mean_shade

            return ClssShadeData(
                shadow=result,
                sun=sun,
                site=self._site,
                shade_percent=round(mean_shade, 1),
                sun_percent=round(mean_sun, 1),
                sun_elevation=round(sun.elevation, 1),
                sun_azimuth=round(sun.azimuth, 1),
                is_day=True,
            )

        except Exception as err:
            raise UpdateFailed(f"Shadow computation failed: {err}") from err
