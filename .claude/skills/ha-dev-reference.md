---
name: ha-dev
description: Reference for Home Assistant custom integration development and HACS publishing. Use when implementing HA integration components (config_flow, coordinator, sensor, __init__, manifest).
user_invocable: true
---

# Home Assistant Custom Integration Development Reference

You are helping build a HACS-compatible Home Assistant custom integration. Use this reference when implementing integration components.

## Required Files

| File | Purpose |
|------|---------|
| `manifest.json` | Integration identity: domain, version, requirements, iot_class |
| `__init__.py` | Entry point: `async_setup_entry()` / `async_unload_entry()` |
| `config_flow.py` | UI configuration: `ConfigFlow` + `OptionsFlow` |
| `const.py` | Constants, DOMAIN, runtime data dataclass |
| `coordinator.py` | `DataUpdateCoordinator` subclass for data polling |
| `sensor.py` | `SensorEntity` platform with `CoordinatorEntity` base |
| `strings.json` | English UI strings |
| `translations/<lang>.json` | Translated UI strings |

## Key Patterns

### manifest.json (required fields for HACS)
```json
{
  "domain": "my_integration",
  "name": "Display Name",
  "version": "1.0.0",
  "documentation": "https://github.com/user/repo",
  "issue_tracker": "https://github.com/user/repo/issues",
  "codeowners": ["@username"],
  "dependencies": [],
  "requirements": ["package>=1.0"],
  "iot_class": "calculated",
  "config_flow": true
}
```

### __init__.py pattern
```python
from __future__ import annotations
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = MyCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

### ConfigFlow pattern
```python
from homeassistant import config_entries
import voluptuous as vol

class MyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # validate input
            await self.async_set_unique_id(user_input["name"])
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input["name"], data=user_input)
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({...}),
            errors=errors,
        )
```

### DataUpdateCoordinator pattern
```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from datetime import timedelta

class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=timedelta(minutes=5))
        self.entry = entry

    async def _async_update_data(self):
        try:
            # fetch data
            return data
        except Exception as err:
            raise UpdateFailed(f"Error: {err}") from err
```

### SensorEntity pattern
```python
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MySensor(CoordinatorEntity, SensorEntity):
    has_entity_name = True

    def __init__(self, coordinator, description):
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(...)

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)
```

### SensorEntityDescription
```python
SENSORS = [
    SensorEntityDescription(
        key="shade_percent",
        name="Shade",
        native_unit_of_measurement="%",
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
]
```

## HACS Requirements

### Repository root
- `hacs.json` with `name`, `homeassistant` (min version), `render_readme`, `country`
- `README.md` with HACS install badge
- `LICENSE`
- `.github/workflows/validate.yaml` — HACS validation action
- `.github/workflows/hassfest.yaml` — HA hassfest validation

### Publishing checklist
1. Public repo with description and topics set
2. Issues enabled
3. Both CI workflows passing
4. At least one GitHub Release (not just a tag)
5. Submit PR to `hacs/default` repo, `integration` file, alphabetically sorted

## Best Practices
- `from __future__ import annotations` in every file
- `_LOGGER = logging.getLogger(__name__)` in every module
- `CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)` in `__init__.py`
- API client code in separate sub-package (no HA imports)
- Use `hass.async_add_executor_job()` for blocking calls
- Stable `unique_id` values (never IP addresses)
- Use `entry.runtime_data` pattern (HA 2024.4.0+), not `hass.data[DOMAIN]`

## Reference docs
- HA Developer Docs: https://developers.home-assistant.io/docs/development_index/
- HACS Publish: https://www.hacs.xyz/docs/publish/integration/
- Local research: docs/ha-custom-integration-reference.md
