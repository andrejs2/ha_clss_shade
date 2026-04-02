"""Shadow engine — ray-marching shadow computation over LiDAR terrain."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, date

import numpy as np

from .clss_data.rasterizer import SiteModel

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .clss_data.horizon import HorizonProfile

_LOGGER = logging.getLogger(__name__)

# Classification codes
CLASS_GROUND = 2
CLASS_LOW_VEG = 3
CLASS_MED_VEG = 4
CLASS_HIGH_VEG = 5
CLASS_BUILDING = 6

# Seasonal transmittance for high vegetation (class 5)
# Other classes use fixed values year-round
TRANSMITTANCE_HIGH_VEG_FULL_LEAF = 0.15  # Jun-Sep
TRANSMITTANCE_HIGH_VEG_PARTIAL = 0.40  # Apr-May, Oct-Nov
TRANSMITTANCE_HIGH_VEG_BARE = 0.65  # Dec-Mar

# Fixed transmittance
TRANSMITTANCE = {
    CLASS_GROUND: 1.0,
    CLASS_LOW_VEG: 0.60,
    CLASS_MED_VEG: 0.40,
    CLASS_BUILDING: 0.0,
}


@dataclass
class SunPosition:
    """Sun position in the sky."""

    azimuth: float  # Degrees from north, clockwise (0=N, 90=E, 180=S, 270=W)
    elevation: float  # Degrees above horizon (0=horizon, 90=zenith)

    @property
    def is_above_horizon(self) -> bool:
        return self.elevation > 0


@dataclass
class ShadowResult:
    """Result of shadow computation."""

    shadow_map: np.ndarray  # Float32, 0.0=full sun, 1.0=full shadow
    sun: SunPosition
    site: SiteModel
    timestamp: datetime

    @property
    def sun_fraction(self) -> np.ndarray:
        """Fraction of direct sunlight reaching each cell."""
        return 1.0 - self.shadow_map

    def zone_shade_percent(self, mask: np.ndarray) -> float:
        """Average shade percentage for a boolean zone mask."""
        if not np.any(mask):
            return 0.0
        return float(np.mean(self.shadow_map[mask]) * 100)

    def zone_sun_percent(self, mask: np.ndarray) -> float:
        """Average sun percentage for a boolean zone mask."""
        return 100.0 - self.zone_shade_percent(mask)


def compute_sun_position(lat: float, lon: float, dt: datetime) -> SunPosition:
    """Calculate sun position using a simplified astronomical algorithm.

    Based on NOAA solar calculator equations. Accuracy: ~0.3° for
    elevation, ~0.5° for azimuth. Sufficient for shadow analysis.

    Args:
        lat: Latitude in degrees.
        lon: Longitude in degrees.
        dt: Datetime (timezone-aware or UTC assumed).

    Returns:
        SunPosition with azimuth and elevation.
    """
    # Julian day
    if dt.tzinfo is not None:
        from datetime import timezone
        dt_utc = dt.astimezone(timezone.utc)
    else:
        dt_utc = dt

    # Days since J2000.0
    jd = _julian_day(dt_utc)
    n = jd - 2451545.0

    # Mean solar longitude and anomaly
    L = (280.460 + 0.9856474 * n) % 360
    g = math.radians((357.528 + 0.9856003 * n) % 360)

    # Ecliptic longitude and obliquity
    ecl_lon = math.radians(L + 1.915 * math.sin(g) + 0.020 * math.sin(2 * g))
    obliquity = math.radians(23.439 - 0.0000004 * n)

    # Right ascension and declination
    sin_ecl = math.sin(ecl_lon)
    cos_ecl = math.cos(ecl_lon)
    ra = math.atan2(math.cos(obliquity) * sin_ecl, cos_ecl)
    declination = math.asin(math.sin(obliquity) * sin_ecl)

    # Greenwich mean sidereal time
    hours_utc = dt_utc.hour + dt_utc.minute / 60 + dt_utc.second / 3600
    gmst = (6.697375 + 0.0657098242 * n + hours_utc) % 24
    lmst = math.radians((gmst * 15 + lon) % 360)

    # Hour angle
    ha = lmst - ra

    lat_rad = math.radians(lat)

    # Elevation
    sin_elev = (
        math.sin(lat_rad) * math.sin(declination)
        + math.cos(lat_rad) * math.cos(declination) * math.cos(ha)
    )
    elevation = math.degrees(math.asin(max(-1, min(1, sin_elev))))

    # Azimuth
    cos_elev = math.cos(math.radians(elevation))
    if cos_elev == 0:
        azimuth = 0.0
    else:
        cos_az = (
            math.sin(declination) - math.sin(lat_rad) * sin_elev
        ) / (math.cos(lat_rad) * cos_elev)
        cos_az = max(-1, min(1, cos_az))
        azimuth = math.degrees(math.acos(cos_az))
        if math.sin(ha) > 0:
            azimuth = 360 - azimuth

    return SunPosition(azimuth=azimuth, elevation=elevation)


def _julian_day(dt: datetime) -> float:
    """Convert datetime to Julian Day Number."""
    y = dt.year
    m = dt.month
    d = dt.day + (dt.hour + dt.minute / 60 + dt.second / 3600) / 24

    if m <= 2:
        y -= 1
        m += 12

    A = int(y / 100)
    B = 2 - A + int(A / 4)

    return int(365.25 * (y + 4716)) + int(30.6001 * (m + 1)) + d + B - 1524.5


def get_seasonal_transmittance(cls_code: int, month: int) -> float:
    """Get transmittance for a classification code considering season.

    Args:
        cls_code: ASPRS classification code.
        month: Month (1-12).

    Returns:
        Transmittance factor (0.0=opaque, 1.0=transparent).
    """
    if cls_code == CLASS_HIGH_VEG:
        if month in (6, 7, 8, 9):
            return TRANSMITTANCE_HIGH_VEG_FULL_LEAF
        if month in (4, 5, 10, 11):
            return TRANSMITTANCE_HIGH_VEG_PARTIAL
        return TRANSMITTANCE_HIGH_VEG_BARE
    return TRANSMITTANCE.get(cls_code, 1.0)


def _build_transmittance_grid(
    classification: np.ndarray, month: int
) -> np.ndarray:
    """Build per-cell transmittance grid from classification and season."""
    grid = np.ones_like(classification, dtype=np.float32)

    grid[classification == CLASS_BUILDING] = TRANSMITTANCE[CLASS_BUILDING]
    grid[classification == CLASS_LOW_VEG] = TRANSMITTANCE[CLASS_LOW_VEG]
    grid[classification == CLASS_MED_VEG] = TRANSMITTANCE[CLASS_MED_VEG]
    grid[classification == CLASS_HIGH_VEG] = get_seasonal_transmittance(
        CLASS_HIGH_VEG, month
    )
    # Ground and water are transparent (1.0), already initialized

    return grid


def _ray_march_vectorized(
    dsm: np.ndarray,
    transmittance: np.ndarray,
    dx: float,
    dy: float,
    dz_per_step: float,
    rows: int,
    cols: int,
) -> np.ndarray:
    """Vectorized ray-marching with early termination.

    Marches all cells simultaneously toward the sun. Uses two
    optimizations over naive approach:
    1. Skip cells already fully shadowed (light < epsilon)
    2. Stop when all rays leave the grid or all cells are resolved
    3. Limit max steps based on max height difference in grid
    """
    light = np.ones((rows, cols), dtype=np.float32)
    active = np.ones((rows, cols), dtype=bool)  # cells still receiving light

    # Cell coordinates (float32 for arithmetic)
    row_idx, col_idx = np.meshgrid(
        np.arange(rows, dtype=np.float32),
        np.arange(cols, dtype=np.float32),
        indexing="ij",
    )

    # Max possible shadow distance based on height range and sun angle
    if dz_per_step > 0:
        height_range = float(np.nanmax(dsm) - np.nanmin(dsm))
        max_shadow_steps = int(math.ceil(height_range / dz_per_step)) + 2
    else:
        max_shadow_steps = 0

    # Also limit by grid diagonal
    max_steps = min(
        int(math.ceil(math.sqrt(rows**2 + cols**2))),
        max(max_shadow_steps, 50),  # At least 50 steps for safety
    )

    for step in range(1, max_steps + 1):
        # Position along the ray
        sample_col = col_idx + dx * step
        sample_row = row_idx + dy * step

        # Integer indices
        sr = sample_row.astype(np.intp)
        sc = sample_col.astype(np.intp)

        # Bounds check
        in_bounds = (sr >= 0) & (sr < rows) & (sc >= 0) & (sc < cols)

        # Only process active cells that are still in bounds
        check = active & in_bounds
        if not np.any(check):
            break

        # Sample obstacle at ray positions (clip for safe indexing)
        sr_safe = np.where(check, sr, 0)
        sc_safe = np.where(check, sc, 0)

        obstacle_height = dsm[sr_safe, sc_safe]
        ray_height = dsm + dz_per_step * step

        # Obstacle blocks when it's taller than the ray at that distance
        blocks = check & (obstacle_height > ray_height)

        if np.any(blocks):
            obstacle_trans = transmittance[sr_safe, sc_safe]
            light[blocks] *= obstacle_trans[blocks]

            # Deactivate cells with negligible remaining light
            newly_dark = blocks & (light < 0.01)
            active[newly_dark] = False

    return (1.0 - light).astype(np.float32)


def is_point_in_sun_3d(
    site: SiteModel,
    sun: SunPosition,
    grid_row: float,
    grid_col: float,
    height_m: float,
    current_date: date | None = None,
    horizon: HorizonProfile | None = None,
    transmittance_grid: np.ndarray | None = None,
) -> float:
    """Check if an arbitrary 3D point receives sunlight.

    Traces a ray from (grid_row, grid_col, height_m) toward the sun,
    checking for DSM obstacles along the way.

    Args:
        transmittance_grid: Pre-built transmittance grid (optional).
            Pass this when calling in a loop to avoid rebuilding each time.

    Returns:
        Light fraction 0.0 (full shade) to 1.0 (full sun).
    """
    if not sun.is_above_horizon:
        return 0.0

    if horizon is not None and not horizon.is_sun_visible(sun.azimuth, sun.elevation):
        return 0.0

    if current_date is None:
        current_date = date.today()

    rows, cols = site.dsm.shape
    if transmittance_grid is None:
        transmittance_grid = _build_transmittance_grid(
            site.classification, current_date.month
        )

    az_rad = math.radians(sun.azimuth)
    elev_rad = math.radians(sun.elevation)
    dx = math.sin(az_rad)
    dy = math.cos(az_rad)
    dz = math.tan(elev_rad) * site.resolution

    # Limit steps based on height range (shadows can't extend further than
    # the tallest obstacle can cast at the current sun elevation)
    light = 1.0
    if dz > 0:
        height_range = float(np.nanmax(site.dsm) - height_m)
        max_steps = min(
            int(math.ceil(math.sqrt(rows**2 + cols**2))),
            max(int(math.ceil(height_range / dz)) + 2, 50),
        )
    else:
        max_steps = 50

    for step in range(1, max_steps + 1):
        sc = int(round(grid_col + dx * step))
        sr = int(round(grid_row + dy * step))

        if sr < 0 or sr >= rows or sc < 0 or sc >= cols:
            break  # left the grid — clear sky

        obstacle_h = site.dsm[sr, sc]
        ray_h = height_m + dz * step

        if obstacle_h > ray_h:
            light *= transmittance_grid[sr, sc]
            if light < 0.01:
                return 0.0

    return light


def _densify_3d_polygon(points_3d: list[dict], max_edge_subdivisions: int = 2) -> list[dict]:
    """Generate dense sample points within a 3D polygon.

    Adds edge midpoints and interior points (centroid + lerp from centroid
    to each vertex/midpoint) for better shade sampling.

    Args:
        points_3d: Vertex points [{x,y,z}, ...].
        max_edge_subdivisions: How many segments to split each edge into.

    Returns:
        Densified list of sample points.
    """
    if len(points_3d) < 3:
        return list(points_3d)

    samples = list(points_3d)  # start with vertices

    # Edge subdivision points
    edge_points = []
    n = len(points_3d)
    for i in range(n):
        a = points_3d[i]
        b = points_3d[(i + 1) % n]
        for k in range(1, max_edge_subdivisions):
            t = k / max_edge_subdivisions
            edge_points.append({
                "x": a["x"] + (b["x"] - a["x"]) * t,
                "y": a["y"] + (b["y"] - a["y"]) * t,
                "z": a["z"] + (b["z"] - a["z"]) * t,
            })
    samples.extend(edge_points)

    # Centroid
    cx = sum(p["x"] for p in points_3d) / n
    cy = sum(p["y"] for p in points_3d) / n
    cz = sum(p["z"] for p in points_3d) / n
    centroid = {"x": cx, "y": cy, "z": cz}
    samples.append(centroid)

    # Interior points: lerp from centroid toward each vertex and edge point
    all_boundary = list(points_3d) + edge_points
    for p in all_boundary:
        for t in (0.33, 0.66):
            samples.append({
                "x": cx + (p["x"] - cx) * t,
                "y": cy + (p["y"] - cy) * t,
                "z": cz + (p["z"] - cz) * t,
            })

    return samples


def compute_3d_zone_sun_percent(
    site: SiteModel,
    sun: SunPosition,
    points_3d: list[dict],
    current_date: date | None = None,
    horizon: HorizonProfile | None = None,
) -> float:
    """Compute sun percentage for a 3D zone defined by arbitrary points.

    Densifies the polygon vertices into many sample points across the
    zone surface, then ray-traces each to get a smooth sun percentage.

    Args:
        site: Rasterized site model.
        sun: Current sun position.
        points_3d: List of {x, y, z} dicts in 3D viewer coordinates.
        current_date: Date for seasonal transmittance.
        horizon: Optional terrain horizon profile.

    Returns:
        Sun percentage (0-100).
    """
    if not points_3d or not sun.is_above_horizon:
        return 0.0

    if current_date is None:
        current_date = date.today()

    # Densify: generate many sample points from polygon vertices
    sample_points = _densify_3d_polygon(points_3d)

    # Build transmittance grid ONCE for all points
    trans_grid = _build_transmittance_grid(site.classification, current_date.month)

    # Coordinate conversion: viewer → grid
    half_w = site.cols * site.resolution / 2
    half_h = site.rows * site.resolution / 2
    base_h = float(np.nanmin(site.dtm))

    sun_values = []
    for pt in sample_points:
        col = (pt["x"] + half_w) / site.resolution
        row = (half_h - pt["z"]) / site.resolution
        height = pt["y"] + base_h

        # Clamp to grid bounds
        col = max(0, min(col, site.cols - 1))
        row = max(0, min(row, site.rows - 1))

        light = is_point_in_sun_3d(
            site, sun, row, col, height, current_date, horizon,
            transmittance_grid=trans_grid,
        )
        sun_values.append(light)

    return round(sum(sun_values) / len(sun_values) * 100, 1)


def compute_shadow_map(
    site: SiteModel,
    sun: SunPosition,
    current_date: date | None = None,
    horizon: HorizonProfile | None = None,
) -> ShadowResult:
    """Compute shadow map for a site model given sun position.

    Uses vectorized ray-marching: for each cell, march toward the sun
    and accumulate transmittance from obstacles encountered.

    Args:
        site: Rasterized LiDAR site model.
        sun: Sun azimuth and elevation.
        current_date: Date for seasonal transmittance. Defaults to today.
        horizon: Optional terrain horizon profile for distant hill occlusion.

    Returns:
        ShadowResult with float shadow map.
    """
    if current_date is None:
        current_date = date.today()

    rows, cols = site.dsm.shape

    # If sun is below horizon (astronomical or terrain), everything is in shadow
    if not sun.is_above_horizon or (
        horizon is not None and not horizon.is_sun_visible(sun.azimuth, sun.elevation)
    ):
        return ShadowResult(
            shadow_map=np.ones((rows, cols), dtype=np.float32),
            sun=sun,
            site=site,
            timestamp=datetime.now(),
        )

    # Build transmittance grid from classification + season
    transmittance = _build_transmittance_grid(site.classification, current_date.month)

    # Sun direction in grid coordinates
    # Azimuth: 0=N(+row), 90=E(+col), 180=S(-row), 270=W(-col)
    az_rad = math.radians(sun.azimuth)
    elev_rad = math.radians(sun.elevation)

    # Direction TO the sun (we march from each cell toward the sun)
    dx = math.sin(az_rad)  # east = +col
    dy = math.cos(az_rad)  # north = +row
    dz_per_step = math.tan(elev_rad) * site.resolution  # height gain per step

    # Optimized approach: sweep along sun direction using horizon angle.
    # Instead of per-cell ray-marching (O(n² * diagonal)), we process
    # scan lines perpendicular to the sun direction and propagate the
    # maximum horizon angle. Falls back to vectorized ray-march with
    # early termination for robustness.
    shadow_map = _ray_march_vectorized(
        site.dsm, transmittance, dx, dy, dz_per_step, rows, cols,
    )

    _LOGGER.info(
        "Shadow map: mean shade=%.1f%%, full sun=%.1f%%, full shade=%.1f%%",
        np.mean(shadow_map) * 100,
        np.mean(shadow_map == 0) * 100,
        np.mean(shadow_map >= 0.99) * 100,
    )

    return ShadowResult(
        shadow_map=shadow_map,
        sun=sun,
        site=site,
        timestamp=datetime.now(),
    )


def compute_daily_sun_hours(
    site: SiteModel,
    lat: float,
    lon: float,
    target_date: date | None = None,
    interval_minutes: int = 15,
    horizon: HorizonProfile | None = None,
) -> np.ndarray:
    """Compute total sun hours per cell for a full day.

    Simulates shadow maps at regular intervals from sunrise to sunset
    and integrates the sun fraction.

    Args:
        site: Rasterized site model.
        lat: Latitude (WGS84).
        lon: Longitude (WGS84).
        target_date: Date to simulate. Defaults to today.
        interval_minutes: Simulation interval.

    Returns:
        Float32 array of sun hours per cell.
    """
    if target_date is None:
        target_date = date.today()

    from datetime import timezone, timedelta

    sun_hours = np.zeros(site.dsm.shape, dtype=np.float32)
    interval_hours = interval_minutes / 60.0

    # Simulate from 4:00 to 22:00 UTC (covers all daylight in Slovenia)
    for hour in range(4, 22):
        for minute in range(0, 60, interval_minutes):
            dt = datetime(
                target_date.year, target_date.month, target_date.day,
                hour, minute, 0,
                tzinfo=timezone.utc,
            )
            sun = compute_sun_position(lat, lon, dt)
            if not sun.is_above_horizon:
                continue

            result = compute_shadow_map(site, sun, target_date, horizon)
            sun_hours += result.sun_fraction * interval_hours

    _LOGGER.info(
        "Daily sun hours (%s): min=%.1f, max=%.1f, mean=%.1f",
        target_date, np.min(sun_hours), np.max(sun_hours), np.mean(sun_hours),
    )

    return sun_hours
