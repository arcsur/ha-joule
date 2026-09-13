"""Climate platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from joule_ble import CookState

from .const import (
    DEFAULT_COOK_TIME_MINUTES,
    DEFAULT_TARGET_TEMP_C,
    DOMAIN,
    MAX_TEMP_C,
    MIN_TEMP_C,
)
from .coordinator import JouleDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule climate entity from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([JouleClimate(coordinator, entry)])


class JouleClimate(CoordinatorEntity[JouleDataUpdateCoordinator], ClimateEntity):
    """Representation of the Joule Sous Vide immersion circulator as a Climate entity."""

    _attr_has_entity_name = True
    _attr_translation_key = "circulator"
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = MIN_TEMP_C
    _attr_max_temp = MAX_TEMP_C
    _attr_target_temperature_step = 0.1
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data['address']}_climate"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Joule"),
            manufacturer="ChefSteps / Breville",
            model=entry.data.get("model", "Joule"),
            sw_version=entry.data.get("firmware_version"),
            hw_version=entry.data.get("hardware_version"),
        )

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        if self.coordinator.data and self.coordinator.data.is_cooking:
            return HVACMode.HEAT
        return HVACMode.OFF

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return the current running HVAC action."""
        if not self.coordinator.data or not self.coordinator.data.is_cooking:
            return HVACAction.OFF
        if self.coordinator.data.is_heating:
            return HVACAction.HEATING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current bath water temperature."""
        if self.coordinator.data:
            return self.coordinator.data.bath_temp_c
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target setpoint temperature."""
        if self.coordinator.data and self.coordinator.data.target_temp_c is not None:
            return self.coordinator.data.target_temp_c
        return DEFAULT_TARGET_TEMP_C

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return

        if self.coordinator.data and self.coordinator.data.is_cooking:
            await self.coordinator.async_set_temperature(float(temp))
        else:
            await self.coordinator.async_start_cook(
                target_temp_c=float(temp),
                cook_time_minutes=self.coordinator.target_cook_time_minutes,
            )

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new operation mode."""
        if hvac_mode == HVACMode.HEAT:
            target = (
                self.coordinator.data.target_temp_c
                if self.coordinator.data and self.coordinator.data.target_temp_c
                else DEFAULT_TARGET_TEMP_C
            )
            await self.coordinator.async_start_cook(
                target_temp_c=target,
                cook_time_minutes=self.coordinator.target_cook_time_minutes,
            )
        elif hvac_mode == HVACMode.OFF:
            await self.coordinator.async_stop_cook()

    async def async_turn_on(self) -> None:
        """Turn on circulator."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self) -> None:
        """Turn off circulator."""
        await self.async_set_hvac_mode(HVACMode.OFF)
