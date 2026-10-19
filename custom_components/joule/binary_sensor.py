"""Binary sensor platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import JouleDataUpdateCoordinator
from .entity import JouleEntity

BINARY_SENSOR_DESCRIPTIONS: tuple[BinarySensorEntityDescription, ...] = (
    BinarySensorEntityDescription(
        key="low_water",
        translation_key="low_water",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="motor_fault",
        translation_key="motor_fault",
        device_class=BinarySensorDeviceClass.PROBLEM,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    BinarySensorEntityDescription(
        key="heating",
        translation_key="heating",
        device_class=BinarySensorDeviceClass.RUNNING,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule binary sensors from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            JouleBinarySensor(coordinator, entry, desc)
            for desc in BINARY_SENSOR_DESCRIPTIONS
        ]
    )


class JouleBinarySensor(JouleEntity, BinarySensorEntity):
    """Representation of a Joule binary status sensor."""

    def __init__(
        self,
        coordinator: JouleDataUpdateCoordinator,
        entry: ConfigEntry,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['address']}_{description.key}"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is active."""
        if not self.coordinator.data:
            return False

        key = self.entity_description.key
        if key == "low_water":
            return self.coordinator.data.low_water
        if key == "motor_fault":
            return self.coordinator.data.motor_fault
        if key == "heating":
            return self.coordinator.data.is_heating

        return False
