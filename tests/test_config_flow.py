"""Test JouleConfigFlow and JouleOptionsFlowHandler."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from joule_ble import (
    JouleAuthData,
    JouleDeviceInfo,
    JouleModel,
    JouleTimeoutError,
)

from custom_components.joule.config_flow import JouleConfigFlow, JouleOptionsFlowHandler


@pytest.mark.asyncio
async def test_config_flow_pair_form_initial_render():
    """Test async_step_pair presents user with pair instructions when user_input is None."""
    flow = JouleConfigFlow()
    flow._name = "DagusJoule"
    flow._discovery_info = MagicMock()
    flow._discovery_info.address = "CD:F6:E0:B4:F7:5D"

    result = await flow.async_step_pair(user_input=None)
    assert result["type"] == "form"
    assert result["step_id"] == "pair"
    assert result["description_placeholders"] == {"name": "DagusJoule"}


@pytest.mark.asyncio
async def test_config_flow_pair_timeout():
    """Test async_step_pair handles JouleTimeoutError by showing retryable pairing_timeout error."""
    flow = JouleConfigFlow()
    flow._name = "DagusJoule"
    discovery_info = MagicMock()
    discovery_info.address = "CD:F6:E0:B4:F7:5D"
    discovery_info.name = "DagusJoule"
    discovery_info.device = MagicMock()
    discovery_info.service_data = {}
    discovery_info.manufacturer_data = {}
    flow._discovery_info = discovery_info

    with patch("custom_components.joule.config_flow.JouleClient") as mock_client_cls:
        client_instance = mock_client_cls.return_value
        client_instance.connect = AsyncMock()
        client_instance.disconnect = AsyncMock()
        client_instance.identify = AsyncMock(
            return_value=JouleDeviceInfo(model=JouleModel.ORIGINAL_JOULE)
        )
        client_instance.start_key_exchange = AsyncMock(
            side_effect=JouleTimeoutError("Key exchange timed out")
        )

        result = await flow.async_step_pair(user_input={})

        assert result["type"] == "form"
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": "pairing_timeout"}
        assert client_instance.start_key_exchange.called
        assert client_instance.disconnect.called


@pytest.mark.asyncio
async def test_config_flow_pair_success():
    """Test async_step_pair succeeds, acquires auth key, and creates entry."""
    flow = JouleConfigFlow()
    flow._name = "DagusJoule"
    discovery_info = MagicMock()
    discovery_info.address = "CD:F6:E0:B4:F7:5D"
    discovery_info.name = "DagusJoule"
    discovery_info.device = MagicMock()
    discovery_info.service_data = {}
    discovery_info.manufacturer_data = {345: b"\x00\x01\x02\x03\x04\x05\x06\x07\x08"}
    flow._discovery_info = discovery_info

    secret_key = bytes.fromhex("1122334455667788")
    auth_data = JouleAuthData(secret_key=secret_key)
    dev_info = JouleDeviceInfo(
        name="DagusJoule",
        serial_number="180705383",
        hardware_version="J7",
        model=JouleModel.ORIGINAL_JOULE,
        recipient_address=b"\x01\x02\x03\x04\x05\x06\x07\x08",
    )

    with patch("custom_components.joule.config_flow.JouleClient") as mock_client_cls:
        client_instance = mock_client_cls.return_value
        client_instance.connect = AsyncMock()
        client_instance.disconnect = AsyncMock()
        client_instance.identify = AsyncMock(return_value=dev_info)
        client_instance.start_key_exchange = AsyncMock(return_value=auth_data)
        client_instance.device_info = dev_info

        result = await flow.async_step_pair(user_input={})

        assert result["type"] == "create_entry"
        assert result["title"] == "DagusJoule"
        assert result["data"]["address"] == "CD:F6:E0:B4:F7:5D"
        assert result["data"]["auth_key"] == "1122334455667788"
        assert result["data"]["hardware_version"] == "J7"
        assert result["data"]["serial_number"] == "180705383"
        assert client_instance.disconnect.called


@pytest.mark.asyncio
async def test_options_flow_handler():
    """Test JouleOptionsFlowHandler doesn't crash on read-only config_entry property."""
    from homeassistant.config_entries import ConfigEntry

    entry = ConfigEntry(options={"auto_start_timer": True, "idle_timeout": 600})
    handler = JouleOptionsFlowHandler(entry)
    result = await handler.async_step_init(user_input=None)

    assert result["type"] == "form"
    assert result["step_id"] == "init"
