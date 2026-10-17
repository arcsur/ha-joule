"""Test JouleDataUpdateCoordinator state change and event firing logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from joule_ble import CookState, JouleState
from custom_components.joule.const import (
    EVENT_COOK_COMPLETED,
    EVENT_LOW_WATER,
    EVENT_WATER_AT_TEMPERATURE,
)
from custom_components.joule.coordinator import JouleDataUpdateCoordinator


@pytest.mark.asyncio
async def test_coordinator_events_and_auto_start(mock_joule_client):
    """Test coordinator fires events when transitioning state and triggers auto_start."""
    hass = MagicMock()
    hass.bus.async_fire = MagicMock()
    hass.async_create_task = MagicMock()

    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {"auto_start_timer": True, "idle_timeout": 300}

    ble_device = MagicMock()
    ble_device.address = "AA:BB:CC:DD:EE:FF"

    coord = JouleDataUpdateCoordinator(hass, entry, mock_joule_client, ble_device)
    assert coord.auto_start_timer is True

    # 1. Simulate transition from PRE_HEATING to WAITING_FOR_FOOD
    coord._previous_step = CookState.PRE_HEATING
    new_state = JouleState(
        connected=True,
        bath_temp_c=56.0,
        target_temp_c=56.0,
        program_step=CookState.WAITING_FOR_FOOD,
    )
    coord._handle_client_update(new_state)

    # Verify EVENT_WATER_AT_TEMPERATURE was fired
    hass.bus.async_fire.assert_any_call(
        EVENT_WATER_AT_TEMPERATURE,
        {
            "device_id": "test_entry_id",
            "address": "AA:BB:CC:DD:EE:FF",
            "target_temp_c": 56.0,
            "bath_temp_c": 56.0,
        },
    )
    # Verify auto-start task was scheduled
    assert hass.async_create_task.called

    # 2. Simulate transition from COOKING to WAITING_FOR_REMOVE_FOOD
    coord._previous_step = CookState.COOKING
    done_state = JouleState(
        connected=True,
        bath_temp_c=56.0,
        program_step=CookState.WAITING_FOR_REMOVE_FOOD,
    )
    coord._handle_client_update(done_state)

    hass.bus.async_fire.assert_any_call(
        EVENT_COOK_COMPLETED,
        {
            "device_id": "test_entry_id",
            "address": "AA:BB:CC:DD:EE:FF",
            "bath_temp_c": 56.0,
        },
    )

    # 3. Simulate Low Water fault
    fault_state = JouleState(
        connected=True,
        program_step=CookState.COOKING,
        low_water=True,
    )
    coord._previous_low_water = False
    coord._handle_client_update(fault_state)

    hass.bus.async_fire.assert_any_call(
        EVENT_LOW_WATER,
        {
            "device_id": "test_entry_id",
            "address": "AA:BB:CC:DD:EE:FF",
        },
    )


@pytest.mark.asyncio
async def test_coordinator_persistent_notification_and_dismissal(mock_joule_client):
    """Test coordinator creates persistent notification on error and clears on dismissal."""
    from homeassistant.components import persistent_notification
    from homeassistant.const import EVENT_CALL_SERVICE

    persistent_notification.async_create.reset_mock()
    persistent_notification.async_dismiss.reset_mock()

    hass = MagicMock()
    listeners = {}

    def async_listen(event, callback):
        listeners[event] = callback
        return lambda: listeners.pop(event, None)

    hass.bus.async_listen.side_effect = async_listen
    hass.async_create_task.side_effect = lambda coro: asyncio.create_task(coro)

    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF", "name": "DagusJoule"}
    entry.options = {}

    ble_device = MagicMock()
    ble_device.address = "AA:BB:CC:DD:EE:FF"

    coord = JouleDataUpdateCoordinator(hass, entry, mock_joule_client, ble_device)
    await coord.async_setup()

    # Trigger error
    error_state = JouleState(
        connected=True,
        program_step=CookState.ERROR,
        low_water=True,
    )
    coord._handle_client_update(error_state)

    # Verify notification created
    persistent_notification.async_create.assert_called_once()
    notif_id = coord._notification_id

    # Simulate user dismissing the notification in HA frontend
    dismiss_event = MagicMock()
    dismiss_event.data = {
        "domain": "persistent_notification",
        "service": "dismiss",
        "service_data": {"notification_id": notif_id},
    }
    listeners[EVENT_CALL_SERVICE](dismiss_event)
    await asyncio.sleep(0.05)

    # Verify clear_errors was called on client
    mock_joule_client.clear_errors.assert_called_once()

