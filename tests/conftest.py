"""Pytest fixtures and Home Assistant stubs for ha-joule tests."""

from __future__ import annotations

from enum import Enum, StrEnum
from pathlib import Path
import sys
from types import ModuleType
from typing import Any, Generic, TypeVar
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure ha-joule and joule-ble are on sys.path
HA_JOULE_ROOT = str(Path(__file__).parent.parent)
JOULE_BLE_SRC = "/Users/arcsur/src/joule-ble/src"
if HA_JOULE_ROOT not in sys.path:
    sys.path.insert(0, HA_JOULE_ROOT)
if JOULE_BLE_SRC not in sys.path:
    sys.path.insert(0, JOULE_BLE_SRC)

_T = TypeVar("_T")


def _setup_stubs() -> None:
    """Register lightweight Home Assistant and voluptuous stubs in sys.modules."""
    if "voluptuous" not in sys.modules:
        vol = ModuleType("voluptuous")
        class Schema:
            def __init__(self, *args, **kwargs):
                pass
            def extend(self, *args, **kwargs):
                return self
            def __call__(self, val):
                return val
        vol.Schema = Schema
        vol.Required = lambda *args, **kwargs: args[0] if args else None
        vol.Optional = lambda *args, **kwargs: args[0] if args else None
        vol.In = lambda *args: args
        vol.All = lambda *args: args
        vol.Coerce = lambda *args: args
        vol.Range = lambda *args, **kwargs: args
        sys.modules["voluptuous"] = vol

    if "homeassistant" in sys.modules:
        return

    # Base package
    ha = ModuleType("homeassistant")
    sys.modules["homeassistant"] = ha

    # homeassistant.const
    ha_const = ModuleType("homeassistant.const")

    class Platform(StrEnum):
        CLIMATE = "climate"
        SENSOR = "sensor"
        BINARY_SENSOR = "binary_sensor"
        BUTTON = "button"
        NUMBER = "number"
        SWITCH = "switch"

    class UnitOfTemperature(StrEnum):
        CELSIUS = "°C"
        FAHRENHEIT = "°F"

    class UnitOfTime(StrEnum):
        SECONDS = "s"
        MINUTES = "min"
        HOURS = "h"

    class EntityCategory(StrEnum):
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"

    ha_const.Platform = Platform
    ha_const.CONF_ADDRESS = "address"
    ha_const.CONF_DEVICE_ID = "device_id"
    ha_const.CONF_DOMAIN = "domain"
    ha_const.CONF_PLATFORM = "platform"
    ha_const.CONF_TYPE = "type"
    ha_const.ATTR_TEMPERATURE = "temperature"
    ha_const.ATTR_DEVICE_ID = "device_id"
    ha_const.ATTR_ENTITY_ID = "entity_id"
    ha_const.PERCENTAGE = "%"
    ha_const.REVOLUTIONS_PER_MINUTE = "rpm"
    ha_const.UnitOfTemperature = UnitOfTemperature
    ha_const.UnitOfTime = UnitOfTime
    ha_const.EntityCategory = EntityCategory
    sys.modules["homeassistant.const"] = ha_const

    # homeassistant.core
    ha_core = ModuleType("homeassistant.core")
    ha_core.HomeAssistant = MagicMock
    ha_core.ServiceCall = MagicMock
    ha_core.CALLBACK_TYPE = Any
    ha_core.callback = lambda f: f
    sys.modules["homeassistant.core"] = ha_core

    # homeassistant.exceptions
    ha_exc = ModuleType("homeassistant.exceptions")
    class ConfigEntryNotReady(Exception):
        pass
    class HomeAssistantError(Exception):
        pass
    ha_exc.ConfigEntryNotReady = ConfigEntryNotReady
    ha_exc.HomeAssistantError = HomeAssistantError
    sys.modules["homeassistant.exceptions"] = ha_exc

    # homeassistant.config_entries
    ha_ce = ModuleType("homeassistant.config_entries")
    class ConfigEntry:
        pass
    class ConfigFlow:
        pass
    class OptionsFlow:
        pass
    ha_ce.ConfigEntry = ConfigEntry
    ha_ce.ConfigFlow = ConfigFlow
    ha_ce.OptionsFlow = OptionsFlow
    sys.modules["homeassistant.config_entries"] = ha_ce

    # homeassistant.data_entry_flow
    ha_def = ModuleType("homeassistant.data_entry_flow")
    ha_def.FlowResult = dict
    sys.modules["homeassistant.data_entry_flow"] = ha_def

    # homeassistant.components
    ha_comp = ModuleType("homeassistant.components")
    sys.modules["homeassistant.components"] = ha_comp

    # homeassistant.components.device_automation
    ha_da = ModuleType("homeassistant.components.device_automation")
    ha_da.DEVICE_TRIGGER_BASE_SCHEMA = sys.modules["voluptuous"].Schema({})
    sys.modules["homeassistant.components.device_automation"] = ha_da

    # homeassistant.components.homeassistant
    ha_ha = ModuleType("homeassistant.components.homeassistant")
    ha_hat = ModuleType("homeassistant.components.homeassistant.triggers")
    ha_hate = ModuleType("homeassistant.components.homeassistant.triggers.event")
    ha_hate.CONF_PLATFORM = "platform"
    ha_hate.CONF_EVENT_TYPE = "event_type"
    ha_hate.CONF_EVENT_DATA = "event_data"
    ha_hate.TRIGGER_SCHEMA = lambda x: x
    ha_hate.async_attach_trigger = AsyncMock(return_value=lambda: None)
    ha_hat.event = ha_hate
    ha_ha.triggers = ha_hat
    sys.modules["homeassistant.components.homeassistant"] = ha_ha
    sys.modules["homeassistant.components.homeassistant.triggers"] = ha_hat
    sys.modules["homeassistant.components.homeassistant.triggers.event"] = ha_hate

    # homeassistant.components.bluetooth
    ha_bt = ModuleType("homeassistant.components.bluetooth")
    class BluetoothChange(Enum):
        ADVERTISEMENT = 1
    class BluetoothScanningMode(Enum):
        ACTIVE = 1
        PASSIVE = 2
    ha_bt.BluetoothChange = BluetoothChange
    ha_bt.BluetoothScanningMode = BluetoothScanningMode
    ha_bt.BluetoothServiceInfoBleak = MagicMock
    ha_bt.async_register_callback = MagicMock(return_value=lambda: None)
    ha_bt.async_ble_device_from_address = MagicMock(return_value=None)
    ha_bt.async_discovered_service_info = MagicMock(return_value=[])
    ha_comp.bluetooth = ha_bt
    sys.modules["homeassistant.components.bluetooth"] = ha_bt

    # homeassistant.helpers
    ha_helpers = ModuleType("homeassistant.helpers")
    sys.modules["homeassistant.helpers"] = ha_helpers

    # homeassistant.helpers.update_coordinator
    ha_uc = ModuleType("homeassistant.helpers.update_coordinator")
    class DataUpdateCoordinator(Generic[_T]):
        def __init__(self, hass, logger, *, name, update_interval=None, update_method=None):
            self.hass = hass
            self.logger = logger
            self.name = name
            self.data = None
            self.listeners = []
        def async_set_updated_data(self, data):
            self.data = data
            for listener in list(self.listeners):
                listener()
    class CoordinatorEntity(Generic[_T]):
        def __init__(self, coordinator):
            self.coordinator = coordinator
    class UpdateFailed(Exception):
        pass
    ha_uc.DataUpdateCoordinator = DataUpdateCoordinator
    ha_uc.CoordinatorEntity = CoordinatorEntity
    ha_uc.UpdateFailed = UpdateFailed
    sys.modules["homeassistant.helpers.update_coordinator"] = ha_uc

    # homeassistant.helpers.event
    ha_event = ModuleType("homeassistant.helpers.event")
    ha_event.async_call_later = MagicMock(return_value=lambda: None)
    sys.modules["homeassistant.helpers.event"] = ha_event

    # homeassistant.helpers.entity
    ha_entity = ModuleType("homeassistant.helpers.entity")
    class DeviceInfo(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)
    ha_entity.DeviceInfo = DeviceInfo
    sys.modules["homeassistant.helpers.entity"] = ha_entity

    # homeassistant.helpers.entity_platform
    ha_ep = ModuleType("homeassistant.helpers.entity_platform")
    ha_ep.AddEntitiesCallback = MagicMock
    sys.modules["homeassistant.helpers.entity_platform"] = ha_ep

    # homeassistant.helpers.device_registry
    ha_dr = ModuleType("homeassistant.helpers.device_registry")
    ha_dr.async_get = MagicMock()
    sys.modules["homeassistant.helpers.device_registry"] = ha_dr

    # homeassistant.helpers.trigger
    ha_trig = ModuleType("homeassistant.helpers.trigger")
    ha_trig.TriggerActionType = Any
    ha_trig.TriggerInfo = Any
    sys.modules["homeassistant.helpers.trigger"] = ha_trig

    # homeassistant.helpers.typing
    ha_type = ModuleType("homeassistant.helpers.typing")
    ha_type.ConfigType = dict
    sys.modules["homeassistant.helpers.typing"] = ha_type

    # homeassistant.util
    ha_util = ModuleType("homeassistant.util")
    sys.modules["homeassistant.util"] = ha_util
    import datetime
    ha_dt = ModuleType("homeassistant.util.dt")
    ha_dt.utcnow = lambda: datetime.datetime.now(datetime.timezone.utc)
    ha_util.dt = ha_dt
    sys.modules["homeassistant.util.dt"] = ha_dt

    # Components: climate, sensor, binary_sensor, button, number, switch
    ha_clim = ModuleType("homeassistant.components.climate")
    class ClimateEntity:
        pass
    class ClimateEntityFeature:
        TARGET_TEMPERATURE = 1
        TURN_ON = 2
        TURN_OFF = 4
    class HVACMode(StrEnum):
        OFF = "off"
        HEAT = "heat"
    class HVACAction(StrEnum):
        OFF = "off"
        HEATING = "heating"
        IDLE = "idle"
    ha_clim.ClimateEntity = ClimateEntity
    ha_clim.ClimateEntityFeature = ClimateEntityFeature
    ha_clim.HVACMode = HVACMode
    ha_clim.HVACAction = HVACAction
    sys.modules["homeassistant.components.climate"] = ha_clim

    ha_sens = ModuleType("homeassistant.components.sensor")
    class SensorEntity:
        pass
    class SensorDeviceClass(StrEnum):
        TEMPERATURE = "temperature"
        ENUM = "enum"
        DURATION = "duration"
        TIMESTAMP = "timestamp"
    class SensorStateClass(StrEnum):
        MEASUREMENT = "measurement"
    class SensorEntityDescription:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    ha_sens.SensorEntity = SensorEntity
    ha_sens.SensorDeviceClass = SensorDeviceClass
    ha_sens.SensorStateClass = SensorStateClass
    ha_sens.SensorEntityDescription = SensorEntityDescription
    sys.modules["homeassistant.components.sensor"] = ha_sens

    ha_bs = ModuleType("homeassistant.components.binary_sensor")
    class BinarySensorEntity:
        pass
    class BinarySensorDeviceClass(StrEnum):
        PROBLEM = "problem"
        RUNNING = "running"
    class BinarySensorEntityDescription:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    ha_bs.BinarySensorEntity = BinarySensorEntity
    ha_bs.BinarySensorDeviceClass = BinarySensorDeviceClass
    ha_bs.BinarySensorEntityDescription = BinarySensorEntityDescription
    sys.modules["homeassistant.components.binary_sensor"] = ha_bs

    ha_btn = ModuleType("homeassistant.components.button")
    class ButtonEntity:
        pass
    class ButtonDeviceClass(StrEnum):
        IDENTIFY = "identify"
    class ButtonEntityDescription:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)
    ha_btn.ButtonEntity = ButtonEntity
    ha_btn.ButtonDeviceClass = ButtonDeviceClass
    ha_btn.ButtonEntityDescription = ButtonEntityDescription
    sys.modules["homeassistant.components.button"] = ha_btn

    ha_num = ModuleType("homeassistant.components.number")
    class NumberEntity:
        pass
    class NumberMode(StrEnum):
        BOX = "box"
        SLIDER = "slider"
    ha_num.NumberEntity = NumberEntity
    ha_num.NumberMode = NumberMode
    sys.modules["homeassistant.components.number"] = ha_num

    ha_sw = ModuleType("homeassistant.components.switch")
    class SwitchEntity:
        pass
    ha_sw.SwitchEntity = SwitchEntity
    sys.modules["homeassistant.components.switch"] = ha_sw


_setup_stubs()

from joule_ble import CookState, ErrorState, JouleClient, JouleModel, JouleState


@pytest.fixture
def mock_joule_client():
    """Create a configured mock JouleClient."""
    client = MagicMock(spec=JouleClient)
    client.is_connected = True
    client._callbacks = []

    state = JouleState(
        connected=True,
        bath_temp_c=55.0,
        target_temp_c=55.0,
        heater_temp_c=60.0,
        upper_board_temp_c=35.0,
        lower_board_temp_c=34.0,
        motor_rpm=1800,
        heater_pwm=0.45,
        time_remaining_seconds=1800,
        cook_time_seconds=3600,
        program_step=CookState.COOKING,
        error_state=ErrorState.NO_ERROR,
        low_water=False,
        motor_fault=False,
    )
    client.state = state

    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.start_cook = AsyncMock()
    client.set_temperature = AsyncMock()
    client.stop_cook = AsyncMock()
    client.drop_food = AsyncMock()
    client.clear_errors = AsyncMock()
    client.identify = AsyncMock()

    def register_callback(cb):
        client._callbacks.append(cb)
        return lambda: client._callbacks.remove(cb) if cb in client._callbacks else None

    client.register_callback.side_effect = register_callback
    return client
