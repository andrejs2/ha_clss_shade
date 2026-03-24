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
from homeassistant.const import DEGREE, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, ClssShadeRuntimeData
from .coordinator import ClssShadeCoordinator, ClssShadeData

_LOGGER = logging.getLogger(__name__)

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
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
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up CLSS Shade sensors from a config entry."""
    runtime_data: ClssShadeRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    entities = [
        ClssShadeSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(entities)


class ClssShadeSensor(CoordinatorEntity[ClssShadeCoordinator], SensorEntity):
    """Sensor entity for CLSS Shade data."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
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
        """Return the sensor value."""
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None

        key = self.entity_description.key
        return getattr(data, key, None)

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return extra attributes for shade/sun sensors."""
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None

        key = self.entity_description.key
        if key == "shade_percent":
            return {
                "sun_azimuth": data.sun_azimuth,
                "sun_elevation": data.sun_elevation,
                "latitude": self.coordinator.latitude,
                "longitude": self.coordinator.longitude,
            }
        return None
