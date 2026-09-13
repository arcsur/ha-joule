"""Config flow for ChefSteps / Breville Joule integration."""

from __future__ import annotations

import logging
from typing import Any

from bleak.backends.device import BLEDevice
from homeassistant import config_entries
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from joule_ble import (
    JouleAuthenticationError,
    JouleClient,
    JouleConnectionError,
    JouleError,
    JouleModel,
)

from .const import (
    CONF_AUTO_START_TIMER,
    CONF_IDLE_TIMEOUT,
    DEFAULT_AUTO_START_TIMER,
    DEFAULT_IDLE_TIMEOUT,
    DEFAULT_NAME,
    DOMAIN,
    UUID_BREVILLE_SERVICE,
    UUID_CHEFSTEP_STREAM_SERVICE,
)

_LOGGER = logging.getLogger(__name__)


class JouleConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Joule."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize flow."""
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_devices: dict[str, BluetoothServiceInfoBleak] = {}
        self._client: JouleClient | None = None
        self._name: str = DEFAULT_NAME

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> FlowResult:
        """Handle Bluetooth discovery."""
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()

        self._discovery_info = discovery_info
        self._name = discovery_info.name or DEFAULT_NAME

        self.context["title_placeholders"] = {"name": self._name}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm discovery before pairing."""
        if user_input is not None:
            return await self.async_step_pair()

        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": self._name},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle manual user initiation."""
        errors: dict[str, str] = {}

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            self._discovery_info = self._discovered_devices[address]
            self._name = self._discovery_info.name or DEFAULT_NAME
            return await self.async_step_pair()

        current_addresses = self._async_current_ids()
        for disc in async_discovered_service_info(self.hass, connectable=True):
            if disc.address in current_addresses:
                continue

            service_uuids = set(disc.service_uuids)
            if (
                UUID_CHEFSTEP_STREAM_SERVICE in service_uuids
                or UUID_BREVILLE_SERVICE in service_uuids
                or (disc.name and "joule" in disc.name.lower())
            ):
                self._discovered_devices[disc.address] = disc

        if not self._discovered_devices:
            return self.async_abort(reason="no_devices_found")

        device_options = {
            addr: f"{disc.name or DEFAULT_NAME} ({addr})"
            for addr, disc in self._discovered_devices.items()
        }

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(device_options)}
            ),
            errors=errors,
        )

    async def async_step_pair(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Perform BLE connection and authenticated pairing."""
        errors: dict[str, str] = {}
        assert self._discovery_info is not None

        ble_device = self._discovery_info.device
        client = JouleClient(ble_device)

        try:
            await client.connect(timeout=15.0)
            # Identify circulator to read device info
            dev_info = await client.identify()
            # Perform pairing / key exchange if needed
            try:
                await client.pair_or_authenticate(timeout=15.0)
            except JouleAuthenticationError as auth_err:
                _LOGGER.warning("Authentication skipped or not needed: %s", auth_err)

            title = dev_info.name or self._name
            await client.disconnect()

            return self.async_create_entry(
                title=title,
                data={
                    CONF_ADDRESS: self._discovery_info.address,
                    "name": title,
                    "model": dev_info.model,
                    "serial_number": dev_info.serial_number,
                    "hardware_version": dev_info.hardware_version,
                    "firmware_version": dev_info.firmware_version,
                },
            )
        except (JouleConnectionError, TimeoutError):
            errors["base"] = "cannot_connect"
        except Exception as err:
            _LOGGER.exception("Unexpected error during Joule pairing: %s", err)
            errors["base"] = "unknown"
        finally:
            if client.is_connected:
                await client.disconnect()

        return self.async_show_form(
            step_id="pair",
            description_placeholders={"name": self._name},
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get options flow."""
        return JouleOptionsFlowHandler(config_entry)


class JouleOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Joule options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage Joule options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_AUTO_START_TIMER,
                        default=self.config_entry.options.get(
                            CONF_AUTO_START_TIMER, DEFAULT_AUTO_START_TIMER
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_IDLE_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                }
            ),
        )
