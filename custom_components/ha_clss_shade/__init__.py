"""CLSS Shade — Home Assistant integration for Slovenian LiDAR solar/shade analysis."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "ha_clss_shade"

_LOGGER = logging.getLogger(__name__)

# Track whether domain-wide setup (panel, websocket) has been done
_DOMAIN_SETUP_DONE = "ha_clss_shade_domain_setup"


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up domain-wide resources: sidebar panel + WebSocket API."""
    if hass.data.get(_DOMAIN_SETUP_DONE):
        return True

    from .websocket_api import async_register_websocket_api

    # Register WebSocket commands
    async_register_websocket_api(hass)

    # Register static path for frontend files
    from homeassistant.components.http import StaticPathConfig

    await hass.http.async_register_static_paths(
        [
            StaticPathConfig(
                "/ha_clss_shade/frontend",
                hass.config.path("custom_components/ha_clss_shade/frontend"),
                cache_headers=False,
            )
        ]
    )

    # Register sidebar panel (iframe mode)
    from homeassistant.components.frontend import async_register_built_in_panel

    async_register_built_in_panel(
        hass,
        component_name="iframe",
        sidebar_title="CLSS Shade",
        sidebar_icon="mdi:sun-angle",
        frontend_url_path="clss-shade",
        config={"url": "/ha_clss_shade/frontend/panel.html"},
        require_admin=False,
        update=True,
    )

    _LOGGER.info("CLSS Shade: panel registered in sidebar")
    hass.data[_DOMAIN_SETUP_DONE] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CLSS Shade from a config entry."""
    from homeassistant.const import Platform

    from .const import ClssShadeRuntimeData
    from .coordinator import ClssShadeCoordinator

    coordinator = ClssShadeCoordinator(hass, entry)

    # Download LiDAR data and build site model (first run may take a while)
    await coordinator.async_setup()

    # First data fetch (computes initial shadow map)
    await coordinator.async_config_entry_first_refresh()

    # Store runtime data
    entry.runtime_data = ClssShadeRuntimeData(coordinator=coordinator)

    # Forward to platforms
    await hass.config_entries.async_forward_entry_setups(
        entry, [Platform.SENSOR]
    )

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a CLSS Shade config entry."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)
