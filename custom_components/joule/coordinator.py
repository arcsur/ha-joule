"""DataUpdateCoordinator for ChefSteps / Breville Joule."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import logging
from typing import Any

from bleak.backends.device import BLEDevice
from bleak_retry_connector import establish_connection
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
import homeassistant.util.dt as dt_util

from joule_ble import (
    CookState,
    ErrorState,
    JouleAuthData,
    JouleClient,
    JouleModel,
    JouleState,
)

from .const import (
    CONF_AUTO_START_TIMER,
    CONF_IDLE_TIMEOUT,
    DEFAULT_AUTO_START_TIMER,
    DEFAULT_COOK_TIME_MINUTES,
    DEFAULT_IDLE_TIMEOUT,
    DOMAIN,
    EVENT_COOK_COMPLETED,
    EVENT_LOW_WATER,
    EVENT_WATER_AT_TEMPERATURE,
)

_LOGGER = logging.getLogger(__name__)


class JouleDataUpdateCoordinator(DataUpdateCoordinator[JouleState]):
    """Class to manage fetching Joule telemetry and managing BLE connection."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: JouleClient,
        ble_device: BLEDevice,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data.get(CONF_ADDRESS, 'joule')}",
            update_interval=None,  # Push updates via BLE notifications
        )
        self.entry = entry
        self.client = client
        self._ble_device = ble_device
        self.address = entry.data[CONF_ADDRESS]

        self.target_cook_time_minutes: int = DEFAULT_COOK_TIME_MINUTES
        self.auto_start_timer: bool = entry.options.get(
            CONF_AUTO_START_TIMER, DEFAULT_AUTO_START_TIMER
        )
        self.idle_timeout_seconds: int = entry.options.get(
            CONF_IDLE_TIMEOUT, DEFAULT_IDLE_TIMEOUT
        )

        self._previous_step: CookState = CookState.IDLE
        self._previous_low_water: bool = False
        self._idle_timer_cancel: CALLBACK_TYPE | None = None
        self._unsubscribe_client_callbacks: CALLBACK_TYPE | None = None
        self._unsubscribe_bluetooth: CALLBACK_TYPE | None = None

        # Register client callback
        self._unsubscribe_client_callbacks = self.client.register_callback(
            self._handle_client_update
        )

    async def async_setup(self) -> None:
        """Set up Bluetooth callbacks and initial connection."""
        self._unsubscribe_bluetooth = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            {"address": self.address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle updated BLEDevice from Home Assistant Bluetooth scanner."""
        self._ble_device = service_info.device
        self.client._ble_device = service_info.device

    @callback
    def _handle_client_update(self, state: JouleState) -> None:
        """Handle live telemetry dispatched by JouleClient."""
        old_step = self._previous_step
        new_step = state.program_step
        self._previous_step = new_step

        old_low_water = self._previous_low_water
        new_low_water = state.low_water
        self._previous_low_water = new_low_water

        # 1. Check for Water At Temperature ("Waiting for food")
        if old_step != CookState.WAITING_FOR_FOOD and new_step == CookState.WAITING_FOR_FOOD:
            _LOGGER.info("Joule (%s) reached target temperature! Add food now", self.address)
            self.hass.bus.async_fire(
                EVENT_WATER_AT_TEMPERATURE,
                {
                    "device_id": self.entry.entry_id,
                    "address": self.address,
                    "target_temp_c": state.target_temp_c,
                    "bath_temp_c": state.bath_temp_c,
                },
            )
            # Auto-start timer if enabled
            if self.auto_start_timer:
                _LOGGER.info("Auto-start timer enabled; advancing cook to active timer")
                self.hass.async_create_task(self.async_drop_food())

        # 2. Check for Cook Completed
        if old_step == CookState.COOKING and new_step == CookState.WAITING_FOR_REMOVE_FOOD:
            _LOGGER.info("Joule (%s) cook timer completed! Ready to remove food", self.address)
            self.hass.bus.async_fire(
                EVENT_COOK_COMPLETED,
                {
                    "device_id": self.entry.entry_id,
                    "address": self.address,
                    "bath_temp_c": state.bath_temp_c,
                },
            )

        # 3. Check for Low Water fault
        if not old_low_water and new_low_water:
            _LOGGER.warning("Joule (%s) low water level detected", self.address)
            self.hass.bus.async_fire(
                EVENT_LOW_WATER,
                {
                    "device_id": self.entry.entry_id,
                    "address": self.address,
                },
            )

        # 4. Manage idle disconnect timeout
        if not state.is_cooking:
            self._schedule_idle_disconnect()
        else:
            self._cancel_idle_disconnect()

        self.async_set_updated_data(state)

    def _schedule_idle_disconnect(self) -> None:
        """Schedule a clean BLE disconnect after idle timeout."""
        if self._idle_timer_cancel is not None:
            return
        if self.idle_timeout_seconds <= 0:
            return

        @callback
        def _execute_disconnect(_now: datetime) -> None:
            self._idle_timer_cancel = None
            if not self.client.state.is_cooking and self.client.is_connected:
                _LOGGER.debug(
                    "Joule (%s) has been idle for %ds, disconnecting BLE to conserve slots",
                    self.address,
                    self.idle_timeout_seconds,
                )
                self.hass.async_create_task(self.client.disconnect())

        self._idle_timer_cancel = async_call_later(
            self.hass, self.idle_timeout_seconds, _execute_disconnect
        )

    def _cancel_idle_disconnect(self) -> None:
        """Cancel pending idle disconnect timer."""
        if self._idle_timer_cancel is not None:
            self._idle_timer_cancel()
            self._idle_timer_cancel = None

    async def async_ensure_connected(self) -> None:
        """Ensure active connection to the Joule exists before issuing commands."""
        self._cancel_idle_disconnect()
        if not self.client.is_connected:
            _LOGGER.debug("Connecting to Joule (%s)...", self.address)
            # Fetch latest BLEDevice from HA Bluetooth
            ble_dev = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_dev:
                self._ble_device = ble_dev
                self.client._ble_device = ble_dev

            await self.client.connect()

    async def async_start_cook(
        self,
        target_temp_c: float,
        cook_time_minutes: int | None = None,
        delayed_start_minutes: int = 0,
        holding_temp_c: float = 0.0,
    ) -> None:
        """Start cooking program."""
        await self.async_ensure_connected()
        cook_time_sec = (cook_time_minutes or self.target_cook_time_minutes) * 60
        delayed_start_sec = delayed_start_minutes * 60
        await self.client.start_cook(
            target_temp_c=target_temp_c,
            cook_time_seconds=cook_time_sec,
            delayed_start_seconds=delayed_start_sec,
            holding_temp_c=holding_temp_c,
        )

    async def async_set_temperature(self, target_temp_c: float) -> None:
        """Update target temperature setpoint."""
        await self.async_ensure_connected()
        await self.client.set_temperature(target_temp_c)

    async def async_stop_cook(self) -> None:
        """Stop heating and circulating."""
        await self.async_ensure_connected()
        await self.client.stop_cook()

    async def async_drop_food(self) -> None:
        """Confirm food added and transition to active timer."""
        await self.async_ensure_connected()
        await self.client.drop_food()

    async def async_clear_errors(self) -> None:
        """Clear software error condition."""
        await self.async_ensure_connected()
        await self.client.clear_errors()

    async def async_identify(self) -> None:
        """Identify device."""
        await self.async_ensure_connected()
        await self.client.identify()

    @callback
    def async_set_auto_start_timer(self, enabled: bool) -> None:
        """Update auto-start timer setting."""
        self.auto_start_timer = enabled

    @callback
    def async_set_target_cook_time(self, minutes: int) -> None:
        """Update target cook time setting."""
        self.target_cook_time_minutes = minutes

    async def async_unload(self) -> None:
        """Clean up coordinator on integration unload."""
        self._cancel_idle_disconnect()
        if self._unsubscribe_client_callbacks:
            self._unsubscribe_client_callbacks()
            self._unsubscribe_client_callbacks = None
        if self._unsubscribe_bluetooth:
            self._unsubscribe_bluetooth()
            self._unsubscribe_bluetooth = None
        if self.client.is_connected:
            await self.client.disconnect()
