"""Device automation triggers for ChefSteps / Breville Joule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType
import voluptuous as vol

from .const import (
    DOMAIN,
    EVENT_COOK_COMPLETED,
    EVENT_LOW_WATER,
    EVENT_WATER_AT_TEMPERATURE,
    TRIGGER_TYPE_COOK_COMPLETED,
    TRIGGER_TYPE_LOW_WATER,
    TRIGGER_TYPE_WATER_AT_TEMPERATURE,
)

TRIGGER_TYPES = {
    TRIGGER_TYPE_WATER_AT_TEMPERATURE,
    TRIGGER_TYPE_COOK_COMPLETED,
    TRIGGER_TYPE_LOW_WATER,
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, Any]]:
    """Return a list of device triggers."""
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DEVICE_ID: device_id,
            CONF_DOMAIN: DOMAIN,
            CONF_TYPE: trig_type,
        }
        for trig_type in TRIGGER_TYPES
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Attach a trigger."""
    trig_type = config[CONF_TYPE]
    event_name = EVENT_WATER_AT_TEMPERATURE

    if trig_type == TRIGGER_TYPE_COOK_COMPLETED:
        event_name = EVENT_COOK_COMPLETED
    elif trig_type == TRIGGER_TYPE_LOW_WATER:
        event_name = EVENT_LOW_WATER

    event_config = {
        event_trigger.CONF_PLATFORM: "event",
        event_trigger.CONF_EVENT_TYPE: event_name,
        event_trigger.CONF_EVENT_DATA: {
            CONF_DEVICE_ID: config[CONF_DEVICE_ID],
        },
    }
    schema = event_trigger.TRIGGER_SCHEMA(event_config)
    return await event_trigger.async_attach_trigger(
        hass, schema, action, trigger_info, platform_type="device"
    )
