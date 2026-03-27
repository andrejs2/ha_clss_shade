"""INCA nowcasting client — fetch location-specific solar radiation from ARSO."""

from __future__ import annotations

import colorsys
import logging
from io import BytesIO

import aiohttp

from .const import (
    INCA_BASE_URL,
    INCA_BBOX,
    INCA_HEIGHT,
    INCA_MAX_GHI,
    INCA_SI0ZM_JSON,
    INCA_WIDTH,
)

_LOGGER = logging.getLogger(__name__)


def _latlon_to_pixel(lat: float, lon: float) -> tuple[int, int]:
    """Convert WGS84 lat/lon to pixel coordinates in the INCA PNG.

    The PNG covers bbox (lat_min, lon_min, lat_max, lon_max) = (44.67, 12.1, 47.42, 17.44)
    at 800×600 pixels. Origin is top-left corner.
    """
    lat_min, lon_min, lat_max, lon_max = INCA_BBOX
    px = int((lon - lon_min) / (lon_max - lon_min) * INCA_WIDTH)
    py = int((lat_max - lat) / (lat_max - lat_min) * INCA_HEIGHT)
    return px, py


def _pixel_to_ghi(pixel: tuple) -> float | None:
    """Convert INCA si0zm PNG pixel (RGBA) to GHI in W/m².

    The INCA si0zm PNG uses a rainbow color scale:
    - Transparent (alpha=0): no data (sea, outside coverage)
    - Blue (hue≈0.59-0.67): low GHI (0-150 W/m²)
    - Cyan (hue≈0.50): ~300 W/m²
    - Green (hue≈0.33): ~600 W/m²
    - Yellow (hue≈0.17): ~900 W/m²
    - Red (hue≈0.00): ~1200 W/m² (maximum)
    - Purple/magenta (hue>0.67): very low GHI (near 0)

    Returns:
        GHI in W/m², or None for no-data pixels.
    """
    # Handle different pixel formats
    if len(pixel) == 4:
        r, g, b, a = pixel
        if a == 0:
            return None  # transparent = no data
    elif len(pixel) == 3:
        r, g, b = pixel
    else:
        return None

    # Black or near-black = 0
    if r == 0 and g == 0 and b == 0:
        return 0.0

    # Convert to HSV
    h, s, v = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

    # Low saturation or value = near-zero or ambiguous
    if s < 0.1 or v < 0.05:
        return 0.0

    # Map hue to GHI
    # Blue (h≈0.67) = 0 W/m², Red (h≈0.0) = max GHI
    # Purple/magenta (h>0.67) wraps around = very low
    if h > 0.67:
        # Purple/magenta zone — map 0.67-1.0 to low values
        ghi = max(0.0, (1.0 - h) / 0.33 * 50.0)
    else:
        # Main rainbow zone: blue(0.67) → red(0.0)
        ghi = (0.67 - h) / 0.67 * INCA_MAX_GHI

    return round(max(0.0, min(ghi, INCA_MAX_GHI)), 1)


async def fetch_inca_solar_radiation(
    session: aiohttp.ClientSession,
    lat: float,
    lon: float,
) -> tuple[float | None, str | None]:
    """Fetch INCA solar radiation (GHI) for a specific location.

    Downloads the latest INCA si0zm PNG and reads the pixel value at
    the given lat/lon. The PNG is ~50 KB and covers all of Slovenia
    at 1 km resolution.

    Args:
        session: aiohttp client session (from HA).
        lat: Latitude (WGS84).
        lon: Longitude (WGS84).

    Returns:
        Tuple of (ghi_wm2, timestamp_iso) or (None, None) on failure.
    """
    # Check if location is within INCA coverage
    lat_min, lon_min, lat_max, lon_max = INCA_BBOX
    if not (lat_min < lat < lat_max and lon_min < lon < lon_max):
        _LOGGER.debug("Location (%.4f, %.4f) outside INCA coverage", lat, lon)
        return None, None

    try:
        # Step 1: Fetch JSON to get latest PNG path
        json_url = f"{INCA_BASE_URL}{INCA_SI0ZM_JSON}"
        async with session.get(json_url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
            if resp.status != 200:
                _LOGGER.warning("INCA JSON fetch failed: HTTP %d", resp.status)
                return None, None
            entries = await resp.json(content_type=None)

        if not entries:
            return None, None

        # Get the most recent ANL entry
        latest = None
        for entry in reversed(entries):
            if entry.get("mode") == "ANL":
                latest = entry
                break
        if latest is None:
            latest = entries[-1]

        png_path = latest.get("path", "")
        timestamp = latest.get("valid", "")

        if not png_path:
            return None, None

        # Step 2: Download PNG
        png_url = f"{INCA_BASE_URL}{png_path}"
        async with session.get(png_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status != 200:
                _LOGGER.warning("INCA PNG fetch failed: HTTP %d", resp.status)
                return None, None
            png_data = await resp.read()

        # Step 3: Read pixel at location
        from PIL import Image

        img = Image.open(BytesIO(png_data))
        px, py = _latlon_to_pixel(lat, lon)

        # Clamp to image bounds
        px = max(0, min(px, img.width - 1))
        py = max(0, min(py, img.height - 1))

        pixel = img.getpixel((px, py))

        # Step 4: Convert pixel to GHI
        ghi = _pixel_to_ghi(pixel)

        _LOGGER.debug(
            "INCA GHI at (%.4f,%.4f) pixel(%d,%d): RGBA%s → %s W/m²",
            lat, lon, px, py, pixel, ghi,
        )

        return ghi, timestamp

    except Exception:
        _LOGGER.exception("INCA fetch failed")
        return None, None
