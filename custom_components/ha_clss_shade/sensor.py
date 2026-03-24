"""Sensor entities for CLSS Shade integration."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    DEGREE,
    PERCENTAGE,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ClssShadeRuntimeData
from .coordinator import ClssShadeCoordinator, ClssShadeData

_LOGGER = logging.getLogger(__name__)

# Global sensors (always created)
GLOBAL_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="shade_percent",
        translation_key="shade_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-partly-cloudy",
    ),
    SensorEntityDescription(
        key="sun_percent",
        translation_key="sun_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-sunny",
    ),
    SensorEntityDescription(
        key="sun_elevation",
        translation_key="sun_elevation",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:angle-acute",
    ),
    SensorEntityDescription(
        key="sun_azimuth",
        translation_key="sun_azimuth",
        native_unit_of_measurement=DEGREE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:compass",
    ),
    SensorEntityDescription(
        key="is_day",
        translation_key="is_day",
        icon="mdi:white-balance-sunny",
    ),
    SensorEntityDescription(
        key="pv_power_estimate",
        translation_key="pv_power_estimate",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
    ),
    SensorEntityDescription(
        key="irrigation_need",
        translation_key="irrigation_need",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
)

# Zone icon mapping
ZONE_ICONS = {
    "roof": "mdi:home-roof",
    "garden": "mdi:flower",
    "trees": "mdi:tree",
    "open": "mdi:grass",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CLSS Shade sensors from a config entry."""
    runtime_data: ClssShadeRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    entities: list[SensorEntity] = []

    # Global sensors
    for description in GLOBAL_SENSORS:
        entities.append(ClssShadeSensor(coordinator, entry, description))

    # Per-zone sensors (shade% and sun% for each auto-detected zone)
    for zone_name in coordinator.zone_names:
        zone_icon = ZONE_ICONS.get(zone_name, "mdi:select-group")

        entities.append(
            ClssZoneSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"zone_{zone_name}_shade",
                    translation_key=f"zone_{zone_name}_shade",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon=zone_icon,
                ),
                zone_name=zone_name,
                value_key="shade_percent",
            )
        )
        entities.append(
            ClssZoneSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"zone_{zone_name}_sun",
                    translation_key=f"zone_{zone_name}_sun",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:weather-sunny",
                ),
                zone_name=zone_name,
                value_key="sun_percent",
            )
        )

    async_add_entities(entities)


class ClssShadeSensor(CoordinatorEntity[ClssShadeCoordinator], SensorEntity):
    """Global sensor entity for CLSS Shade data."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GURS / ARSO",
            model="CLSS LiDAR Shade Analysis",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def native_value(self) -> float | bool | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        return getattr(data, self.entity_description.key, None)

    @property
    def extra_state_attributes(self) -> dict | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None

        key = self.entity_description.key
        if key == "shade_percent":
            attrs = {
                "sun_azimuth": data.sun_azimuth,
                "sun_elevation": data.sun_elevation,
                "latitude": self.coordinator.latitude,
                "longitude": self.coordinator.longitude,
            }
            # Add zone summary
            for zname, zdata in data.zones.items():
                attrs[f"zone_{zname}_shade"] = zdata.shade_percent
            return attrs

        if key == "pv_power_estimate" and data.weather:
            return {
                "solar_radiation_wm2": data.weather.solar_radiation,
                "roof_sun_percent": data.zones.get("roof", None)
                and data.zones["roof"].sun_percent,
            }

        if key == "irrigation_need" and data.weather:
            return {
                "evapotranspiration_mm": data.weather.evapotranspiration,
                "water_balance_mm": data.weather.water_balance,
                "garden_shade_percent": data.zones.get("garden", None)
                and data.zones["garden"].shade_percent,
            }

        return None


class ClssZoneSensor(CoordinatorEntity[ClssShadeCoordinator], SensorEntity):
    """Per-zone sensor entity."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        zone_name: str,
        value_key: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_name = zone_name
        self._value_key = value_key
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GURS / ARSO",
            model="CLSS LiDAR Shade Analysis",
            entry_type=DeviceEntryType.SERVICE,
        )
        # Dynamic name since translation keys for zones are dynamic
        self._attr_name = f"{zone_name.capitalize()} {value_key.replace('_', ' ')}"

    @property
    def native_value(self) -> float | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        zone = data.zones.get(self._zone_name)
        if zone is None:
            return None
        return getattr(zone, self._value_key, None)

    @property
    def extra_state_attributes(self) -> dict | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        zone = data.zones.get(self._zone_name)
        if zone is None:
            return None
        return {
            "zone_type": self._zone_name,
            "area_m2": zone.area_m2,
            "cell_count": zone.cell_count,
        }
