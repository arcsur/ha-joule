"""Config flow for ChefSteps / Breville Joule integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from joule_ble import (
    JouleAuthenticationError,
    JouleBluetoothDeviceData,
    JouleClient,
    JouleConnectionError,
    JouleTimeoutError,
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

        if user_input is None:
            return self.async_show_form(
                step_id="pair",
                description_placeholders={"name": self._name},
            )

        ble_device = self._discovery_info.device
        parser = JouleBluetoothDeviceData()
        disc_device_info = parser.update(
            ble_device, self._discovery_info.advertisement
        )
        recipient_addr = (
            disc_device_info.recipient_address
            if disc_device_info and disc_device_info.recipient_address
            else None
        )
        client = JouleClient(ble_device, recipient_address=recipient_addr)

        try:
            # Connect without auto-starting cook feed so pairing is not blocked
            await client.connect(timeout=15.0, auto_start_feed=False)

            # Identify circulator to read device info
            dev_info = None
            try:
                dev_info = await client.identify()
            except (JouleTimeoutError, TimeoutError) as ident_err:
                _LOGGER.debug(
                    "Initial identify query timed out (%s); attempting key exchange / pairing first...",
                    ident_err,
                )

            # Perform pairing / key exchange: prompts user with flashing LED to press top button
            auth_data = await client.start_key_exchange(timeout=30.0)

            # If initial identify query was gated behind pairing, re-try identify now
            if dev_info is None or not dev_info.serial_number:
                try:
                    dev_info = await client.identify()
                except Exception as ident_err2:
                    _LOGGER.warning(
                        "Post-auth identify query skipped or timed out: %s", ident_err2
                    )
                    dev_info = client.device_info

            title = dev_info.name or self._name
            await client.disconnect()

            entry_data: dict[str, Any] = {
                CONF_ADDRESS: self._discovery_info.address,
                "name": title,
                "model": dev_info.model,
                "serial_number": dev_info.serial_number,
                "hardware_version": dev_info.hardware_version,
                "firmware_version": dev_info.firmware_version,
            }
            if dev_info.recipient_address:
                try:
                    entry_data["recipient_address"] = dev_info.recipient_address.decode(
                        "utf-8"
                    )
                except UnicodeDecodeError:
                    entry_data["recipient_address"] = dev_info.recipient_address.hex()

            if auth_data and auth_data.secret_key:
                secret_hex = (
                    auth_data.secret_key.hex()
                    if isinstance(auth_data.secret_key, bytes)
                    else str(auth_data.secret_key)
                )
                entry_data["auth_key"] = secret_hex

            return self.async_create_entry(
                title=title,
                data=entry_data,
            )
        except JouleTimeoutError:
            errors["base"] = "pairing_timeout"
        except (JouleConnectionError, TimeoutError):
            errors["base"] = "cannot_connect"
        except JouleAuthenticationError:
            errors["base"] = "pairing_timeout"
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
        self._config_entry = config_entry

    @property
    def _entry(self) -> config_entries.ConfigEntry:
        """Return config entry safely across HA core versions."""
        if hasattr(self, "config_entry") and self.config_entry:
            return self.config_entry
        return self._config_entry

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
                        default=self._entry.options.get(
                            CONF_AUTO_START_TIMER, DEFAULT_AUTO_START_TIMER
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_IDLE_TIMEOUT,
                        default=self._entry.options.get(
                            CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=3600)),
                }
            ),
        )
