"""Sensor platform for ChefSteps / Breville Joule."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    REVOLUTIONS_PER_MINUTE,
    EntityCategory,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
import homeassistant.util.dt as dt_util

from joule_ble import CookState

from .const import DOMAIN
from .coordinator import JouleDataUpdateCoordinator

SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="bath_temp",
        translation_key="bath_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    SensorEntityDescription(
        key="cook_status",
        translation_key="cook_status",
        device_class=SensorDeviceClass.ENUM,
        options=[
            "idle",
            "pre_heating",
            "waiting_for_food",
            "cooking",
            "waiting_for_remove_food",
            "error",
            "unknown",
        ],
    ),
    SensorEntityDescription(
        key="time_remaining",
        translation_key="time_remaining",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="heater_temp",
        translation_key="heater_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="upper_board_temp",
        translation_key="upper_board_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="lower_board_temp",
        translation_key="lower_board_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="motor_rpm",
        translation_key="motor_rpm",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=REVOLUTIONS_PER_MINUTE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heater_power",
        translation_key="heater_power",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="error_severity",
        translation_key="error_severity",
        device_class=SensorDeviceClass.ENUM,
        options=["no_error", "soft_error", "hard_error"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="turbo_cook_state",
        translation_key="turbo_cook_state",
        device_class=SensorDeviceClass.ENUM,
        options=["no_turbo", "turbo_enabled", "turbo_timed_out"],
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Joule sensors from a config entry."""
    coordinator: JouleDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        JouleSensor(coordinator, entry, desc) for desc in SENSOR_DESCRIPTIONS
    ]
    entities.append(JouleCookFinishTimeSensor(coordinator, entry))
    async_add_entities(entities)


class JouleSensor(CoordinatorEntity[JouleDataUpdateCoordinator], SensorEntity):
    """Generic telemetry or status sensor for Joule."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: JouleDataUpdateCoordinator,
        entry: ConfigEntry,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data['address']}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Joule"),
            manufacturer="ChefSteps / Breville",
            model=entry.data.get("model", "Joule"),
        )

    @property
    def native_value(self) -> Any:
        """Return sensor value from coordinator telemetry."""
        if not self.coordinator.data:
            return None

        state = self.coordinator.data
        key = self.entity_description.key

        if key == "bath_temp":
            return state.bath_temp_c
        if key == "cook_status":
            return state.program_step.value
        if key == "time_remaining":
            return state.time_remaining_seconds
        if key == "heater_temp":
            return state.heater_temp_c
        if key == "upper_board_temp":
            return state.upper_board_temp_c
        if key == "lower_board_temp":
            return state.lower_board_temp_c
        if key == "motor_rpm":
            return state.motor_rpm
        if key == "heater_power":
            if state.heater_pwm is not None:
                return round(state.heater_pwm * 100.0, 1)
            return None
        if key == "error_severity":
            return state.error_state.value
        if key == "turbo_cook_state":
            return state.turbo_cook_state.value

        return None


class JouleCookFinishTimeSensor(
    CoordinatorEntity[JouleDataUpdateCoordinator], SensorEntity
):
    """Timestamp sensor for when cooking finishes, enabling live Lovelace countdowns."""

    _attr_has_entity_name = True
    _attr_translation_key = "cook_finish_time"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: JouleDataUpdateCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the timestamp sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data['address']}_cook_finish_time"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data["address"])},
            name=entry.data.get("name", "Joule"),
            manufacturer="ChefSteps / Breville",
        )

    @property
    def native_value(self) -> datetime | None:
        """Return calculated expected cook completion timestamp."""
        if (
            self.coordinator.data
            and self.coordinator.data.program_step == CookState.COOKING
            and self.coordinator.data.time_remaining_seconds
            and self.coordinator.data.time_remaining_seconds > 0
        ):
            return dt_util.utcnow() + timedelta(
                seconds=self.coordinator.data.time_remaining_seconds
            )
        return None
