# Home Assistant Custom Integration Reference

Research sourced from the official Home Assistant developer documentation at
https://developers.home-assistant.io (fetched 2026-03-24).

---

## 1. Required Files and Directory Structure

An integration lives in `custom_components/<domain>/` and requires these files:

| File | Purpose |
|------|---------|
| `manifest.json` | Integration metadata, dependencies, discovery info |
| `__init__.py` | Entry point: `async_setup_entry()` / `async_unload_entry()` |
| `config_flow.py` | UI-based configuration wizard |
| `const.py` | Shared constants (`DOMAIN`, config keys, defaults) |
| `strings.json` | User-facing strings for config flow, errors, abort reasons |
| `sensor.py` (etc.) | Platform files, one per entity domain (sensor, switch, light...) |
| `coordinator.py` | DataUpdateCoordinator subclass (convention, not enforced) |
| `icons.json` | Icon definitions per entity/state (preferred over hardcoded icons) |

The scaffold tool generates this structure: `python3 -m script.scaffold integration`

### File Naming Conventions

- The directory name **must** match the `domain` field in `manifest.json`.
- Domain must be a short name of characters and underscores only.
- Platform files are named after the entity domain they implement (`sensor.py`, `binary_sensor.py`, `switch.py`, `light.py`, `climate.py`, etc.).
- Constants go in `const.py`; do not duplicate constants from `homeassistant.const`.

---

## 2. manifest.json Fields and Requirements

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `domain` | `str` | Unique identifier; must match directory name; cannot change after publication |
| `name` | `str` | Display name. Append "Cloud" for cloud variants; never append "Local" |
| `codeowners` | `list[str]` | GitHub usernames/teams responsible for maintenance |
| `dependencies` | `list[str]` | Integrations that must load before this one |
| `documentation` | `str` | URL to docs (core: `https://www.home-assistant.io/integrations/<domain>`) |
| `integration_type` | `str` | One of: `device`, `entity`, `hardware`, `helper`, `hub`, `service`, `system`, `virtual` |
| `iot_class` | `str` | One of: `assumed_state`, `cloud_polling`, `cloud_push`, `local_polling`, `local_push`, `calculated` |
| `requirements` | `list[str]` | Pip-compatible packages, e.g. `["pychromecast==3.2.0"]`. Pin exact versions. |

### Key Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | `str` | **Required for custom integrations**, omit for core. SemVer or CalVer. |
| `config_flow` | `bool` | Set `true` if integration has a config flow; requires `config_flow.py` |
| `single_config_entry` | `bool` | Limit to one config entry per integration |
| `after_dependencies` | `list[str]` | Non-essential integrations that load first if present |
| `loggers` | `list[str]` | Logger names used by third-party libraries |
| `quality_scale` | `str` | `bronze`, `silver`, `gold`, or `platinum` |
| `issue_tracker` | `str` | Bug report URL (omit for core; auto-generated) |

### Discovery Fields (all optional arrays)

`bluetooth`, `zeroconf`, `ssdp`, `homekit`, `mqtt`, `dhcp`, `usb` -- each with
matcher-specific sub-fields for automatic device discovery.

### Example

```json
{
  "domain": "my_device",
  "name": "My Device",
  "codeowners": ["@myhandle"],
  "config_flow": true,
  "dependencies": [],
  "documentation": "https://github.com/myhandle/ha-my-device",
  "integration_type": "device",
  "iot_class": "local_polling",
  "requirements": ["my-device-lib==1.2.3"],
  "version": "1.0.0"
}
```

---

## 3. Config Flow Implementation Pattern

The config flow provides the UI-based setup wizard. The manifest must have
`"config_flow": true`. All code in `config_flow.py` requires full test coverage
for core acceptance.

### Class Structure

```python
from homeassistant import config_entries
from .const import DOMAIN

class MyDeviceConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1          # Major version -- bump triggers migration
    MINOR_VERSION = 1    # Minor version -- backwards-compatible changes
```

### Reserved Step Names

| Step | Trigger |
|------|---------|
| `user` | Manual UI setup |
| `discovery` (dhcp/zeroconf/ssdp/usb/homekit/bluetooth/mqtt/hassio) | Auto-detection |
| `reauth` | Authentication failure |
| `reconfigure` | User edits existing entry |
| `import` | YAML migration |

### Basic User Step with Error Handling

```python
async def async_step_user(self, user_input=None):
    errors = {}
    if user_input is not None:
        try:
            await validate_input(user_input)
            return self.async_create_entry(title="My Device", data=user_input)
        except ConnectionError:
            errors["base"] = "cannot_connect"
        except InvalidAuth:
            errors["base"] = "invalid_auth"
        except Exception:
            errors["base"] = "unknown"

    return self.async_show_form(
        step_id="user",
        data_schema=vol.Schema({
            vol.Required("host"): str,
            vol.Required("password"): str,
        }),
        errors=errors,
    )
```

### Unique ID and Duplicate Prevention

```python
await self.async_set_unique_id(device_serial_number)
self._abort_if_unique_id_configured()
# Optionally update existing entry's connection details:
self._abort_if_unique_id_configured(updates={CONF_HOST: new_host})
```

Valid unique ID sources: serial numbers, formatted MAC addresses, device identifiers.
**Never use**: IP addresses, user-changeable hostnames, device names.

### Reauthentication Flow

Triggered from `__init__.py` when auth fails:
```python
raise ConfigEntryAuthFailed("Token expired")
```
The flow handler implements `async_step_reauth` and `async_step_reauth_confirm`.

### Reconfiguration Flow

```python
async def async_step_reconfigure(self, user_input=None):
    if user_input is not None:
        return self.async_update_reload_and_abort(
            self._get_reconfigure_entry(), data_updates=user_input
        )
    return self.async_show_form(step_id="reconfigure", data_schema=...)
```

### Options Flow

For settings that can change after setup (polling interval, etc.):
```python
class MyDeviceOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        return self.async_show_form(step_id="init", data_schema=...)
```

### strings.json Structure

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Connect to Device",
        "data": { "host": "Host", "password": "Password" }
      }
    },
    "error": {
      "cannot_connect": "Failed to connect",
      "invalid_auth": "Invalid credentials",
      "unknown": "Unexpected error"
    },
    "abort": {
      "already_configured": "Device is already configured"
    }
  }
}
```

### Version Migration

When `VERSION` changes, implement in `__init__.py`:
```python
async def async_migrate_entry(hass, config_entry):
    if config_entry.version > 2:
        return False   # Future version, cannot downgrade
    if config_entry.version == 1:
        new_data = {**config_entry.data, "new_field": "default"}
        hass.config_entries.async_update_entry(config_entry, data=new_data, version=2)
    return True
```

---

## 4. DataUpdateCoordinator Pattern

The recommended approach for polling integrations. One coordinator polls a single
endpoint; all entities subscribe to its updates.

### Subclass Pattern (coordinator.py)

```python
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed

class MyCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, config_entry, api_client):
        super().__init__(
            hass,
            logger,
            name="my_device",
            config_entry=config_entry,
            update_interval=timedelta(seconds=30),
            always_update=True,  # False if data supports __eq__
        )
        self.api = api_client

    async def _async_setup(self):
        """One-time setup during first refresh (optional)."""
        await self.api.initialize()

    async def _async_update_data(self):
        """Fetch data from API."""
        try:
            async with async_timeout.timeout(10):
                return await self.api.fetch_data()
        except AuthError as err:
            raise ConfigEntryAuthFailed from err      # triggers reauth flow
        except ApiError as err:
            raise UpdateFailed(f"Error: {err}") from err  # retries next interval
```

### Error Handling

| Exception | Effect |
|-----------|--------|
| `UpdateFailed` | Marks entities unavailable; retries at next interval. Supports `retry_after`. |
| `ConfigEntryAuthFailed` | Cancels all future updates; triggers reauth flow. |
| `asyncio.TimeoutError`, `aiohttp.ClientError` | Handled automatically by the coordinator. |

### Initialization in __init__.py

```python
async def async_setup_entry(hass, entry):
    coordinator = MyCoordinator(hass, entry, api_client)
    await coordinator.async_config_entry_first_refresh()  # raises ConfigEntryNotReady on failure
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
```

### Entity Subscription via CoordinatorEntity

```python
from homeassistant.helpers.update_coordinator import CoordinatorEntity

class MySensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, idx):
        super().__init__(coordinator, context=idx)  # context filters updates

    @callback
    def _handle_coordinator_update(self):
        self._attr_native_value = self.coordinator.data[self.idx]["value"]
        self.async_write_ha_state()
```

`CoordinatorEntity` automatically provides: `should_poll=False`, `async_update`,
`async_added_to_hass`, `available` (False when last update failed).

### Push-Based Alternative

For push APIs, omit `update_interval`. Push new data manually:
```python
coordinator.async_set_updated_data(new_data)
```

---

## 5. Sensor Entity Implementation

### Class Hierarchy

Inherit from `SensorEntity` (or `RestoreSensor` to persist state across restarts).
Combine with `CoordinatorEntity` for coordinator-based updates.

### Core Properties

| Property | Type | Description |
|----------|------|-------------|
| `native_value` | `str\|int\|float\|date\|datetime\|Decimal` | The sensor's current value in its native unit |
| `native_unit_of_measurement` | `str\|None` | Unit of the value (auto-converts for temperature, pressure, etc.) |
| `device_class` | `SensorDeviceClass\|None` | Categorizes sensor for specialized display and unit conversion |
| `state_class` | `SensorStateClass\|None` | Determines statistics tracking; makes numeric sensors show as line charts |
| `suggested_display_precision` | `int\|None` | Decimal places for display |
| `last_reset` | `datetime\|None` | When accumulating sensors reset (for TOTAL state class) |
| `options` | `list[str]\|None` | For ENUM device class: list of valid discrete states |

### State Classes

| Value | Use Case | Statistics |
|-------|----------|------------|
| `MEASUREMENT` | Current readings (temp, humidity, power) | Hourly min/max/mean |
| `TOTAL` | Accumulating bidirectional values (net energy) | Sum of increases/decreases |
| `TOTAL_INCREASING` | Monotonic counters that reset to zero (gas/water meters) | Auto-detects resets; tolerates <10% decrease |
| `MEASUREMENT_ANGLE` | Degree-based angles (wind direction) | Angle-specific statistics |

### Device Classes (partial list of 80+)

- **Environmental**: TEMPERATURE, HUMIDITY, ATMOSPHERIC_PRESSURE, ILLUMINANCE
- **Air Quality**: CO2, CO, PM25, PM10, AQI, VOLATILE_ORGANIC_COMPOUNDS
- **Energy/Power**: ENERGY, POWER, VOLTAGE, CURRENT, POWER_FACTOR
- **Other**: BATTERY (%), MONETARY, ENUM, TIMESTAMP, DURATION, DISTANCE, SPEED, WEIGHT

### EntityDescription Pattern (recommended for multiple sensors)

```python
@dataclass(kw_only=True)
class MyDeviceSensorDescription(SensorEntityDescription):
    value_fn: Callable[[DeviceData], StateType]

SENSORS: tuple[MyDeviceSensorDescription, ...] = (
    MyDeviceSensorDescription(
        key="temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.temperature,
    ),
    MyDeviceSensorDescription(
        key="battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.battery_level,
    ),
)
```

### Platform Setup (sensor.py)

```python
async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    async_add_entities(
        MyDeviceSensor(coordinator, description)
        for description in SENSORS
    )
```

### Implementation Rules

- Properties must return only in-memory data -- never perform I/O in properties.
- Use `_attr_*` class/instance attributes or `@property` methods.
- Create additional sensor entities instead of stuffing data into `extra_state_attributes`.
- Set `has_entity_name = True` (mandatory for new integrations).
- Name should describe the data point only, not the device (e.g. "Temperature" not "Living Room Sensor Temperature").

---

## 6. Entity Naming and Device Registration

### has_entity_name = True (mandatory for new integrations)

- Named entity on a device: `friendly_name = "{device_name} {entity_name}"`
- Unnamed entity (main feature): `friendly_name = "{device_name}"`
- Entity name = `None` for the device's primary feature.
- Names: capital first letter, lowercase remainder. Use `translation_key` instead of hardcoded English.

### unique_id

- Must be unique within a platform (e.g., all sensors).
- Must be stable across updates -- never change it.
- Common pattern: `f"{device_serial}_{description.key}"`
- Never user-configurable.

### device_info

```python
_attr_device_info = DeviceInfo(
    identifiers={(DOMAIN, device.serial)},
    name="My Device",
    manufacturer="ACME",
    model="Widget 3000",
    sw_version=device.firmware,
)
```

Entities with `unique_id` + `device_info` are automatically registered to the device.

---

## 7. Best Practices and Common Pitfalls

### From the Code Review Checklist

1. **Dependencies**: All requirements in `manifest.json` with pinned versions from PyPI. Never use GitHub URLs.
2. **API code belongs in a third-party library** on PyPI, not in the integration. The integration calls library objects; it does not make raw HTTP/API calls.
3. **Configuration validation**: Use voluptuous schemas. Define defaults in schemas, not in `setup_platform()`.
4. **Do not pass `hass` to entity constructors** -- it is available as `self.hass` after registration.
5. **Do not call `update()` in constructors** -- use `add_entities(entities, update_before_add=True)`.
6. **No I/O in properties** -- fetch and cache data in `update()` / `_async_update_data()`.
7. **Use UTC timestamps** in state and attributes, never relative times.
8. **Use constants from `homeassistant.const`** before defining your own.
9. **Register custom services under your domain**: `my_domain.my_action`, not under a platform domain.
10. **Consolidate `async_add_entities` calls** -- call it once with all entities, not in a loop.
11. **Use entity lifecycle hooks** (`async_added_to_hass`, `async_will_remove_from_hass`) for subscribing/unsubscribing.
12. **Prefer icon translations** in `icons.json` over hardcoded `_attr_icon`.

### Common Pitfalls

- **Forgetting `version` in manifest.json** for custom integrations (it is required).
- **Mutable unique IDs**: Using IP addresses or hostnames that change.
- **Missing error handling in config flow**: Every path must either show a form with errors, create an entry, or abort.
- **Not raising `ConfigEntryNotReady`**: If the device is unreachable at setup, raise this so HA retries.
- **Not implementing `async_unload_entry`**: Required for clean reload/removal; must undo everything `async_setup_entry` did.
- **Blocking I/O on the event loop**: Use `hass.async_add_executor_job()` for synchronous library calls.
- **Polling too aggressively**: Choose a reasonable `update_interval` (30s-60s for most devices).
- **Not using `CoordinatorEntity`**: Rolling your own polling when the coordinator pattern handles availability, error retry, and deduplication automatically.

---

## 8. Complete __init__.py Pattern

```python
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from .coordinator import MyCoordinator

PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass, entry: ConfigEntry) -> bool:
    api = MyApiClient(entry.data["host"], entry.data["password"])
    coordinator = MyCoordinator(hass, entry, api)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry: ConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
```

---

## Sources

- https://developers.home-assistant.io/docs/development_index/
- https://developers.home-assistant.io/docs/creating_integration_manifest/
- https://developers.home-assistant.io/docs/config_entries_config_flow_handler/
- https://developers.home-assistant.io/docs/integration_fetching_data/
- https://developers.home-assistant.io/docs/core/entity/sensor/
- https://developers.home-assistant.io/docs/creating_platform_code_review/
- https://developers.home-assistant.io/docs/creating_component_index/
- https://developers.home-assistant.io/docs/config_entries_index/
- https://developers.home-assistant.io/docs/core/entity/
