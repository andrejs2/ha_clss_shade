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
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, IRRIGABLE_ZONE_TYPES, ClssShadeRuntimeData
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
        key="cloud_coverage",
        translation_key="cloud_coverage",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:weather-cloudy",
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
        key="pv_power_real",
        translation_key="pv_power_real",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-panel",
    ),
    SensorEntityDescription(
        key="pv_performance_factor",
        translation_key="pv_performance_factor",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:chart-bell-curve",
    ),
    SensorEntityDescription(
        key="irrigation_need",
        translation_key="irrigation_need",
        native_unit_of_measurement=UnitOfVolume.LITERS,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:water",
    ),
    SensorEntityDescription(
        key="pv_forecast_today_kwh",
        translation_key="pv_forecast_today_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power-variant",
    ),
    SensorEntityDescription(
        key="pv_forecast_tomorrow_kwh",
        translation_key="pv_forecast_tomorrow_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power-variant-outline",
    ),
    SensorEntityDescription(
        key="pv_forecast_next_hour_w",
        translation_key="pv_forecast_next_hour_w",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:flash",
    ),
    SensorEntityDescription(
        key="pv_forecast_5day_kwh",
        translation_key="pv_forecast_5day_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:calendar-week",
    ),
    SensorEntityDescription(
        key="pv_forecast_next_1h_wh",
        translation_key="pv_forecast_next_1h_wh",
        native_unit_of_measurement="Wh",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-fast",
    ),
    SensorEntityDescription(
        key="pv_forecast_next_3h_wh",
        translation_key="pv_forecast_next_3h_wh",
        native_unit_of_measurement="Wh",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:clock-outline",
    ),
    SensorEntityDescription(
        key="pv_forecast_rest_of_today_kwh",
        translation_key="pv_forecast_rest_of_today_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:sun-clock",
    ),
)

# Zone icon mapping by zone_type
ZONE_ICONS = {
    "roof": "mdi:home-roof",
    "garden": "mdi:flower",
    "lawn": "mdi:grass",
    "vegetables": "mdi:carrot",
    "berries": "mdi:fruit-grapes",
    "fruit_trees": "mdi:tree-outline",
    "flowers": "mdi:flower-tulip",
    "greenhouse": "mdi:greenhouse",
    "trees": "mdi:tree",
    "open": "mdi:grass",
    "custom": "mdi:select-group",
    "terrace": "mdi:deck",
    "pv": "mdi:solar-panel-large",
    "parking": "mdi:parking",
    "pool": "mdi:pool",
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

    # Per-zone sensors (shade% and sun% for each zone)
    for zone_name in coordinator.zone_names:
        zone_type = coordinator.zone_type(zone_name)
        zone_icon = ZONE_ICONS.get(zone_type, ZONE_ICONS.get(zone_name, "mdi:select-group"))

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

    # 3D zone sensors (sun% for each 3D zone)
    zones_3d_config = entry.options.get("zones_3d", [])
    for z3d in zones_3d_config:
        zone_name = z3d.get("name", "")
        if not zone_name:
            continue
        entities.append(
            Clss3dZoneSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"zone3d_{zone_name}_sun",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:cube-scan",
                ),
                zone_name=zone_name,
            )
        )
        entities.append(
            Clss3dZoneSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"zone3d_{zone_name}_shade",
                    native_unit_of_measurement=PERCENTAGE,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:cube-scan",
                ),
                zone_name=zone_name,
                invert=True,
            )
        )

    # Per-zone irrigation sensors (user-defined irrigable zones only)
    _AUTO_ZONES = {"roof", "garden", "trees", "open"}
    for zone_name in coordinator.zone_names:
        if zone_name in _AUTO_ZONES:
            continue
        zone_type = coordinator.zone_type(zone_name)
        if zone_type not in IRRIGABLE_ZONE_TYPES:
            continue
        entities.append(
            ClssZoneIrrigationSensor(
                coordinator,
                entry,
                SensorEntityDescription(
                    key=f"zone_{zone_name}_irrigation",
                    native_unit_of_measurement=UnitOfVolume.LITERS,
                    state_class=SensorStateClass.MEASUREMENT,
                    icon="mdi:watering-can",
                ),
                zone_name=zone_name,
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

        if key == "pv_power_estimate":
            pv_config_str = self.coordinator.config_entry.options.get("pv_zones_config", "")
            panel_tilt = self.coordinator.config_entry.options.get("pv_panel_tilt", 30)
            panel_azimuth = self.coordinator.config_entry.options.get("pv_panel_azimuth", 180)
            attrs = {
                "pv_config": pv_config_str or "roof:5000 (privzeto)",
                "panel_tilt_deg": panel_tilt,
                "panel_azimuth_deg": panel_azimuth,
            }
            if data.weather:
                attrs["solar_radiation_wm2"] = data.weather.solar_radiation
                attrs["cloud_coverage_pct"] = data.weather.cloud_coverage
            # Per-zone details
            total_wp = 0
            for part in (pv_config_str or "roof").split(","):
                part = part.strip()
                if ":" in part:
                    zn, cap = part.split(":", 1)
                    zn = zn.strip()
                    cap_val = int(cap) if cap.strip().isdigit() else 0
                else:
                    zn = part
                    cap_val = 5000
                total_wp += cap_val
                zd = data.zones.get(zn)
                if zd:
                    attrs[f"{zn}_sun_pct"] = zd.sun_percent
                    attrs[f"{zn}_wp"] = cap_val
            attrs["total_capacity_wp"] = total_wp
            return attrs

        if key == "pv_performance_factor":
            attrs = {
                "pv_real_w": data.pv_power_real,
                "pv_estimate_w": data.pv_power_estimate,
                "factor": data.pv_performance_factor,
            }
            if data.pv_performance_factor is not None:
                pf = data.pv_performance_factor
                if pf < 0.7:
                    attrs["status"] = "nizka_ucinkovitost"
                elif pf > 1.3:
                    attrs["status"] = "ocena_prenizka"
                else:
                    attrs["status"] = "normalno"
            return attrs

        if key in ("pv_forecast_today_kwh", "pv_forecast_tomorrow_kwh"):
            fc = data.forecast
            if fc is None:
                return None
            day = fc.today if key == "pv_forecast_today_kwh" else fc.tomorrow
            if day is None:
                return None
            hourly = []
            for pt in day.hourly:
                if pt.power_w > 0 or pt.sun_elevation > 0:
                    hourly.append({
                        "time": pt.dt.isoformat(),
                        "estimate_w": round(pt.power_w, 1),
                        "cloud_factor": round(pt.cloud_factor, 2),
                        "cloud_coverage": pt.cloud_coverage,
                        "sun_elevation": round(pt.sun_elevation, 1),
                        "poa_factor": round(pt.poa_factor, 2),
                    })
            return {
                "forecast_hourly": hourly,
                "total_kwh": round(day.total_kwh, 2),
                "computed_at": day.computed_at.isoformat(),
                "performance_factor_ema": round(fc.performance_factor_ema, 3),
            }

        if key == "pv_forecast_5day_kwh":
            fc = data.forecast
            if fc is None or not fc.days:
                return None
            day_labels = ["danes", "jutri"]
            days_attr = []
            all_hourly = []
            for i, day in enumerate(fc.days):
                label = day_labels[i] if i < len(day_labels) else day.date.strftime("%a %d.%m.")
                days_attr.append({
                    "date": day.date.isoformat(),
                    "total_kwh": round(day.total_kwh, 2),
                    "label": label,
                })
                for pt in day.hourly:
                    if pt.power_w > 0 or pt.sun_elevation > 0:
                        all_hourly.append({
                            "time": pt.dt.isoformat(),
                            "estimate_w": round(pt.power_w, 1),
                            "cloud_coverage": pt.cloud_coverage,
                            "sun_elevation": round(pt.sun_elevation, 1),
                            "day_index": i,
                        })
            return {
                "days": days_attr,
                "forecast_hourly_5day": all_hourly,
                "next_1h_wh": round(fc.next_1h_wh, 0),
                "next_3h_wh": round(fc.next_3h_wh, 0),
                "rest_of_today_kwh": round(fc.rest_of_today_kwh, 2),
                "computed_at": fc.days[0].computed_at.isoformat(),
                "performance_factor_ema": round(fc.performance_factor_ema, 3),
            }

        if key == "irrigation_need" and data.weather:
            # Show which garden area is used for irrigation
            garden_info = self.coordinator._get_irrigation_garden(data.zones)
            attrs = {
                "evapotranspiration_mm": data.weather.evapotranspiration,
                "water_balance_mm": data.weather.water_balance,
                "vir_podatkov": data.weather.agro_source or "ni podatkov",
                "garden_shade_percent": garden_info[0] if garden_info else None,
                "garden_area_m2": garden_info[1] if garden_info else None,
            }
            # Add multi-day agrometeo forecast
            for day in data.weather.agro_days:
                if day.evapotranspiracija_mm is not None:
                    prefix = day.datum or "?"
                    attrs[f"{prefix}_etp_mm"] = day.evapotranspiracija_mm
                    if day.vodna_bilanca_mm is not None:
                        attrs[f"{prefix}_bilanca_mm"] = day.vodna_bilanca_mm
                    if day.padavine_24h_mm is not None:
                        attrs[f"{prefix}_padavine_mm"] = day.padavine_24h_mm
                    attrs[f"{prefix}_tip"] = day.tip
            return attrs

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


class Clss3dZoneSensor(CoordinatorEntity[ClssShadeCoordinator], SensorEntity):
    """3D zone sensor — sun/shade percent from 3D ray tracing."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        zone_name: str,
        invert: bool = False,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_name = zone_name
        self._invert = invert
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GURS / ARSO",
            model="CLSS LiDAR Shade Analysis",
            entry_type=DeviceEntryType.SERVICE,
        )
        kind = "shade percent" if invert else "sun percent"
        self._attr_name = f"{zone_name.capitalize()} 3D {kind}"

    @property
    def native_value(self) -> float | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        sun_pct = data.zones_3d.get(self._zone_name)
        if sun_pct is None:
            return None
        return round(100.0 - sun_pct, 1) if self._invert else sun_pct


class ClssZoneIrrigationSensor(CoordinatorEntity[ClssShadeCoordinator], SensorEntity):
    """Per-zone irrigation sensor with 5-day forecast."""

    has_entity_name = True

    def __init__(
        self,
        coordinator: ClssShadeCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
        zone_name: str,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._zone_name = zone_name
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer="GURS / ARSO",
            model="CLSS LiDAR Shade Analysis",
            entry_type=DeviceEntryType.SERVICE,
        )
        self._attr_name = f"{zone_name.replace('_', ' ').capitalize()} irrigation need"

    @property
    def native_value(self) -> float | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        forecast = data.zone_irrigation.get(self._zone_name)
        if forecast is None:
            return None
        return forecast.today_liters

    @property
    def extra_state_attributes(self) -> dict | None:
        data: ClssShadeData | None = self.coordinator.data
        if data is None:
            return None
        forecast = data.zone_irrigation.get(self._zone_name)
        if forecast is None:
            return None
        throughput = self.coordinator.zone_throughput(self._zone_name)
        duration_min = None
        if throughput and throughput > 0 and forecast.today_liters > 0:
            duration_min = round(forecast.today_liters / throughput, 1)

        attrs: dict = {
            "crop_kc": forecast.crop_kc,
            "zone_type": forecast.zone_type,
            "area_m2": forecast.area_m2,
            "today_need_mm": forecast.today_need_mm,
            "correction_factor": forecast.correction_factor,
            "throughput_lpm": throughput,
            "duration_minutes": duration_min,
        }
        # 5-day forecast breakdown
        daily = []
        for day in forecast.forecast_daily:
            daily.append({
                "date": day.date,
                "need_mm": day.need_mm,
                "need_liters": day.need_liters,
                "etp_mm": day.etp_mm,
                "precipitation_mm": day.precipitation_mm,
                "water_balance_mm": day.water_balance_mm,
                "shade_percent": day.shade_percent,
                "seasonal_factor": day.seasonal_factor,
                "tip": day.tip,
            })
        attrs["forecast_daily"] = daily
        return attrs
