"""Config flow for CLSS Shade integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from .const import (
    CONF_INCLUDE_NEIGHBORS,
    CONF_RADIUS,
    DEFAULT_RADIUS_M,
    DOMAIN,
)
from .clss_data.geo import is_in_slovenia

_LOGGER = logging.getLogger(__name__)


class ClssShadeConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for CLSS Shade."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step — location and radius."""
        errors: dict[str, str] = {}

        if user_input is not None:
            lat = user_input[CONF_LATITUDE]
            lon = user_input[CONF_LONGITUDE]

            if not is_in_slovenia(lat, lon):
                errors["base"] = "invalid_location"
            else:
                name = user_input.get(CONF_NAME, f"CLSS {lat:.4f},{lon:.4f}")
                await self.async_set_unique_id(f"{lat:.4f}_{lon:.4f}")
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_LATITUDE: lat,
                        CONF_LONGITUDE: lon,
                    },
                    options={
                        CONF_RADIUS: user_input.get(CONF_RADIUS, DEFAULT_RADIUS_M),
                        CONF_INCLUDE_NEIGHBORS: user_input.get(
                            CONF_INCLUDE_NEIGHBORS, False
                        ),
                    },
                )

        # Pre-fill with HA home location
        suggested_lat = self.hass.config.latitude
        suggested_lon = self.hass.config.longitude

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default="Home"
                    ): str,
                    vol.Required(
                        CONF_LATITUDE, default=suggested_lat
                    ): vol.Coerce(float),
                    vol.Required(
                        CONF_LONGITUDE, default=suggested_lon
                    ): vol.Coerce(float),
                    vol.Optional(
                        CONF_RADIUS, default=DEFAULT_RADIUS_M
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=50, max=1000)
                    ),
                    vol.Optional(
                        CONF_INCLUDE_NEIGHBORS, default=False
                    ): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> ClssShadeOptionsFlow:
        """Get the options flow handler."""
        return ClssShadeOptionsFlow(config_entry)


class ClssShadeOptionsFlow(config_entries.OptionsFlow):
    """Handle options for CLSS Shade."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self._config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_RADIUS,
                        default=current.get(CONF_RADIUS, DEFAULT_RADIUS_M),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=50, max=1000)
                    ),
                    vol.Optional(
                        CONF_INCLUDE_NEIGHBORS,
                        default=current.get(CONF_INCLUDE_NEIGHBORS, False),
                    ): bool,
                }
            ),
        )
