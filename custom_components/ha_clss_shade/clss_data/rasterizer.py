"""Rasterize LAZ point cloud files into DSM/DTM numpy grids."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import laspy
import numpy as np

from .geo import wgs84_to_d96tm

_LOGGER = logging.getLogger(__name__)

# ASPRS classification codes
CLASS_GROUND = 2

# Classes to discard before rasterization
CLASSES_NOISE = frozenset({0, 1, 7, 17, 18, 21})

# Chunk size for reading large LAZ files
READ_CHUNK_SIZE = 500_000


@dataclass
class SiteModel:
    """Rasterized site model from LiDAR data.

    All grids share the same shape and coordinate system.
    Grid origin is at the SW corner (min easting, min northing).
    Row 0 = southernmost row, increasing northward.
    """

    dsm: np.ndarray  # Digital Surface Model — max Z per cell (meters)
    dtm: np.ndarray  # Digital Terrain Model — ground Z per cell (meters)
    classification: np.ndarray  # Class of highest point per cell (uint8)
    resolution: float  # Cell size in meters
    origin_e: float  # Easting of SW corner (D96/TM)
    origin_n: float  # Northing of SW corner (D96/TM)
    center_e: float  # Center easting (D96/TM)
    center_n: float  # Center northing (D96/TM)

    @property
    def rows(self) -> int:
        return self.dsm.shape[0]

    @property
    def cols(self) -> int:
        return self.dsm.shape[1]

    @property
    def height_above_ground(self) -> np.ndarray:
        """Normalized height: DSM - DTM."""
        return self.dsm - self.dtm

    def save(self, path: Path) -> None:
        """Save site model to compressed .npz file."""
        np.savez_compressed(
            path,
            dsm=self.dsm,
            dtm=self.dtm,
            classification=self.classification,
            resolution=np.array(self.resolution),
            origin_e=np.array(self.origin_e),
            origin_n=np.array(self.origin_n),
            center_e=np.array(self.center_e),
            center_n=np.array(self.center_n),
        )
        size_mb = path.stat().st_size / (1024 * 1024)
        _LOGGER.info("Saved site model to %s (%.1f MB)", path, size_mb)

    @classmethod
    def load(cls, path: Path) -> SiteModel:
        """Load site model from .npz file."""
        data = np.load(path)
        return cls(
            dsm=data["dsm"],
            dtm=data["dtm"],
            classification=data["classification"],
            resolution=float(data["resolution"]),
            origin_e=float(data["origin_e"]),
            origin_n=float(data["origin_n"]),
            center_e=float(data["center_e"]),
            center_n=float(data["center_n"]),
        )


def rasterize_laz(
    laz_paths: list[Path],
    center_lat: float,
    center_lon: float,
    radius_m: float = 500.0,
    resolution: float | None = None,
) -> SiteModel:
    """Rasterize LAZ file(s) into a SiteModel.

    Reads point cloud data, clips to a circular area around the center,
    and builds DSM, DTM, and classification grids.

    Args:
        laz_paths: Paths to LAZ/LAS files.
        center_lat: Center latitude (WGS84).
        center_lon: Center longitude (WGS84).
        radius_m: Clip radius in meters.
        resolution: Cell size in meters. Auto-calculated from point
            density if None (~4 points per cell).

    Returns:
        Rasterized SiteModel.
    """
    center_e, center_n = wgs84_to_d96tm(center_lat, center_lon)

    # Collect points from all LAZ files
    all_x, all_y, all_z, all_cls = [], [], [], []

    for laz_path in laz_paths:
        _LOGGER.info("Reading %s", laz_path.name)
        x, y, z, cls = _read_laz_clipped(laz_path, center_e, center_n, radius_m)
        if len(x) > 0:
            all_x.append(x)
            all_y.append(y)
            all_z.append(z)
            all_cls.append(cls)
            _LOGGER.info("  %d points within radius", len(x))
        else:
            _LOGGER.warning("  No points within radius from %s", laz_path.name)

    if not all_x:
        raise ValueError("No points found within radius from any LAZ file")

    x = np.concatenate(all_x)
    y = np.concatenate(all_y)
    z = np.concatenate(all_z)
    cls = np.concatenate(all_cls)

    _LOGGER.info("Total points: %d", len(x))

    # Auto-calculate resolution from point density
    if resolution is None:
        resolution = _auto_resolution(x, y, radius_m)

    _LOGGER.info("Grid resolution: %.2f m", resolution)

    # Build grid
    return _build_grids(x, y, z, cls, center_e, center_n, radius_m, resolution)


def _read_laz_clipped(
    path: Path,
    center_e: float,
    center_n: float,
    radius_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Read LAZ file and clip to circular area, filtering noise classes."""
    all_x, all_y, all_z, all_cls = [], [], [], []

    # Use square pre-filter for efficiency, then circular clip
    e_min = center_e - radius_m
    e_max = center_e + radius_m
    n_min = center_n - radius_m
    n_max = center_n + radius_m

    with laspy.open(path) as reader:
        for chunk in reader.chunk_iterator(READ_CHUNK_SIZE):
            x = chunk.x
            y = chunk.y
            z = chunk.z
            cls = chunk.classification

            # Square pre-filter
            mask = (x >= e_min) & (x <= e_max) & (y >= n_min) & (y <= n_max)
            x, y, z, cls = x[mask], y[mask], z[mask], cls[mask]

            if len(x) == 0:
                continue

            # Remove noise classes
            noise_mask = np.zeros(len(cls), dtype=bool)
            for nc in CLASSES_NOISE:
                noise_mask |= cls == nc
            keep = ~noise_mask
            x, y, z, cls = x[keep], y[keep], z[keep], cls[keep]

            if len(x) == 0:
                continue

            # Circular clip
            dist_sq = (x - center_e) ** 2 + (y - center_n) ** 2
            circle = dist_sq <= radius_m**2
            all_x.append(x[circle])
            all_y.append(y[circle])
            all_z.append(z[circle])
            all_cls.append(cls[circle])

    if not all_x:
        return np.array([]), np.array([]), np.array([]), np.array([], dtype=np.uint8)

    return (
        np.concatenate(all_x),
        np.concatenate(all_y),
        np.concatenate(all_z),
        np.concatenate(all_cls).astype(np.uint8),
    )


def _read_laz_clipped_rgb(
    path: Path,
    center_e: float,
    center_n: float,
    radius_m: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray | None]:
    """Read LAZ file clipped to circular area, with optional RGB.

    Returns (x, y, z, classification, rgb) where rgb is Nx3 uint8 or None.
    """
    all_x, all_y, all_z, all_cls = [], [], [], []
    all_rgb = []
    has_rgb = None

    e_min = center_e - radius_m
    e_max = center_e + radius_m
    n_min = center_n - radius_m
    n_max = center_n + radius_m

    with laspy.open(path) as reader:
        if has_rgb is None:
            dims = {d.name for d in reader.header.point_format.dimensions}
            has_rgb = "red" in dims and "green" in dims and "blue" in dims

        for chunk in reader.chunk_iterator(READ_CHUNK_SIZE):
            x = chunk.x
            y = chunk.y
            z = chunk.z
            cls = chunk.classification

            mask = (x >= e_min) & (x <= e_max) & (y >= n_min) & (y <= n_max)
            x, y, z, cls = x[mask], y[mask], z[mask], cls[mask]

            if has_rgb:
                r = np.asarray(chunk.red)[mask]
                g = np.asarray(chunk.green)[mask]
                b = np.asarray(chunk.blue)[mask]

            if len(x) == 0:
                continue

            noise_mask = np.zeros(len(cls), dtype=bool)
            for nc in CLASSES_NOISE:
                noise_mask |= cls == nc
            keep = ~noise_mask
            x, y, z, cls = x[keep], y[keep], z[keep], cls[keep]

            if has_rgb:
                r, g, b = r[keep], g[keep], b[keep]

            if len(x) == 0:
                continue

            dist_sq = (x - center_e) ** 2 + (y - center_n) ** 2
            circle = dist_sq <= radius_m**2
            all_x.append(x[circle])
            all_y.append(y[circle])
            all_z.append(z[circle])
            all_cls.append(cls[circle])

            if has_rgb:
                all_rgb.append(np.column_stack([r[circle], g[circle], b[circle]]))

    if not all_x:
        return np.array([]), np.array([]), np.array([]), np.array([], dtype=np.uint8), None

    rgb = None
    if has_rgb and all_rgb:
        rgb_raw = np.concatenate(all_rgb)
        # LAZ stores 16-bit RGB (0-65535), normalize to 8-bit (0-255)
        if rgb_raw.max() > 255:
            rgb = (rgb_raw / 256).astype(np.uint8)
        else:
            rgb = rgb_raw.astype(np.uint8)

    return (
        np.concatenate(all_x),
        np.concatenate(all_y),
        np.concatenate(all_z),
        np.concatenate(all_cls).astype(np.uint8),
        rgb,
    )


def _auto_resolution(x: np.ndarray, y: np.ndarray, radius_m: float) -> float:
    """Calculate resolution targeting ~4 points per cell.

    Snapped to 0.5m increments, clamped to [0.5, 5.0].
    """
    area = np.pi * radius_m**2
    density = len(x) / area  # points per m²
    target_pts_per_cell = 4.0

    if density > 0:
        cell_area = target_pts_per_cell / density
        res = np.sqrt(cell_area)
    else:
        res = 1.0

    # Snap to 0.5m increments
    res = round(res * 2) / 2
    return float(np.clip(res, 0.5, 5.0))


def _build_grids(
    x: np.ndarray,
    y: np.ndarray,
    z: np.ndarray,
    cls: np.ndarray,
    center_e: float,
    center_n: float,
    radius_m: float,
    resolution: float,
) -> SiteModel:
    """Build DSM, DTM, and classification grids from point cloud."""
    # Grid extent (square bounding box around circular clip)
    origin_e = center_e - radius_m
    origin_n = center_n - radius_m
    grid_size = int(np.ceil(2 * radius_m / resolution))

    # Point -> grid cell indices
    col = ((x - origin_e) / resolution).astype(int)
    row = ((y - origin_n) / resolution).astype(int)

    # Clamp to grid bounds
    valid = (col >= 0) & (col < grid_size) & (row >= 0) & (row < grid_size)
    col, row, z, cls = col[valid], row[valid], z[valid], cls[valid]

    # Initialize grids
    dsm = np.full((grid_size, grid_size), np.nan, dtype=np.float32)
    dtm = np.full((grid_size, grid_size), np.nan, dtype=np.float32)
    classification = np.zeros((grid_size, grid_size), dtype=np.uint8)

    # Ground accumulator for DTM (mean of ground points)
    ground_sum = np.zeros((grid_size, grid_size), dtype=np.float64)
    ground_count = np.zeros((grid_size, grid_size), dtype=np.int32)

    # DSM: max Z per cell, track which class the max-Z point belongs to
    dsm_z_max = np.full((grid_size, grid_size), -np.inf, dtype=np.float64)

    # Process all points
    is_ground = cls == CLASS_GROUND

    # Ground points -> DTM
    g_row, g_col, g_z = row[is_ground], col[is_ground], z[is_ground]
    np.add.at(ground_sum, (g_row, g_col), g_z)
    np.add.at(ground_count, (g_row, g_col), 1)

    # All points -> DSM (find max Z per cell)
    flat_idx = row * grid_size + col
    for i in range(len(flat_idx)):
        r, c = row[i], col[i]
        if z[i] > dsm_z_max[r, c]:
            dsm_z_max[r, c] = z[i]
            classification[r, c] = cls[i]

    # Finalize DTM
    has_ground = ground_count > 0
    dtm[has_ground] = (ground_sum[has_ground] / ground_count[has_ground]).astype(np.float32)

    # Finalize DSM
    has_dsm = dsm_z_max > -np.inf
    dsm[has_dsm] = dsm_z_max[has_dsm].astype(np.float32)

    # Fill DSM gaps with nearest neighbor interpolation
    dsm = _fill_nan_nearest(dsm)

    # Fill DTM gaps: interpolate from ground-classified cells only.
    # Previous approach used DSM as fallback, but under dense vegetation
    # DSM includes tree canopy height → artificial terrain bumps.
    # Nearest-neighbor from actual ground cells gives smooth terrain.
    dtm = _fill_nan_nearest(dtm)

    filled_cells = np.sum(~np.isnan(dsm))
    total_cells = grid_size * grid_size
    _LOGGER.info(
        "Grid %dx%d, %.1f%% filled, res=%.1fm",
        grid_size, grid_size, filled_cells / total_cells * 100, resolution,
    )

    return SiteModel(
        dsm=dsm,
        dtm=dtm,
        classification=classification,
        resolution=resolution,
        origin_e=origin_e,
        origin_n=origin_n,
        center_e=center_e,
        center_n=center_n,
    )


def _fill_nan_nearest(grid: np.ndarray) -> np.ndarray:
    """Fill NaN cells with nearest valid neighbor value."""
    from scipy.ndimage import distance_transform_edt

    nan_mask = np.isnan(grid)
    if not np.any(nan_mask):
        return grid
    if np.all(nan_mask):
        return np.zeros_like(grid)

    # distance_transform_edt returns indices of nearest non-NaN cell
    _, nearest_idx = distance_transform_edt(nan_mask, return_distances=True, return_indices=True)
    filled = grid.copy()
    filled[nan_mask] = grid[nearest_idx[0][nan_mask], nearest_idx[1][nan_mask]]
    return filled
