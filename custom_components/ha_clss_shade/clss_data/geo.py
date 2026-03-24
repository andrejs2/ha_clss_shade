"""Coordinate transforms between WGS84 and EPSG:3794 (D96/TM) and tile utilities."""

from __future__ import annotations

import math

from pyproj import Transformer

# Slovenia bounding box (WGS84)
SI_LAT_MIN = 45.42
SI_LAT_MAX = 46.88
SI_LON_MIN = 13.38
SI_LON_MAX = 16.61

# Tile size in meters
TILE_SIZE_M = 1000

# Reusable transformers (thread-safe, cached)
_to_d96tm = Transformer.from_crs("EPSG:4326", "EPSG:3794", always_xy=True)
_to_wgs84 = Transformer.from_crs("EPSG:3794", "EPSG:4326", always_xy=True)


def is_in_slovenia(lat: float, lon: float) -> bool:
    """Check if WGS84 coordinates are within Slovenia's bounding box."""
    return SI_LAT_MIN <= lat <= SI_LAT_MAX and SI_LON_MIN <= lon <= SI_LON_MAX


def wgs84_to_d96tm(lat: float, lon: float) -> tuple[float, float]:
    """Convert WGS84 (lat, lon) to EPSG:3794 D96/TM (easting, northing).

    Args:
        lat: Latitude in degrees (WGS84).
        lon: Longitude in degrees (WGS84).

    Returns:
        Tuple of (easting, northing) in meters.
    """
    easting, northing = _to_d96tm.transform(lon, lat)
    return easting, northing


def d96tm_to_wgs84(easting: float, northing: float) -> tuple[float, float]:
    """Convert EPSG:3794 D96/TM (easting, northing) to WGS84 (lat, lon).

    Args:
        easting: Easting in meters (D96/TM).
        northing: Northing in meters (D96/TM).

    Returns:
        Tuple of (lat, lon) in degrees.
    """
    lon, lat = _to_wgs84.transform(easting, northing)
    return lat, lon


def get_tile_coords(easting: float, northing: float) -> tuple[int, int]:
    """Get ARSO tile coordinates for a D96/TM position.

    Tiles are 1x1 km. Tile coordinate = floor(position / 1000).

    Args:
        easting: Easting in meters (D96/TM).
        northing: Northing in meters (D96/TM).

    Returns:
        Tuple of (tile_e, tile_n) — integer km coordinates.
    """
    tile_e = math.floor(easting / TILE_SIZE_M)
    tile_n = math.floor(northing / TILE_SIZE_M)
    return tile_e, tile_n


def get_tile_origin(tile_e: int, tile_n: int) -> tuple[float, float]:
    """Get the SW corner (origin) of a tile in D96/TM meters.

    Args:
        tile_e: Tile easting coordinate (km).
        tile_n: Tile northing coordinate (km).

    Returns:
        Tuple of (easting, northing) in meters for SW corner.
    """
    return float(tile_e * TILE_SIZE_M), float(tile_n * TILE_SIZE_M)


def get_tiles_for_radius(
    lat: float, lon: float, radius_m: float
) -> list[tuple[int, int]]:
    """Get all tile coordinates needed to cover a circular area.

    Args:
        lat: Center latitude (WGS84).
        lon: Center longitude (WGS84).
        radius_m: Radius in meters.

    Returns:
        List of (tile_e, tile_n) tuples covering the area.
    """
    easting, northing = wgs84_to_d96tm(lat, lon)

    # Bounding box in D96/TM
    e_min = easting - radius_m
    e_max = easting + radius_m
    n_min = northing - radius_m
    n_max = northing + radius_m

    # Tile range
    te_min = math.floor(e_min / TILE_SIZE_M)
    te_max = math.floor(e_max / TILE_SIZE_M)
    tn_min = math.floor(n_min / TILE_SIZE_M)
    tn_max = math.floor(n_max / TILE_SIZE_M)

    tiles = []
    for te in range(te_min, te_max + 1):
        for tn in range(tn_min, tn_max + 1):
            tiles.append((te, tn))

    return tiles


def tile_filename(tile_e: int, tile_n: int) -> str:
    """Generate the LAZ filename for a tile.

    Format: TM_{eastingKm}_{northingKm}.laz

    Args:
        tile_e: Tile easting coordinate (km).
        tile_n: Tile northing coordinate (km).

    Returns:
        Filename string, e.g. "TM_462_101.laz"
    """
    return f"TM_{tile_e}_{tile_n}.laz"
