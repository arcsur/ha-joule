"""Test coordinator commands call underlying JouleClient properly."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from custom_components.joule.coordinator import JouleDataUpdateCoordinator


@pytest.mark.asyncio
async def test_coordinator_commands(mock_joule_client):
    """Verify start_cook, set_temperature, stop_cook, drop_food, clear_errors, identify."""
    hass = MagicMock()
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {"address": "AA:BB:CC:DD:EE:FF"}
    entry.options = {}

    ble_device = MagicMock()
    coord = JouleDataUpdateCoordinator(hass, entry, mock_joule_client, ble_device)

    with patch("homeassistant.components.bluetooth.async_ble_device_from_address", return_value=ble_device):
        # start_cook
        await coord.async_start_cook(target_temp_c=58.0, cook_time_minutes=45)
        mock_joule_client.start_cook.assert_called_once_with(
            target_temp_c=58.0,
            cook_time_seconds=2700,
            delayed_start_seconds=0,
            holding_temp_c=0.0,
        )

        # set_temperature
        await coord.async_set_temperature(60.0)
        mock_joule_client.set_temperature.assert_called_once_with(60.0)

        # drop_food
        await coord.async_drop_food()
        mock_joule_client.drop_food.assert_called_once()

        # stop_cook
        await coord.async_stop_cook()
        mock_joule_client.stop_cook.assert_called_once()

        # clear_errors
        await coord.async_clear_errors()
        mock_joule_client.clear_errors.assert_called_once()

        # identify
        await coord.async_identify()
        mock_joule_client.identify.assert_called_once()
