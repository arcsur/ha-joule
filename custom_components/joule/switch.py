"""Switch platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_AUTO_START_TIMER, DOMAIN
from .coordinator import JouleDataUpdateCoordinator
from .entity import JouleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule switch entities from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JouleAutoStartTimerSwitch(coordinator, entry)])


class JouleAutoStartTimerSwitch(JouleEntity, SwitchEntity):
    """Switch to toggle auto-starting the timer when water reaches temperature."""

    _attr_translation_key = "auto_start_timer"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_auto_start_timer"

    @property
    def available(self) -> bool:
        """Auto-start timer setting is always available in software."""
        return True

    @property
    def is_on(self) -> bool:
        """Return True if auto-start is enabled."""
        return self.coordinator.auto_start_timer

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on auto-start timer."""
        self.coordinator.async_set_auto_start_timer(True)
        new_options = dict(self.coordinator.entry.options)
        new_options[CONF_AUTO_START_TIMER] = True
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        if hasattr(self, "hass") and self.hass is not None:
            self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off auto-start timer."""
        self.coordinator.async_set_auto_start_timer(False)
        new_options = dict(self.coordinator.entry.options)
        new_options[CONF_AUTO_START_TIMER] = False
        self.coordinator.hass.config_entries.async_update_entry(
            self.coordinator.entry, options=new_options
        )
        if hasattr(self, "hass") and self.hass is not None:
            self.async_write_ha_state()
