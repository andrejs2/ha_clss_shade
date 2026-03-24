"""CLSS Shade — Home Assistant integration for Slovenian LiDAR solar/shade analysis."""

from __future__ import annotations

DOMAIN = "ha_clss_shade"


async def async_setup_entry(hass, entry) -> bool:
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


async def async_unload_entry(hass, entry) -> bool:
    """Unload a CLSS Shade config entry."""
    from homeassistant.const import Platform

    return await hass.config_entries.async_unload_platforms(
        entry, [Platform.SENSOR]
    )


async def _async_options_updated(hass, entry) -> None:
    """Handle options update — reload the integration."""
    await hass.config_entries.async_reload(entry.entry_id)
