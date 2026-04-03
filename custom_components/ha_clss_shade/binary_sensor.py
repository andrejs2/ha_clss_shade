"""Binary sensor entities for CLSS Shade — recommended watering per zone."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IRRIGABLE_ZONE_TYPES, ClssShadeRuntimeData
from .coordinator import ClssShadeCoordinator, ClssShadeData

_LOGGER = logging.getLogger(__name__)

# Threshold: recommend watering when daily need exceeds 0.5 mm
_RECOMMEND_THRESHOLD_MM = 0.5


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up recommended watering binary sensors."""
    runtime_data: ClssShadeRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    entities: list[BinarySensorEntity] = []

    _AUTO_ZONES = {"roof", "garden", "trees", "open"}
    for zone_name in coordinator.zone_names:
        if zone_name in _AUTO_ZONES:
            continue
        zone_type = coordinator.zone_type(zone_name)
        if zone_type not in IRRIGABLE_ZONE_TYPES:
            continue
        entities.append(
            ClssRecommendedWateringSensor(coordinator, entry, zone_name)
        )

    async_add_entities(entities)


class ClssRecommendedWateringSensor(
    CoordinatorEntity[ClssShadeCoordinator], BinarySensorEntity
):
    """Binary sensor — ON when watering is recommended for a zone."""

    has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.MOISTURE

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator)
        self._zone_name = zone_name
        self._attr_unique_id = (
            f"{entry.entry_id}_zone_{zone_name}_recommended_watering"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GURS / ARSO",
            model="CLSS LiDAR Shade Analysis",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_name = (
            f"{zone_name.replace('_', ' ').capitalize()} recommended watering"
        )

    @property
    def is_on(self) -> bool | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        forecast = data.zone_irrigation.get(self._zone_name)
        if forecast is None:
            return None
        return forecast.today_need_mm > _RECOMMEND_THRESHOLD_MM

    @property
    def extra_state_attributes(self) -> dict | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        forecast = data.zone_irrigation.get(self._zone_name)
        if forecast is None:
            return None
        return {
            "need_liters": forecast.today_liters,
            "need_mm": forecast.today_need_mm,
            "crop_kc": forecast.crop_kc,
            "zone_type": forecast.zone_type,
        }
