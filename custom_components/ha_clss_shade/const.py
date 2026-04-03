"""Constants for CLSS Shade integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coordinator import ClssShadeCoordinator

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
DEFAULT_RADIUS_M = 200
DEFAULT_UPDATE_INTERVAL_MIN = 5

# Config keys
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_RADIUS = "radius"
CONF_NAME = "name"
CONF_INCLUDE_NEIGHBORS = "include_neighbors"
CONF_CUSTOM_ZONES = "custom_zones"
CONF_3D_ZONES = "zones_3d"
CONF_PV_CAPACITY_WP = "pv_capacity_wp"
CONF_PV_ZONE = "pv_zone"
CONF_PV_ZONES_CONFIG = "pv_zones_config"
CONF_PV_REAL_ENTITY = "pv_real_entity"
CONF_PV_PANEL_TILT = "pv_panel_tilt"
CONF_PV_PANEL_AZIMUTH = "pv_panel_azimuth"
DEFAULT_PV_CAPACITY_WP = 5000
DEFAULT_PV_PANEL_TILT = 30  # degrees from horizontal
DEFAULT_PV_PANEL_AZIMUTH = 180  # degrees, 180 = south

# Forecast
DEFAULT_FORECAST_INTERVAL_MIN = 60  # shadow forecast refresh interval
DEFAULT_FORECAST_WEATHER_INTERVAL_MIN = 30  # weather forecast refresh interval
FORECAST_STEP_MINUTES = 60  # shadow computation time step (all days)
FORECAST_STEP_MINUTES_FAR = 60  # shadow computation time step (days 2+)
FORECAST_DAYS = 5  # total forecast days (today + 4)
FORECAST_FAR_CACHE_HOURS = 3  # cache far-day shadow data for N hours

# INCA nowcasting
INCA_BASE_URL = "https://meteo.arso.gov.si"
INCA_SI0ZM_JSON = "/uploads/probase/www/nowcast/inca/inca_si0zm_data.json?prod=si0zm"
INCA_REFRESH_INTERVAL_MIN = 15  # INCA updates every 15 min
INCA_BBOX = (44.67, 12.1, 47.42, 17.44)  # lat_min, lon_min, lat_max, lon_max
INCA_WIDTH = 800
INCA_HEIGHT = 600
INCA_MAX_GHI = 1200  # W/m² max for color scale calibration

# Crop coefficients (FAO-56 Kc mid-season values)
CROP_KC: dict[str, float] = {
    "lawn": 0.95,
    "vegetables": 1.05,
    "berries": 0.85,
    "fruit_trees": 0.95,
    "flowers": 0.90,
    "garden": 1.00,
    "greenhouse": 1.0,
}

# Zone types eligible for per-zone irrigation sensors
IRRIGABLE_ZONE_TYPES: set[str] = set(CROP_KC.keys())

# Seasonal irrigation multiplier by month (1-12)
# Winter: no irrigation needed; spring/autumn: reduced; summer: full
SEASONAL_FACTOR: dict[int, float] = {
    1: 0.0,   # jan — dormant
    2: 0.0,   # feb — dormant
    3: 0.3,   # mar — early spring
    4: 0.6,   # apr — spring
    5: 0.9,   # maj — late spring
    6: 1.0,   # jun — full season
    7: 1.0,   # jul — full season
    8: 1.0,   # avg — full season
    9: 0.9,   # sep — late summer
    10: 0.5,  # okt — autumn
    11: 0.2,  # nov — late autumn
    12: 0.0,  # dec — dormant
}

# Data storage
DATA_DIR_NAME = "clss_shade"


@dataclass
class ClssShadeRuntimeData:
    """Runtime data for a CLSS Shade config entry."""

    coordinator: ClssShadeCoordinator
