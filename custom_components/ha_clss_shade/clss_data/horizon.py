"""Horizon profile — compute terrain obstruction from DEM elevation data.

Uses Open-Meteo elevation API (Copernicus 30m DEM, free, no API key)
to sample terrain elevation along radial lines from the observer point.
For each azimuth direction, computes the maximum horizon angle caused
by distant terrain (hills, mountains) beyond the LiDAR coverage radius.

This fixes the known limitation where the shadow engine (200m LiDAR radius)
cannot detect hills that block morning/evening sun.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_LOGGER = logging.getLogger(__name__)

OPENMETEO_ELEVATION_URL = "https://api.open-meteo.com/v1/elevation"

# Sampling parameters
DEFAULT_AZIMUTH_STEP = 5.0  # degrees (72 directions)
DEFAULT_MIN_DISTANCE_M = 300  # start beyond LiDAR radius
DEFAULT_MAX_DISTANCE_M = 5000  # 5 km radius
DEFAULT_DISTANCE_STEP_M = 250  # sample every 250m
MAX_POINTS_PER_REQUEST = 100  # Open-Meteo batch limit


@dataclass
class HorizonProfile:
    """Pre-computed horizon angles per azimuth direction.

    For each azimuth (0-360°, step=5°), stores the minimum sun elevation
    angle required to clear the terrain horizon.
    """

    azimuths: np.ndarray  # degrees [0, 5, 10, ..., 355]
    elevations: np.ndarray  # horizon elevation angle per azimuth (degrees)
    observer_elevation: float  # observer ground elevation (m ASL)
    max_distance_m: float  # sampling radius

    def min_elevation(self, azimuth: float) -> float:
        """Get minimum sun elevation to clear the horizon at given azimuth.

        Uses linear interpolation between sampled azimuths.
        """
        az = azimuth % 360.0
        step = self.azimuths[1] - self.azimuths[0] if len(self.azimuths) > 1 else 5.0
        idx_f = az / step
        idx_lo = int(idx_f) % len(self.azimuths)
        idx_hi = (idx_lo + 1) % len(self.azimuths)
        frac = idx_f - int(idx_f)
        return float(
            self.elevations[idx_lo] * (1 - frac)
            + self.elevations[idx_hi] * frac
        )

    def is_sun_visible(self, sun_azimuth: float, sun_elevation: float) -> bool:
        """Check if sun is above the terrain horizon."""
        return sun_elevation > self.min_elevation(sun_azimuth)

    def save(self, path: Path) -> None:
        """Save horizon profile to .npz file."""
        np.savez_compressed(
            path,
            azimuths=self.azimuths,
            elevations=self.elevations,
            observer_elevation=np.array(self.observer_elevation),
            max_distance_m=np.array(self.max_distance_m),
        )

    @classmethod
    def load(cls, path: Path) -> HorizonProfile:
        """Load horizon profile from .npz file."""
        data = np.load(path)
        return cls(
            azimuths=data["azimuths"],
            elevations=data["elevations"],
            observer_elevation=float(data["observer_elevation"]),
            max_distance_m=float(data["max_distance_m"]),
        )


def _destination_point(
    lat: float, lon: float, azimuth_deg: float, distance_m: float,
) -> tuple[float, float]:
    """Compute destination point given start, azimuth, and distance.

    Uses the Vincenty direct formula (spherical approximation).
    """
    R = 6371000.0  # Earth radius in meters
    lat_r = math.radians(lat)
    lon_r = math.radians(lon)
    az_r = math.radians(azimuth_deg)
    d_r = distance_m / R

    lat2 = math.asin(
        math.sin(lat_r) * math.cos(d_r)
        + math.cos(lat_r) * math.sin(d_r) * math.cos(az_r)
    )
    lon2 = lon_r + math.atan2(
        math.sin(az_r) * math.sin(d_r) * math.cos(lat_r),
        math.cos(d_r) - math.sin(lat_r) * math.sin(lat2),
    )

    return math.degrees(lat2), math.degrees(lon2)


async def _fetch_elevations_batch(
    session,
    lats: list[float],
    lons: list[float],
) -> list[float | None]:
    """Fetch elevations for a batch of points from Open-Meteo.

    Includes retry with backoff for HTTP 429 (rate limit) responses.
    """
    import asyncio

    import aiohttp

    results: list[float | None] = []

    # Split into chunks of MAX_POINTS_PER_REQUEST
    for start in range(0, len(lats), MAX_POINTS_PER_REQUEST):
        chunk_lats = lats[start : start + MAX_POINTS_PER_REQUEST]
        chunk_lons = lons[start : start + MAX_POINTS_PER_REQUEST]

        params = {
            "latitude": ",".join(f"{lat:.5f}" for lat in chunk_lats),
            "longitude": ",".join(f"{lon:.5f}" for lon in chunk_lons),
        }

        # Retry up to 3 times with backoff for rate limiting
        success = False
        for attempt in range(3):
            try:
                async with session.get(
                    OPENMETEO_ELEVATION_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 429:
                        wait = 2.0 * (attempt + 1)
                        _LOGGER.debug(
                            "Open-Meteo rate limited, waiting %.0fs (attempt %d)",
                            wait, attempt + 1,
                        )
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        _LOGGER.warning(
                            "Open-Meteo elevation fetch failed: HTTP %d", resp.status,
                        )
                        break
                    data = await resp.json()

                elevations = data.get("elevation", [])
                for elev in elevations:
                    results.append(float(elev) if elev is not None else None)

                # Pad if response shorter than request
                if len(elevations) < len(chunk_lats):
                    results.extend([None] * (len(chunk_lats) - len(elevations)))

                success = True
                break

            except Exception:
                _LOGGER.exception("Open-Meteo elevation batch fetch failed")
                break

        if not success:
            results.extend([None] * len(chunk_lats))

        # Small delay between batches to avoid rate limiting
        await asyncio.sleep(0.3)

    return results


async def compute_horizon_profile(
    session,
    lat: float,
    lon: float,
    azimuth_step: float = DEFAULT_AZIMUTH_STEP,
    min_distance_m: float = DEFAULT_MIN_DISTANCE_M,
    max_distance_m: float = DEFAULT_MAX_DISTANCE_M,
    distance_step_m: float = DEFAULT_DISTANCE_STEP_M,
) -> HorizonProfile:
    """Compute horizon profile using Open-Meteo elevation API.

    Samples elevation at points along radial lines from the center,
    computing the maximum horizon angle for each azimuth direction.

    Args:
        session: aiohttp ClientSession.
        lat: Observer latitude (WGS84).
        lon: Observer longitude (WGS84).
        azimuth_step: Angular resolution in degrees.
        min_distance_m: Start sampling distance (beyond LiDAR radius).
        max_distance_m: Maximum sampling distance.
        distance_step_m: Distance between samples along each radial.

    Returns:
        HorizonProfile with horizon elevation per azimuth.
    """
    azimuths = np.arange(0, 360, azimuth_step)
    distances = np.arange(min_distance_m, max_distance_m + 1, distance_step_m)
    n_az = len(azimuths)
    n_dist = len(distances)

    # Generate all sample points
    all_lats: list[float] = [lat]  # first point = observer
    all_lons: list[float] = [lon]

    for az in azimuths:
        for dist in distances:
            p_lat, p_lon = _destination_point(lat, lon, float(az), float(dist))
            all_lats.append(p_lat)
            all_lons.append(p_lon)

    _LOGGER.info(
        "Horizon profile: sampling %d points (%d azimuths × %d distances)",
        len(all_lats) - 1, n_az, n_dist,
    )

    # Fetch all elevations
    all_elevations = await _fetch_elevations_batch(session, all_lats, all_lons)

    observer_elev = all_elevations[0]
    if observer_elev is None:
        _LOGGER.warning("Could not get observer elevation, defaulting to 300m")
        observer_elev = 300.0

    # Compute max horizon angle per azimuth
    horizon_angles = np.zeros(n_az, dtype=np.float64)

    for i_az, az in enumerate(azimuths):
        max_angle = 0.0
        for i_dist, dist in enumerate(distances):
            idx = 1 + i_az * n_dist + i_dist
            target_elev = all_elevations[idx]
            if target_elev is None:
                continue

            # Horizon angle: elevation difference / horizontal distance
            elev_diff = target_elev - observer_elev
            if elev_diff > 0:
                angle = math.degrees(math.atan2(elev_diff, float(dist)))
                if angle > max_angle:
                    max_angle = angle

        horizon_angles[i_az] = max_angle

    # Log summary
    max_horizon = float(np.max(horizon_angles))
    mean_horizon = float(np.mean(horizon_angles))
    peak_az = float(azimuths[np.argmax(horizon_angles)])
    _LOGGER.info(
        "Horizon profile computed: max=%.1f° at az=%.0f°, mean=%.1f°",
        max_horizon, peak_az, mean_horizon,
    )

    return HorizonProfile(
        azimuths=azimuths.astype(np.float64),
        elevations=horizon_angles,
        observer_elevation=observer_elev,
        max_distance_m=max_distance_m,
    )
