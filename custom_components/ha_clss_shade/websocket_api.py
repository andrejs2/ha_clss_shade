"""WebSocket API for CLSS Shade frontend panel."""

from __future__ import annotations

import base64
import logging

import numpy as np
import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_3D_ZONES, CONF_CUSTOM_ZONES, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register WebSocket commands for the panel."""
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_zones)
    websocket_api.async_register_command(hass, ws_get_terrain)
    websocket_api.async_register_command(hass, ws_save_3d_zones)
    websocket_api.async_register_command(hass, ws_get_3d_zones)
    websocket_api.async_register_command(hass, ws_get_pointcloud)


@websocket_api.websocket_command(
    {vol.Required("type"): "ha_clss_shade/get_config"}
)
@callback
def ws_get_config(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return integration config and zones for the panel."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "No CLSS Shade entry found")
        return

    result = []
    for entry in entries:
        zones = entry.options.get(CONF_CUSTOM_ZONES, [])
        result.append(
            {
                "entry_id": entry.entry_id,
                "title": entry.title,
                "latitude": entry.data.get("latitude", hass.config.latitude),
                "longitude": entry.data.get("longitude", hass.config.longitude),
                "radius": entry.options.get("radius", 200),
                "zones": zones,
            }
        )

    connection.send_result(msg["id"], {"entries": result})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_clss_shade/save_zones",
        vol.Optional("entry_id"): str,
        vol.Required("zones"): [
            {
                vol.Required("name"): str,
                vol.Required("zone_type"): str,
                vol.Required("shape"): vol.In(["polygon", "circle"]),
                vol.Optional("vertices"): [[vol.Coerce(float)]],
                vol.Optional("offset_e"): vol.Coerce(float),
                vol.Optional("offset_n"): vol.Coerce(float),
                vol.Optional("radius"): vol.Coerce(float),
                vol.Optional("color"): str,
            }
        ],
    }
)
@websocket_api.async_response
async def ws_save_zones(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Save zones from the panel to config entry options."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "No CLSS Shade entry found")
        return

    entry_id = msg.get("entry_id")
    if entry_id:
        entry = next((e for e in entries if e.entry_id == entry_id), None)
    else:
        entry = entries[0]

    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    # Update options with new zones (preserving other options)
    new_options = {**entry.options, CONF_CUSTOM_ZONES: msg["zones"]}
    hass.config_entries.async_update_entry(entry, options=new_options)

    _LOGGER.info("Saved %d custom zones for entry %s", len(msg["zones"]), entry.title)
    connection.send_result(msg["id"], {"saved": len(msg["zones"])})


@websocket_api.websocket_command(
    {vol.Required("type"): "ha_clss_shade/get_3d_zones"}
)
@callback
def ws_get_3d_zones(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return saved 3D zones."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_result(msg["id"], {"zones": []})
        return
    zones = entries[0].options.get(CONF_3D_ZONES, [])
    connection.send_result(msg["id"], {"zones": zones})


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_clss_shade/save_3d_zones",
        vol.Optional("entry_id"): str,
        vol.Required("zones"): [
            {
                vol.Required("name"): str,
                vol.Required("points"): [
                    {
                        vol.Required("x"): vol.Coerce(float),
                        vol.Required("y"): vol.Coerce(float),
                        vol.Required("z"): vol.Coerce(float),
                    }
                ],
                vol.Optional("color"): str,
                vol.Optional("zone_type"): str,
            }
        ],
    }
)
@websocket_api.async_response
async def ws_save_3d_zones(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Save 3D zones from the panel to config entry options."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "No CLSS Shade entry found")
        return

    entry_id = msg.get("entry_id")
    entry = (
        next((e for e in entries if e.entry_id == entry_id), None)
        if entry_id
        else entries[0]
    )
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    new_options = {**entry.options, CONF_3D_ZONES: msg["zones"]}
    hass.config_entries.async_update_entry(entry, options=new_options)

    _LOGGER.info("Saved %d 3D zones for entry %s", len(msg["zones"]), entry.title)
    connection.send_result(msg["id"], {"saved": len(msg["zones"])})


def _encode_grid(arr: np.ndarray, dtype: str = "float32") -> str:
    """Encode numpy array as base64 string for WebSocket transfer."""
    return base64.b64encode(arr.astype(dtype).tobytes()).decode("ascii")


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_clss_shade/get_terrain",
        vol.Optional("entry_id"): str,
    }
)
@websocket_api.async_response
async def ws_get_terrain(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return DSM/DTM/classification grids for 3D viewer.

    Grids are base64-encoded: DSM and DTM as float32, classification as uint8.
    Frontend decodes with Float32Array/Uint8Array and builds Three.js mesh.
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "No CLSS Shade entry found")
        return

    entry_id = msg.get("entry_id")
    entry = (
        next((e for e in entries if e.entry_id == entry_id), None)
        if entry_id
        else entries[0]
    )
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    # Get coordinator to access site model
    runtime_data = entry.runtime_data
    if runtime_data is None:
        connection.send_error(msg["id"], "not_ready", "Integration not ready")
        return

    coordinator = runtime_data.coordinator
    site = coordinator._site
    if site is None:
        connection.send_error(msg["id"], "no_data", "Site model not loaded")
        return

    # Encode grids as base64
    result = await hass.async_add_executor_job(
        _build_terrain_payload, site
    )

    _LOGGER.info(
        "Terrain data sent: %dx%d grid, %.1fm resolution",
        site.rows, site.cols, site.resolution,
    )
    connection.send_result(msg["id"], result)


def _build_terrain_payload(site) -> dict:
    """Build terrain payload in executor thread (numpy operations)."""
    from .clss_data.geo import d96tm_to_wgs84

    # Compute WGS84 bounds for satellite texture
    sw_lat, sw_lon = d96tm_to_wgs84(site.origin_e, site.origin_n)
    ne_lat, ne_lon = d96tm_to_wgs84(
        site.origin_e + site.cols * site.resolution,
        site.origin_n + site.rows * site.resolution,
    )

    return {
        "rows": site.rows,
        "cols": site.cols,
        "resolution": site.resolution,
        "origin_e": site.origin_e,
        "origin_n": site.origin_n,
        "center_e": site.center_e,
        "center_n": site.center_n,
        "bounds_sw": [sw_lat, sw_lon],
        "bounds_ne": [ne_lat, ne_lon],
        "dsm_b64": _encode_grid(site.dsm, "float32"),
        "dtm_b64": _encode_grid(site.dtm, "float32"),
        "classification_b64": _encode_grid(site.classification, "uint8"),
    }


@websocket_api.websocket_command(
    {
        vol.Required("type"): "ha_clss_shade/get_pointcloud",
        vol.Optional("entry_id"): str,
        vol.Optional("subsample", default=1): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)
@websocket_api.async_response
async def ws_get_pointcloud(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict,
) -> None:
    """Return raw point cloud data (XYZ + classification) for 3D viewer.

    Points are base64-encoded: positions as float32 (x,y,z interleaved),
    classification as uint8. Coordinates are viewer-local (centered, Y=up).
    """
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        connection.send_error(msg["id"], "not_configured", "No CLSS Shade entry found")
        return

    entry_id = msg.get("entry_id")
    entry = (
        next((e for e in entries if e.entry_id == entry_id), None)
        if entry_id
        else entries[0]
    )
    if entry is None:
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    runtime_data = entry.runtime_data
    if runtime_data is None:
        connection.send_error(msg["id"], "not_ready", "Integration not ready")
        return

    coordinator = runtime_data.coordinator
    site = coordinator._site
    if site is None:
        connection.send_error(msg["id"], "no_data", "Site model not loaded")
        return

    # Find cached LAZ files
    laz_dir = coordinator._data_dir / "laz"
    laz_paths = sorted(laz_dir.glob("TM_*.laz")) if laz_dir.exists() else []
    if not laz_paths:
        connection.send_error(msg["id"], "no_laz", "No cached LAZ files found")
        return

    # Find POF ortophoto TIF files for RGB coloring
    # Look in data_dir, data_dir/laz, and data_dir/pof
    pof_paths = []
    for search_dir in [coordinator._data_dir, coordinator._data_dir / "laz", coordinator._data_dir / "pof"]:
        pof_paths.extend(sorted(search_dir.glob("POF_*.tif")))
    if pof_paths:
        _LOGGER.info("Found POF ortophoto(s): %s", [p.name for p in pof_paths])
    else:
        _LOGGER.info(
            "No POF ortophoto found. For RGB colors, place POF_*.tif in %s",
            coordinator._data_dir,
        )

    subsample = msg.get("subsample", 1)

    result = await hass.async_add_executor_job(
        _build_pointcloud_payload,
        laz_paths,
        site,
        subsample,
        pof_paths,
    )

    _LOGGER.info(
        "Point cloud sent: %d points (subsample=%d), %.1f MB",
        result["num_points"],
        subsample,
        len(result["positions_b64"]) * 3 / 4 / 1_000_000,
    )
    connection.send_result(msg["id"], result)


def _build_pointcloud_payload(
    laz_paths: list,
    site,
    subsample: int,
    pof_paths: list | None = None,
) -> dict:
    """Read LAZ files and build point cloud payload (executor thread)."""
    from .clss_data.rasterizer import _read_laz_clipped

    radius = site.resolution * max(site.rows, site.cols) / 2

    all_x, all_y, all_z, all_cls = [], [], [], []
    for path in laz_paths:
        x, y, z, cls = _read_laz_clipped(
            path, site.center_e, site.center_n, radius
        )
        if len(x) > 0:
            all_x.append(x)
            all_y.append(y)
            all_z.append(z)
            all_cls.append(cls)

    if not all_x:
        return {"num_points": 0, "positions_b64": "", "classification_b64": ""}

    x = np.concatenate(all_x)
    y = np.concatenate(all_y)
    z = np.concatenate(all_z)
    cls = np.concatenate(all_cls)

    # Subsample
    if subsample > 1:
        x = x[::subsample]
        y = y[::subsample]
        z = z[::subsample]
        cls = cls[::subsample]

    # Sample RGB from POF ortophoto GeoTIFF (if available)
    rgb = None
    has_rgb = False
    if pof_paths:
        rgb = _sample_pof_rgb(pof_paths, x, y)
        if rgb is not None:
            has_rgb = True
            _LOGGER.info("POF RGB sampled for %d points", len(x))

    # Convert D96/TM to viewer-local coordinates (centered, Y=up)
    # Must match mesh coordinate system in viewer3d.js:
    #   X = (easting - origin_e) - halfW
    #   Y = elevation - baseH
    #   Z = halfH - (northing - origin_n)  [north = -Z]
    half_w = site.cols * site.resolution / 2
    half_h = site.rows * site.resolution / 2
    base_h = float(np.min(site.dtm))

    vx = (x - site.origin_e) - half_w       # easting → X (centered)
    vy = z - base_h                          # elevation → Y (up)
    vz = half_h - (y - site.origin_n)        # northing → Z (north = -Z, matching mesh)

    # Interleave as [x0,y0,z0, x1,y1,z1, ...]
    positions = np.empty(len(vx) * 3, dtype=np.float32)
    positions[0::3] = vx
    positions[1::3] = vy
    positions[2::3] = vz

    result = {
        "num_points": len(vx),
        "resolution": site.resolution,
        "positions_b64": base64.b64encode(positions.tobytes()).decode("ascii"),
        "classification_b64": base64.b64encode(cls.astype(np.uint8).tobytes()).decode("ascii"),
        "has_rgb": has_rgb,
    }

    if has_rgb and rgb is not None:
        result["rgb_b64"] = base64.b64encode(rgb.tobytes()).decode("ascii")

    return result


def _sample_pof_rgb(
    pof_paths: list, x_d96: np.ndarray, y_d96: np.ndarray
) -> np.ndarray | None:
    """Sample RGB colors from POF ortophoto GeoTIFF at point positions.

    POF files are georeferenced GeoTIFF (D96/TM) with ModelTiepointTag
    and ModelPixelScaleTag. Pixel (0,0) = top-left = (origin_e, origin_n).
    Northing decreases with increasing row.
    """
    from PIL import Image

    rgb = np.zeros((len(x_d96), 3), dtype=np.uint8)
    colored = np.zeros(len(x_d96), dtype=bool)

    for pof_path in pof_paths:
        try:
            img = Image.open(pof_path)
            if img.mode != "RGB":
                _LOGGER.warning("POF %s is not RGB (mode=%s), skipping", pof_path.name, img.mode)
                continue

            tags = img.tag_v2
            pixel_scale = tags.get(33550)  # ModelPixelScaleTag
            tiepoint = tags.get(33922)     # ModelTiepointTag

            if not pixel_scale or not tiepoint:
                _LOGGER.warning("POF %s missing georeference tags, skipping", pof_path.name)
                continue

            origin_e = tiepoint[3]
            origin_n = tiepoint[4]
            sx = pixel_scale[0]
            sy = pixel_scale[1]
            w, h = img.size

            # Compute pixel coordinates for all points
            col = ((x_d96 - origin_e) / sx).astype(np.int32)
            row = ((origin_n - y_d96) / sy).astype(np.int32)

            # Points within this tile
            valid = (col >= 0) & (col < w) & (row >= 0) & (row < h) & ~colored

            if not np.any(valid):
                continue

            # Load as numpy array and sample
            img_array = np.array(img)
            rgb[valid] = img_array[row[valid], col[valid]]
            colored |= valid

            _LOGGER.info(
                "POF %s: colored %d/%d points (%.0f%%)",
                pof_path.name, np.sum(valid), len(x_d96),
                np.sum(valid) / len(x_d96) * 100,
            )

        except Exception:
            _LOGGER.exception("Error reading POF %s", pof_path.name)
            continue

    if not np.any(colored):
        return None

    return rgb
