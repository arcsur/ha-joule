"""The ChefSteps / Breville Joule integration."""

from __future__ import annotations

import logging

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from joule_ble import JouleAuthData, JouleClient, JouleModel

from .const import CONF_AUTH_SECRET, CONF_AUTH_TOKEN, CONF_MODEL, DOMAIN, PLATFORMS
from .coordinator import JouleDataUpdateCoordinator
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up ChefSteps / Breville Joule from a config entry."""
    address: str = entry.data[CONF_ADDRESS]
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )

    if not ble_device:
        _LOGGER.debug(
            "Joule (%s) not found in current Bluetooth scan; initializing with placeholder BLEDevice",
            address,
        )
        ble_device = BLEDevice(
            address,
            entry.data.get("name", "Joule"),
            None,
        )

    secret_raw = entry.data.get("auth_key") or entry.data.get(CONF_AUTH_SECRET)
    secret: bytes | str | None = None
    if secret_raw:
        if isinstance(secret_raw, str):
            try:
                secret = bytes.fromhex(secret_raw)
            except ValueError:
                secret = secret_raw
        else:
            secret = secret_raw

    auth_data = JouleAuthData(
        token=entry.data.get(CONF_AUTH_TOKEN),
        secret=secret,
        secret_key=secret
        if isinstance(secret, bytes)
        else (secret.encode() if secret else None),
    )
    raw_model = entry.data.get(CONF_MODEL)
    model = (
        JouleModel(raw_model)
        if raw_model in JouleModel._value2member_map_
        else JouleModel.UNKNOWN
    )

    recipient_raw = entry.data.get("recipient_address")
    recipient_address: bytes | None = None
    if recipient_raw:
        if isinstance(recipient_raw, str):
            clean = recipient_raw.replace(":", "").replace("-", "")
            try:
                recipient_address = bytes.fromhex(clean)
            except ValueError:
                recipient_address = recipient_raw.encode("utf-8")
        elif isinstance(recipient_raw, (bytes, bytearray)):
            recipient_address = bytes(recipient_raw)

    client = JouleClient(
        ble_device,
        auth_data=auth_data,
        model=model,
        recipient_address=recipient_address,
    )
    coordinator = JouleDataUpdateCoordinator(hass, entry, client, ble_device)
    await coordinator.async_setup()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    # Set up entity platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await async_setup_services(hass)

    # Reload entry on options update
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    return True


async def async_update_options(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_unload()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await async_unload_services(hass)

    return unload_ok
