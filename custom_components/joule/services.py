"""Custom services for ChefSteps / Breville Joule."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr
import voluptuous as vol

from .const import (
    ATTR_COOK_TIME,
    ATTR_DELAYED_START,
    ATTR_HOLDING_TEMP,
    ATTR_TARGET_TEMP,
    DOMAIN,
    MAX_TEMP_C,
    MIN_TEMP_C,
    SERVICE_CLEAR_ERROR,
    SERVICE_DROP_FOOD,
    SERVICE_IDENTIFY,
    SERVICE_START_COOK,
)
from .coordinator import JouleDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

START_COOK_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): vol.All(vol.Coerce(str)),
        vol.Required(ATTR_TARGET_TEMP): vol.All(
            vol.Coerce(float), vol.Range(min=MIN_TEMP_C, max=MAX_TEMP_C)
        ),
        vol.Optional(ATTR_COOK_TIME, default=60): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=4320)
        ),
        vol.Optional(ATTR_DELAYED_START, default=0): vol.All(
            vol.Coerce(int), vol.Range(min=0, max=1440)
        ),
        vol.Optional(ATTR_HOLDING_TEMP, default=0.0): vol.All(
            vol.Coerce(float), vol.Range(min=0.0, max=MAX_TEMP_C)
        ),
    }
)

DEVICE_ACTION_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): vol.All(vol.Coerce(str)),
    }
)


def _get_coordinator(
    hass: HomeAssistant, call: ServiceCall
) -> JouleDataUpdateCoordinator:
    """Resolve coordinator from device_id or single configured Joule."""
    device_id = call.data.get(ATTR_DEVICE_ID)

    if device_id:
        dev_reg = dr.async_get(hass)
        device = dev_reg.async_get(device_id)
        if device:
            for entry_id in device.config_entries:
                if entry_id in hass.data.get(DOMAIN, {}):
                    return hass.data[DOMAIN][entry_id]

    # Fallback to the only Joule if one exists
    coordinators: dict[str, JouleDataUpdateCoordinator] = hass.data.get(DOMAIN, {})
    if len(coordinators) == 1:
        return next(iter(coordinators.values()))

    raise HomeAssistantError("Could not determine which Joule device to target")


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register custom services for Joule."""

    async def handle_start_cook(call: ServiceCall) -> None:
        coord = _get_coordinator(hass, call)
        await coord.async_start_cook(
            target_temp_c=call.data[ATTR_TARGET_TEMP],
            cook_time_minutes=call.data.get(ATTR_COOK_TIME),
            delayed_start_minutes=call.data.get(ATTR_DELAYED_START, 0),
            holding_temp_c=call.data.get(ATTR_HOLDING_TEMP, 0.0),
        )

    async def handle_drop_food(call: ServiceCall) -> None:
        coord = _get_coordinator(hass, call)
        await coord.async_drop_food()

    async def handle_clear_error(call: ServiceCall) -> None:
        coord = _get_coordinator(hass, call)
        await coord.async_clear_errors()

    async def handle_identify(call: ServiceCall) -> None:
        coord = _get_coordinator(hass, call)
        await coord.async_identify()

    hass.services.async_register(
        DOMAIN, SERVICE_START_COOK, handle_start_cook, schema=START_COOK_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DROP_FOOD, handle_drop_food, schema=DEVICE_ACTION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_CLEAR_ERROR, handle_clear_error, schema=DEVICE_ACTION_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_IDENTIFY, handle_identify, schema=DEVICE_ACTION_SCHEMA
    )


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unregister services when last entry is unloaded."""
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_START_COOK)
        hass.services.async_remove(DOMAIN, SERVICE_DROP_FOOD)
        hass.services.async_remove(DOMAIN, SERVICE_CLEAR_ERROR)
        hass.services.async_remove(DOMAIN, SERVICE_IDENTIFY)
