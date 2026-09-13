"""Test entity platforms: climate, sensor, binary_sensor, button, number, switch."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from joule_ble import CookState, ErrorState, JouleState
from custom_components.joule.climate import JouleClimate
from custom_components.joule.sensor import JouleSensor, JouleCookFinishTimeSensor, SENSOR_DESCRIPTIONS
from custom_components.joule.binary_sensor import JouleBinarySensor, BINARY_SENSOR_DESCRIPTIONS
from custom_components.joule.button import JouleFoodAddedButton, JouleIdentifyButton, JouleClearErrorButton
from custom_components.joule.number import JouleCookTimeNumber
from custom_components.joule.switch import JouleAutoStartTimerSwitch
from custom_components.joule.coordinator import JouleDataUpdateCoordinator


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
    coord, entry, hass, mock_client = test_setup
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
    assert climate.hvac_mode == "off"

    # Turn on starts cooking
    await climate.async_turn_on()
    mock_client.start_cook.assert_called_once()


def test_sensor_entities(test_setup):
    """Test telemetry sensors report correct values from state."""
    coord, entry, hass, mock_client = test_setup

    sensors = {desc.key: JouleSensor(coord, entry, desc) for desc in SENSOR_DESCRIPTIONS}

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


def test_binary_sensors(test_setup):
    """Test binary sensors."""
    coord, entry, hass, mock_client = test_setup

    bin_sensors = {desc.key: JouleBinarySensor(coord, entry, desc) for desc in BINARY_SENSOR_DESCRIPTIONS}

    assert bin_sensors["low_water"].is_on is False
    assert bin_sensors["motor_fault"].is_on is False
    assert bin_sensors["heating"].is_on is False

    coord.data.low_water = True
    coord.data.program_step = CookState.PRE_HEATING
    assert bin_sensors["low_water"].is_on is True
    assert bin_sensors["heating"].is_on is True


@pytest.mark.asyncio
async def test_buttons(test_setup):
    """Test button entities and availability."""
    coord, entry, hass, mock_client = test_setup

    food_btn = JouleFoodAddedButton(coord, entry)
    identify_btn = JouleIdentifyButton(coord, entry)
    clear_btn = JouleClearErrorButton(coord, entry)

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


@pytest.mark.asyncio
async def test_number_and_switch(test_setup):
    """Test cook time number and auto start switch."""
    coord, entry, hass, mock_client = test_setup

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
