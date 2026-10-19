"""Test entity platforms: climate, sensor, binary_sensor, button, number, switch."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from joule_ble import CookState

from custom_components.joule.binary_sensor import (
    BINARY_SENSOR_DESCRIPTIONS,
    JouleBinarySensor,
)
from custom_components.joule.button import (
    JouleClearErrorButton,
    JouleFoodAddedButton,
    JouleIdentifyButton,
    JoulePairButton,
)
from custom_components.joule.climate import JouleClimate
from custom_components.joule.coordinator import JouleDataUpdateCoordinator
from custom_components.joule.number import JouleCookTimeNumber
from custom_components.joule.sensor import (
    BREVILLE_TURBO_SENSOR_DESCRIPTIONS,
    COMMON_SENSOR_DESCRIPTIONS,
    SENSOR_DESCRIPTIONS,
    JouleCookFinishTimeSensor,
    JouleSensor,
)
from custom_components.joule.sensor import (
    async_setup_entry as async_setup_sensor_entry,
)
from custom_components.joule.switch import JouleAutoStartTimerSwitch


@pytest.fixture
def test_setup(mock_joule_client):
    """Fixture providing coordinator and mock entry."""
    hass = MagicMock()
    hass.config_entries.async_update_entry = MagicMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {
        "address": "AA:BB:CC:DD:EE:FF",
        "name": "Kitchen Joule",
        "model": "Original Joule",
        "firmware_version": "1.2.3",
        "hardware_version": "1.0",
    }
    entry.options = {"auto_start_timer": False}

    ble_device = MagicMock()
    coord = JouleDataUpdateCoordinator(hass, entry, mock_joule_client, ble_device)
    coord.data = mock_joule_client.state
    return coord, entry, hass, mock_joule_client


@pytest.mark.asyncio
async def test_climate_entity(test_setup):
    """Test climate entity behaviors."""
    coord, entry, _hass, mock_client = test_setup
    climate = JouleClimate(coord, entry)

    # Status when cooking
    assert climate.hvac_mode == "heat"
    assert climate.current_temperature == 55.0
    assert climate.target_temperature == 55.0

    # Set temperature
    await climate.async_set_temperature(temperature=58.5)
    mock_client.set_temperature.assert_called_once_with(58.5)

    # Turn off
    await climate.async_turn_off()
    mock_client.stop_cook.assert_called_once()

    # Status when idle
    coord.data.program_step = CookState.IDLE
    coord.data.target_temp_c = None
    assert climate.hvac_mode == "off"

    # Setting temperature when idle adjusts target_temperature without starting cook
    mock_client.start_cook.reset_mock()
    await climate.async_set_temperature(temperature=52.0)
    assert climate.target_temperature == 52.0
    mock_client.start_cook.assert_not_called()

    # Turn on starts cooking with dialed setpoint
    await climate.async_turn_on()
    mock_client.start_cook.assert_called_once_with(
        target_temp_c=52.0,
        cook_time_seconds=3600,
        delayed_start_seconds=0,
        holding_temp_c=0.0,
    )

    # Calling async_set_hvac_mode(heat) when already cooking does not double-call start_cook
    coord.data.program_step = CookState.PRE_HEATING
    mock_client.start_cook.reset_mock()
    await climate.async_set_hvac_mode("heat")
    mock_client.start_cook.assert_not_called()

    # Turning off when in error state calls stop_cook cleanly
    coord.data.program_step = CookState.ERROR
    mock_client.stop_cook.reset_mock()
    await climate.async_turn_off()
    mock_client.stop_cook.assert_called_once()


def test_sensor_entities(test_setup):
    """Test telemetry sensors report correct values from state."""
    coord, entry, _hass, _mock_client = test_setup

    sensors = {
        desc.key: JouleSensor(coord, entry, desc) for desc in SENSOR_DESCRIPTIONS
    }

    assert sensors["bath_temp"].native_value == 55.0
    assert sensors["cook_status"].native_value == "cooking"
    assert sensors["time_remaining"].native_value == 1800
    assert sensors["heater_temp"].native_value == 60.0
    assert sensors["upper_board_temp"].native_value == 35.0
    assert sensors["lower_board_temp"].native_value == 34.0
    assert sensors["motor_rpm"].native_value == 1800
    assert sensors["heater_power"].native_value == 45.0
    assert sensors["error_severity"].native_value == "no_error"
    assert sensors["turbo_cook_state"].native_value == "no_turbo"

    # Finish time sensor
    finish_sensor = JouleCookFinishTimeSensor(coord, entry)
    val = finish_sensor.native_value
    assert isinstance(val, datetime)


@pytest.mark.asyncio
async def test_sensor_platform_setup_chefsteps(test_setup):
    """Test ChefSteps device excludes turbo_cook_state and purges orphaned registry entry."""
    coord, entry, hass, mock_client = test_setup
    mock_client.is_breville_profile = False
    entry.data = {**entry.data, "model": "Original Joule"}

    hass.data = {"joule": {entry.entry_id: coord}}

    mock_ent_reg = MagicMock()
    mock_ent_reg.async_get_entity_id.return_value = "sensor.kitchen_joule_turbo_mode"

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    from unittest.mock import patch

    with patch(
        "homeassistant.helpers.entity_registry.async_get", return_value=mock_ent_reg
    ):
        await async_setup_sensor_entry(hass, entry, mock_add_entities)

    # Must call async_remove on the orphaned entity
    mock_ent_reg.async_get_entity_id.assert_called_once_with(
        "sensor", "joule", f"{entry.data['address']}_turbo_cook_state"
    )
    mock_ent_reg.async_remove.assert_called_once_with("sensor.kitchen_joule_turbo_mode")

    # turbo_cook_state must NOT be added
    keys = [
        getattr(e, "entity_description", None) and e.entity_description.key
        for e in added_entities
    ]
    assert "turbo_cook_state" not in keys
    assert "bath_temp" in keys
    assert (
        len(added_entities) == len(COMMON_SENSOR_DESCRIPTIONS) + 1
    )  # common + finish_time


@pytest.mark.asyncio
async def test_sensor_platform_setup_breville(test_setup):
    """Test Breville Joule Turbo includes turbo_cook_state."""
    coord, entry, hass, mock_client = test_setup
    mock_client.is_breville_profile = True
    entry.data = {**entry.data, "model": "Joule Turbo"}

    hass.data = {"joule": {entry.entry_id: coord}}

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_sensor_entry(hass, entry, mock_add_entities)

    keys = [
        getattr(e, "entity_description", None) and e.entity_description.key
        for e in added_entities
    ]
    assert "turbo_cook_state" in keys
    assert "bath_temp" in keys
    assert (
        len(added_entities)
        == len(COMMON_SENSOR_DESCRIPTIONS) + len(BREVILLE_TURBO_SENSOR_DESCRIPTIONS) + 1
    )


def test_binary_sensors(test_setup):
    """Test binary sensors."""
    coord, entry, _hass, _mock_client = test_setup

    bin_sensors = {
        desc.key: JouleBinarySensor(coord, entry, desc)
        for desc in BINARY_SENSOR_DESCRIPTIONS
    }

    assert bin_sensors["low_water"].is_on is False
    assert bin_sensors["motor_fault"].is_on is False
    assert bin_sensors["heating"].is_on is True  # Active during COOKING

    coord.data.program_step = CookState.IDLE
    assert bin_sensors["heating"].is_on is False

    coord.data.low_water = True
    coord.data.program_step = CookState.PRE_HEATING
    assert bin_sensors["low_water"].is_on is True
    assert bin_sensors["heating"].is_on is True


@pytest.mark.asyncio
async def test_buttons(test_setup):
    """Test button entities and availability."""
    coord, entry, _hass, mock_client = test_setup

    food_btn = JouleFoodAddedButton(coord, entry)
    identify_btn = JouleIdentifyButton(coord, entry)
    clear_btn = JouleClearErrorButton(coord, entry)
    pair_btn = JoulePairButton(coord, entry)

    # Food button only available in WAITING_FOR_FOOD
    assert food_btn.available is False
    coord.data.program_step = CookState.WAITING_FOR_FOOD
    assert food_btn.available is True

    await food_btn.async_press()
    mock_client.drop_food.assert_called_once()

    await identify_btn.async_press()
    mock_client.identify.assert_called_once()

    await clear_btn.async_press()
    mock_client.clear_errors.assert_called_once()

    mock_client.start_key_exchange = AsyncMock(
        return_value=MagicMock(secret_key=b"1234")
    )
    await pair_btn.async_press()
    mock_client.start_key_exchange.assert_called_once()


@pytest.mark.asyncio
async def test_number_and_switch(test_setup):
    """Test cook time number and auto start switch."""
    coord, entry, hass, _mock_client = test_setup

    num = JouleCookTimeNumber(coord, entry)
    assert num.native_value == 60.0

    await num.async_set_native_value(90.0)
    assert coord.target_cook_time_minutes == 90

    sw = JouleAutoStartTimerSwitch(coord, entry)
    assert sw.is_on is False

    await sw.async_turn_on()
    assert coord.auto_start_timer is True
    assert hass.config_entries.async_update_entry.called

    await sw.async_turn_off()
    assert coord.auto_start_timer is False
