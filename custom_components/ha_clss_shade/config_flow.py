"""Config flow for CLSS Shade integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME

from .const import (
    CONF_CUSTOM_ZONES,
    CONF_INCLUDE_NEIGHBORS,
    CONF_PV_CAPACITY_WP,
    CONF_PV_ZONE,
    CONF_RADIUS,
    DEFAULT_PV_CAPACITY_WP,
    DEFAULT_RADIUS_M,
    DOMAIN,
)
from .clss_data.geo import is_in_slovenia

_LOGGER = logging.getLogger(__name__)

ZONE_TYPES = {
    "custom": "Custom",
    "garden": "Garden / Vrt",
    "terrace": "Terrace / Terasa",
    "pv": "PV Panels / Sončne celice",
    "parking": "Parking / Parkirišče",
    "pool": "Pool / Bazen",
}

ZONE_SHAPES = {
    "polygon": "Polygon / Poligon",
    "circle": "Circle / Krog",
}


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
                        CONF_CUSTOM_ZONES: [],
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
        self._options: dict = {}

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage options — general settings and zone management."""
        if user_input is not None:
            action = user_input.pop("zone_action", "done")

            # Preserve current custom zones
            self._options = {
                CONF_RADIUS: user_input.get(CONF_RADIUS, DEFAULT_RADIUS_M),
                CONF_INCLUDE_NEIGHBORS: user_input.get(CONF_INCLUDE_NEIGHBORS, False),
                CONF_PV_CAPACITY_WP: user_input.get(CONF_PV_CAPACITY_WP, DEFAULT_PV_CAPACITY_WP),
                CONF_PV_ZONE: user_input.get(CONF_PV_ZONE, "roof"),
                CONF_CUSTOM_ZONES: list(
                    self._config_entry.options.get(CONF_CUSTOM_ZONES, [])
                ),
            }

            if action == "add_zone":
                return await self.async_step_add_zone()
            if action == "remove_zone":
                return await self.async_step_remove_zone()
            return self.async_create_entry(title="", data=self._options)

        current = self._config_entry.options
        custom_zones = current.get(CONF_CUSTOM_ZONES, [])

        # Build zone action choices
        zone_actions: dict[str, str] = {"done": "Save / Shrani"}
        zone_actions["add_zone"] = "Add zone / Dodaj cono"
        if custom_zones:
            zone_names = ", ".join(z["name"] for z in custom_zones)
            zone_actions["remove_zone"] = f"Remove zone / Odstrani ({zone_names})"

        description_placeholders = {}
        if custom_zones:
            lines = []
            for z in custom_zones:
                shape = z.get("shape", "circle")
                if shape == "polygon":
                    lines.append(
                        f"  • {z['name']} ({z['zone_type']}, poligon): "
                        f"{len(z.get('vertices', []))} oglišč"
                    )
                else:
                    lines.append(
                        f"  • {z['name']} ({z['zone_type']}, krog): "
                        f"E{z.get('offset_e', 0):+.0f}m N{z.get('offset_n', 0):+.0f}m "
                        f"r={z.get('radius', 10)}m"
                    )
            description_placeholders["custom_zones"] = "\n".join(lines)
        else:
            description_placeholders["custom_zones"] = "  (none)"

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
                    vol.Optional(
                        CONF_PV_CAPACITY_WP,
                        default=current.get(CONF_PV_CAPACITY_WP, DEFAULT_PV_CAPACITY_WP),
                    ): vol.All(
                        vol.Coerce(int), vol.Range(min=0, max=100000)
                    ),
                    vol.Optional(
                        CONF_PV_ZONE,
                        default=current.get(CONF_PV_ZONE, "roof"),
                    ): str,
                    vol.Required("zone_action", default="done"): vol.In(zone_actions),
                }
            ),
            description_placeholders=description_placeholders,
        )

    async def async_step_add_zone(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Choose zone shape."""
        if user_input is not None:
            self._zone_shape = user_input["zone_shape"]
            self._zone_name = user_input["zone_name"].strip().lower().replace(" ", "_")
            self._zone_type = user_input["zone_type"]

            # Validate name
            existing = {z["name"] for z in self._options.get(CONF_CUSTOM_ZONES, [])}
            auto_names = {"roof", "garden", "trees", "open"}
            if self._zone_name in existing or self._zone_name in auto_names:
                return self.async_show_form(
                    step_id="add_zone",
                    data_schema=self._add_zone_schema(),
                    errors={"zone_name": "zone_name_exists"},
                )
            if not self._zone_name:
                return self.async_show_form(
                    step_id="add_zone",
                    data_schema=self._add_zone_schema(),
                    errors={"zone_name": "zone_name_empty"},
                )

            if self._zone_shape == "polygon":
                return await self.async_step_add_polygon()
            return await self.async_step_add_circle()

        return self.async_show_form(
            step_id="add_zone",
            data_schema=self._add_zone_schema(),
        )

    def _add_zone_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required("zone_name"): str,
                vol.Required("zone_type", default="custom"): vol.In(ZONE_TYPES),
                vol.Required("zone_shape", default="polygon"): vol.In(ZONE_SHAPES),
            }
        )

    async def async_step_add_polygon(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a polygon zone — enter vertices."""
        errors: dict[str, str] = {}

        if user_input is not None:
            from .zones import parse_vertices

            try:
                vertices = parse_vertices(user_input["vertices"])
            except ValueError as err:
                _LOGGER.debug("Invalid vertices: %s", err)
                errors["vertices"] = "invalid_vertices"
            else:
                zone = {
                    "name": self._zone_name,
                    "zone_type": self._zone_type,
                    "shape": "polygon",
                    "vertices": [[e, n] for e, n in vertices],
                }
                zones = list(self._options.get(CONF_CUSTOM_ZONES, []))
                zones.append(zone)
                self._options[CONF_CUSTOM_ZONES] = zones
                return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="add_polygon",
            data_schema=vol.Schema(
                {
                    vol.Required("vertices"): str,
                }
            ),
            description_placeholders={
                "zone_name": self._zone_name,
            },
            errors=errors,
        )

    async def async_step_add_circle(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a circular zone."""
        errors: dict[str, str] = {}

        if user_input is not None:
            zone = {
                "name": self._zone_name,
                "zone_type": self._zone_type,
                "shape": "circle",
                "offset_e": round(user_input["offset_east"], 1),
                "offset_n": round(user_input["offset_north"], 1),
                "radius": round(user_input["zone_radius"], 1),
            }
            zones = list(self._options.get(CONF_CUSTOM_ZONES, []))
            zones.append(zone)
            self._options[CONF_CUSTOM_ZONES] = zones
            return self.async_create_entry(title="", data=self._options)

        return self.async_show_form(
            step_id="add_circle",
            data_schema=vol.Schema(
                {
                    vol.Required("offset_east", default=0.0): vol.Coerce(float),
                    vol.Required("offset_north", default=0.0): vol.Coerce(float),
                    vol.Required("zone_radius", default=10.0): vol.All(
                        vol.Coerce(float), vol.Range(min=1, max=200)
                    ),
                }
            ),
            description_placeholders={
                "zone_name": self._zone_name,
            },
            errors=errors,
        )

    async def async_step_remove_zone(
        self, user_input: dict | None = None
    ) -> config_entries.ConfigFlowResult:
        """Remove a custom zone."""
        if user_input is not None:
            to_remove = user_input["zone_to_remove"]
            zones = [
                z
                for z in self._options.get(CONF_CUSTOM_ZONES, [])
                if z["name"] != to_remove
            ]
            self._options[CONF_CUSTOM_ZONES] = zones
            return self.async_create_entry(title="", data=self._options)

        custom_zones = self._options.get(CONF_CUSTOM_ZONES, [])
        zone_names = {z["name"]: z["name"] for z in custom_zones}

        return self.async_show_form(
            step_id="remove_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone_to_remove"): vol.In(zone_names),
                }
            ),
        )
