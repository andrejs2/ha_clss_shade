"""WebSocket API for CLSS Shade frontend panel."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import CONF_CUSTOM_ZONES, DOMAIN

_LOGGER = logging.getLogger(__name__)


@callback
def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register WebSocket commands for the panel."""
    websocket_api.async_register_command(hass, ws_get_config)
    websocket_api.async_register_command(hass, ws_save_zones)


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
