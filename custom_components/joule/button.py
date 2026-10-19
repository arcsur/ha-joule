"""Button platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from joule_ble import CookState

from .const import DOMAIN
from .coordinator import JouleDataUpdateCoordinator
from .entity import JouleEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule buttons from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            JouleFoodAddedButton(coordinator, entry),
            JouleIdentifyButton(coordinator, entry),
            JouleClearErrorButton(coordinator, entry),
            JoulePairButton(coordinator, entry),
        ]
    )


class JouleFoodAddedButton(JouleEntity, ButtonEntity):
    """Button to confirm food has been dropped and start timer countdown."""

    _attr_translation_key = "food_added"

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_food_added"

    @property
    def available(self) -> bool:
        """Available only when coordinator is available and waiting for food."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.coordinator.data.program_step == CookState.WAITING_FOR_FOOD
        )

    async def async_press(self) -> None:
        """Press the food added button."""
        await self.coordinator.async_drop_food()


class JouleIdentifyButton(JouleEntity, ButtonEntity):
    """Button to flash Joule LED and identify device."""

    _attr_translation_key = "identify"
    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_identify"

    async def async_press(self) -> None:
        """Trigger identify."""
        await self.coordinator.async_identify()


class JouleClearErrorButton(JouleEntity, ButtonEntity):
    """Button to clear software error condition."""

    _attr_translation_key = "clear_error"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_clear_error"

    async def async_press(self) -> None:
        """Clear errors."""
        await self.coordinator.async_clear_errors()


class JoulePairButton(JouleEntity, ButtonEntity):
    """Button to pair Joule via BLE key exchange."""

    _attr_translation_key = "pair"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize button."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.data['address']}_pair"

    async def async_press(self) -> None:
        """Trigger pairing."""
        await self.coordinator.async_pair()
