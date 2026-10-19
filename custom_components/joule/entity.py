"""Base entity for ChefSteps / Breville Joule integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from joule_ble import JouleModel

from .const import DOMAIN
from .coordinator import JouleDataUpdateCoordinator


class JouleEntity(CoordinatorEntity[JouleDataUpdateCoordinator]):
    """Base class for Joule entities."""

    _attr_has_entity_name = True

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize base entity."""
        super().__init__(coordinator)
        self.entry = entry
        is_breville = (
            coordinator.client.is_breville_profile
            or entry.data.get("model") == JouleModel.JOULE_TURBO
            or "turbo" in str(entry.data.get("model", "")).lower()
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Joule"),
            manufacturer="Breville" if is_breville else "ChefSteps",
            model=entry.data.get(
                "model", "Joule Turbo" if is_breville else "Original Joule"
            ),
            sw_version=entry.data.get("firmware_version"),
            hw_version=entry.data.get("hardware_version"),
        )

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        return self.coordinator.available
