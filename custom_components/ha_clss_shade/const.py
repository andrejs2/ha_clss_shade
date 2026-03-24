"""Constants for CLSS Shade integration."""

from __future__ import annotations

DOMAIN = "ha_clss_shade"

# CLSS LiDAR classification codes (ASPRS)
CLASS_GROUND = 2
CLASS_LOW_VEGETATION = 3
CLASS_MEDIUM_VEGETATION = 4
CLASS_HIGH_VEGETATION = 5
CLASS_BUILDING = 6
CLASS_WATER = 9

# Classes to filter out before processing
CLASSES_NOISE = {0, 1, 7, 17, 18, 21}

# Default transmittance by classification (0.0 = opaque, 1.0 = transparent)
DEFAULT_TRANSMITTANCE = {
    CLASS_GROUND: 1.0,
    CLASS_LOW_VEGETATION: 0.6,
    CLASS_MEDIUM_VEGETATION: 0.4,
    CLASS_HIGH_VEGETATION: 0.35,
    CLASS_BUILDING: 0.0,
    CLASS_WATER: 1.0,
}

# EPSG:3794 (D96/TM) parameters
CRS_EPSG = 3794
CRS_CENTRAL_MERIDIAN = 15.0
CRS_FALSE_EASTING = 500000
CRS_FALSE_NORTHING = -5000000

# ARSO LiDAR server
ARSO_LIDAR_BASE_URL = "http://gis.arso.gov.si/lidar"
ARSO_TILE_SIZE_M = 1000  # 1 km tiles

# Default configuration
DEFAULT_RADIUS_M = 500
DEFAULT_UPDATE_INTERVAL_MIN = 5
DEFAULT_CELL_RESOLUTION_M = 1.0
