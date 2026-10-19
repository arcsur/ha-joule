"""DataUpdateCoordinator for ChefSteps / Breville Joule."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from bleak.backends.device import BLEDevice
from homeassistant.components import bluetooth, persistent_notification
from homeassistant.components.bluetooth import BluetoothChange
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, EVENT_CALL_SERVICE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from joule_ble import (
    CookState,
    ErrorState,
    JouleClient,
    JouleConnectionError,
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
        self._was_idle_disconnected: bool = False
        self._idle_timer_cancel: CALLBACK_TYPE | None = None
        self._unsubscribe_client_callbacks: CALLBACK_TYPE | None = None
        self._unsubscribe_bluetooth: CALLBACK_TYPE | None = None
        self._unsubscribe_unavailable: CALLBACK_TYPE | None = None
        self._unsubscribe_service_call: CALLBACK_TYPE | None = None
        self._notification_id: str = f"joule_error_{self.address.replace(':', '_')}"
        self._notification_active: bool = False

        # Register client callback
        self._unsubscribe_client_callbacks = self.client.register_callback(
            self._handle_client_update
        )

    @property
    def available(self) -> bool:
        """Return True if the Joule device is currently available."""
        if self.client.is_connected:
            return True
        return bool(
            self._was_idle_disconnected
            and bluetooth.async_address_present(
                self.hass, self.address, connectable=True
            )
        )

    @property
    def is_cooking(self) -> bool:
        """Return True if device is actively cooking."""
        if self.data and hasattr(self.data, "is_cooking"):
            return bool(self.data.is_cooking)
        if hasattr(self.client, "state") and hasattr(self.client.state, "is_cooking"):
            return bool(self.client.state.is_cooking)
        return False

    @property
    def has_error(self) -> bool:
        """Return True if device is in an error condition."""
        if self.data and hasattr(self.data, "has_error"):
            return bool(self.data.has_error)
        if hasattr(self.client, "state") and hasattr(self.client.state, "has_error"):
            return bool(self.client.state.has_error)
        return False

    async def async_setup(self) -> None:
        """Set up Bluetooth callbacks and initial connection."""
        self._unsubscribe_bluetooth = bluetooth.async_register_callback(
            self.hass,
            self._async_handle_bluetooth_event,
            {"address": self.address, "connectable": True},
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

        if hasattr(bluetooth, "async_track_unavailable"):
            self._unsubscribe_unavailable = bluetooth.async_track_unavailable(
                self.hass,
                self._async_handle_bluetooth_unavailable,
                self.address,
                connectable=True,
            )

        @callback
        def _async_handle_service_call(event: Any) -> None:
            data = getattr(event, "data", {})
            if (
                data.get("domain") == "persistent_notification"
                and data.get("service") == "dismiss"
                and data.get("service_data", {}).get("notification_id")
                == self._notification_id
            ):
                _LOGGER.info(
                    "Persistent notification dismissed for Joule (%s); clearing errors on device",
                    self.address,
                )
                self.hass.async_create_task(self.async_clear_errors())

        self._unsubscribe_service_call = self.hass.bus.async_listen(
            EVENT_CALL_SERVICE, _async_handle_service_call
        )

        # Establish initial connection in background to stream telemetry immediately
        async def _initial_connect() -> None:
            try:
                await self.async_ensure_connected()
            except Exception as err:  # noqa: BLE001
                _LOGGER.info(
                    "Initial connection to Joule (%s) deferred (device currently unavailable): %s",
                    self.address,
                    err,
                )

        self.hass.async_create_task(_initial_connect())

    @callback
    def _async_handle_bluetooth_event(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Handle updated BLEDevice from Home Assistant Bluetooth scanner."""
        self._ble_device = service_info.device
        self.client._ble_device = service_info.device
        if service_info.manufacturer_data and 345 in service_info.manufacturer_data:
            mfg = service_info.manufacturer_data[345]
            if len(mfg) > 1:
                self.client._recipient_address = mfg[1:]

        # If not connected and we have never received data or were disconnected unexpectedly,
        # connect now to begin streaming telemetry
        if not self.client.is_connected and (
            self.data is None or not self._was_idle_disconnected
        ):
            _LOGGER.debug(
                "Joule (%s) advertisement detected; connecting in background",
                self.address,
            )
            self.hass.async_create_task(self.async_ensure_connected())

        self.async_update_listeners()

    @callback
    def _async_handle_bluetooth_unavailable(
        self,
        service_info: bluetooth.BluetoothServiceInfoBleak,
    ) -> None:
        """Handle device no longer being seen by Bluetooth scanner."""
        _LOGGER.debug("Joule (%s) is no longer seen by Bluetooth scanner", self.address)
        self.async_update_listeners()

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
        if (
            old_step != CookState.WAITING_FOR_FOOD
            and new_step == CookState.WAITING_FOR_FOOD
        ):
            _LOGGER.info(
                "Joule (%s) reached target temperature! Add food now", self.address
            )
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
        if (
            old_step == CookState.COOKING
            and new_step == CookState.WAITING_FOR_REMOVE_FOOD
        ):
            _LOGGER.info(
                "Joule (%s) cook timer completed! Ready to remove food", self.address
            )
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

        # 4. Manage persistent error notification
        is_error = (
            state.error_state != ErrorState.NO_ERROR
            or state.low_water
            or state.motor_fault
            or new_step == CookState.ERROR
        )
        if is_error and not self._notification_active:
            self._notification_active = True
            dev_name = self.entry.data.get("name", f"Joule ({self.address})")
            err_msg = (
                "Low water level detected. Please add water to the bath."
                if state.low_water
                else f"An error condition was reported: {state.error_state.value}."
            )
            persistent_notification.async_create(
                self.hass,
                message=(
                    f"**{dev_name} Error Alert**\n\n{err_msg}\n\n"
                    "Dismissing this notification will automatically send a Clear Error "
                    "command to the Joule, or you can use the **Clear Error** button."
                ),
                title=f"{dev_name} Alert",
                notification_id=self._notification_id,
            )
        elif not is_error and self._notification_active:
            self._notification_active = False
            persistent_notification.async_dismiss(self.hass, self._notification_id)

        # 5. Manage idle disconnect timeout
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
        if not self.client.is_connected:
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
                self._was_idle_disconnected = True
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
        self._was_idle_disconnected = False
        if not self.client.is_connected:
            _LOGGER.debug("Connecting to Joule (%s)...", self.address)
            # Fetch latest BLEDevice from HA Bluetooth
            ble_dev = bluetooth.async_ble_device_from_address(
                self.hass, self.address, connectable=True
            )
            if ble_dev:
                self._ble_device = ble_dev
                self.client._ble_device = ble_dev
            elif not bluetooth.async_address_present(
                self.hass, self.address, connectable=True
            ):
                raise JouleConnectionError(
                    f"Joule circulator ({self.address}) is not currently advertising or in range"
                )

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
        if self.client.state.has_error or self.is_cooking:
            _LOGGER.info(
                "Joule (%s) in step %s (error=%s); resetting circulator before starting cook",
                self.address,
                self.client.state.program_step.value,
                self.client.state.error_state.value,
            )
            try:
                await self.client.stop_cook()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Pre-start stop_cook skipped/failed: %s", err)
            try:
                await self.client.clear_errors()
            except Exception as err:  # noqa: BLE001
                _LOGGER.debug("Pre-start clear_errors skipped/failed: %s", err)

        if cook_time_minutes is not None:
            cook_time_sec = cook_time_minutes * 60
        else:
            cook_time_sec = self.target_cook_time_minutes * 60
        delayed_start_sec = delayed_start_minutes * 60
        await self.client.start_cook(
            target_temp_c=target_temp_c,
            cook_time_seconds=cook_time_sec,
            delayed_start_seconds=delayed_start_sec,
            holding_temp_c=holding_temp_c,
        )
        self.async_set_updated_data(self.client.state)

    async def async_set_temperature(self, target_temp_c: float) -> None:
        """Update target temperature setpoint."""
        await self.async_ensure_connected()
        await self.client.set_temperature(target_temp_c)
        self.async_set_updated_data(self.client.state)

    async def async_stop_cook(self) -> None:
        """Stop heating and circulating."""
        await self.async_ensure_connected()
        await self.client.stop_cook()
        self.async_set_updated_data(self.client.state)

    async def async_drop_food(self) -> None:
        """Confirm food added and transition to active timer."""
        await self.async_ensure_connected()
        await self.client.drop_food()
        self.async_set_updated_data(self.client.state)

    async def async_clear_errors(self) -> None:
        """Clear software error condition and reset circulator."""
        await self.async_ensure_connected()
        await self.client.clear_errors()
        if self._notification_active:
            self._notification_active = False
            persistent_notification.async_dismiss(self.hass, self._notification_id)
        self.async_set_updated_data(self.client.state)

    async def async_identify(self) -> None:
        """Identify device."""
        await self.async_ensure_connected()
        await self.client.identify()

    async def async_pair(self, timeout: float = 30.0) -> None:
        """Initiate physical button pairing / key exchange with the Joule."""
        await self.async_ensure_connected()
        _LOGGER.info(
            "Starting key exchange with Joule (%s). Please press the top button on Joule within %ds to confirm proximity.",
            self.address,
            int(timeout),
        )
        auth_data = await self.client.start_key_exchange(timeout=timeout)
        if auth_data and auth_data.secret_key:
            secret_hex = (
                auth_data.secret_key.hex()
                if isinstance(auth_data.secret_key, bytes)
                else str(auth_data.secret_key)
            )
            new_data = {**self.entry.data, "auth_key": secret_hex}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            _LOGGER.info(
                "Successfully paired with Joule (%s) and saved authentication key to config entry",
                self.address,
            )

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
        if self._unsubscribe_service_call:
            self._unsubscribe_service_call()
            self._unsubscribe_service_call = None
        if self._notification_active:
            persistent_notification.async_dismiss(self.hass, self._notification_id)
            self._notification_active = False
        if self._unsubscribe_client_callbacks:
            self._unsubscribe_client_callbacks()
            self._unsubscribe_client_callbacks = None
        if self._unsubscribe_bluetooth:
            self._unsubscribe_bluetooth()
            self._unsubscribe_bluetooth = None
        if self._unsubscribe_unavailable:
            self._unsubscribe_unavailable()
            self._unsubscribe_unavailable = None
        if self.client.is_connected:
            await self.client.disconnect()
