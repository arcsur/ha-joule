"""Number platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JouleDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule number entities from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JouleCookTimeNumber(coordinator, entry)])


class JouleCookTimeNumber(
    CoordinatorEntity[JouleDataUpdateCoordinator], NumberEntity
):
    """Input number entity for target cook time in minutes."""

    _attr_has_entity_name = True
    _attr_translation_key = "target_cook_time"
    _attr_native_min_value = 1
    _attr_native_max_value = 4320  # 72 hours
    _attr_native_step = 1
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize number entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data['address']}_target_cook_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Joule"),
            manufacturer="ChefSteps / Breville",
        )

    @property
    def native_value(self) -> float:
        """Return configured cook time in minutes."""
        return float(self.coordinator.target_cook_time_minutes)

    async def async_set_native_value(self, value: float) -> None:
        """Set new cook time in minutes."""
        self.coordinator.async_set_target_cook_time(int(value))
