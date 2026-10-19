# Joule-BLE Development & Protocol Guidelines

## Core Protocol Architecture

`joule-ble` supports two distinct hardware generations with completely different GATT service layouts and authentication requirements:

1. **ChefSteps Original Joule (`CS10001` / `CS20001`, Hardware `J7`, Models `123`, `52R`)**
   - **Service UUID**: `700b4321-9836-4383-a2b2-31a9098d1473`
   - **Stream Write (`700b4322`)**: GATT Write Request (`WRITE_TYPE_DEFAULT`, `response=True`).
   - **Stream Read (`700b4323`)**: GATT Read to retrieve incoming `StreamMessage` payload.
   - **Stream Subscribe (`700b4325`)**: Notifications act as alert triggers signaling new data is available on `700b4323`.
   - **File Transfer (`700b4326`)**: OTA firmware file transfer (`WRITE_TYPE_NO_RESPONSE`, `response=False`).
   - **Authentication & Proximity**: Identification (`IdentifyCirculatorRequest`) and LED commands are open without authentication. However, state-changing commands (`StartProgramRequest`) require the circulator to be in `verified` proximity state. Initial key exchange (`StartKeyExchangeRequest`) requires the user to physically press the Joule's top button within the timeout period; upon confirmation the circulator replies with `StartKeyExchangeReply` containing a 64-bit secret key. The client immediately submits this key via `SubmitKeyRequest`. On subsequent reconnections, the client simply submits the stored secret key via `SubmitKeyRequest` (no button press required).

2. **Breville Joule Turbo (`CS30001`, Hardware `CS30001`)**
   - **Service UUID**: `c6f2d9e3-49e7-4125-9014-bfc6d669ff00`
   - **App Message (`c6f2d9e3-...-09`)**: GATT Write Request (`response=True`).
   - **App Feed (`c6f2d9e3-...-0b`)**: Subscribed streaming telemetry notifications.
   - **Authentication**: **REQUIRES KEY EXCHANGE**. Initiated via `StartKeyExchangeRequest` and `SubmitKeyRequest`.

---

## Critical Implementation Rules

### 1. Never Slice Protobuf Stream Messages
- **Never chunk or fragment Protobuf `StreamMessage` bytes** across BLE MTU slices.
- The official mobile app (`BleKitManager` / `AmazonFreeRTOSDevice`) always dispatches the intact Protobuf byte array in a single `writeCharacteristic` call with `WRITE_TYPE_DEFAULT`.
- Slicing payloads into 20-byte chunks corrupts message framing on Nordic nRF peripheral firmware, causing silent message rejection and pairing timeouts.

### 2. Recipient Address Negotiation
- Manufacturer Data ID `345` (`0x0159`) contains the 8-byte recipient hardware address (e.g. `b'\xc0\x00\x00\xf0\xce\xbd\xcb\xbf'`).
- Always preserve raw recipient address bytes. Do not attempt ASCII decoding if non-ASCII bytes are present.

### 3. ChefSteps Radio Settle Delay
- After subscribing to `700b4325` notifications on ChefSteps devices, allow a 500ms delay (`asyncio.sleep(0.5)`) for the BLE radio to settle before issuing the initial `IdentifyCirculatorRequest`.

### 4. ChefSteps KeepAlive & Idle Connection Maintenance
- ChefSteps Original Joule peripheral firmware runs an idle watchdog that disconnects the BLE connection after ~10-15 seconds of inactivity.
- Send a periodic `KeepAlive` message (`StreamMessage.keepAlive`) every 3 seconds to `700b4322` without waiting for a reply to maintain the connection.
- Cancel the keepalive task cleanly upon disconnection.

### 5. ChefSteps Cook Data Feed Activation
- ChefSteps Original Joule firmware requires sending `describeFeedRequest` (`feedId=COOK_DATA`) followed by `beginLiveFeed` (`feedType=COOK_DATA`) fire-and-forget (`expected_reply=None`).
- **Never wait synchronously for `beginLiveFeedReply` on ChefSteps devices**; the official app sends these asynchronously without awaiting a synchronous reply future. Awaiting a reply times out and aborts connection setup.

### 6. Atomic Stream Transaction Locking & Non-blocking KeepAlive
- Request-reply commands on `700b4322` / `700b4323` must be serialized under a single transaction lock (`_stream_lock`). Never issue pipelined writes while awaiting a command reply.
- However, raw GATT characteristic writes are guarded by `_write_lock`, which is released immediately upon write completion.
- Periodic `KeepAlive` heartbeats (and other fire-and-forget writes) do **NOT** acquire `_stream_lock`; they only acquire `_write_lock`. This prevents KeepAlive starvation and BLE link drops while awaiting long reply operations (e.g. user physical button press during key exchange).
- When constructing `StartProgramRequest`:
  - On ChefSteps (`not self._is_breville_profile`), `circulatorProgram.programType` **MUST ALWAYS** be set to `MANUAL` (`0`), and `cookTime` **MUST NOT** be serialized into the message. Local control manages timers in software. Setting `AUTOMATIC` causes ChefSteps firmware to reject the command.
  - On Breville (`self._is_breville_profile`), if `cookTime` is active/positive (>0), `programType` is `AUTOMATIC` (`1`). If 0, `programType` is `MANUAL` (`0`) and `cookTime` is omitted.
  - Only populate optional fields (`delayedStart`, `holdingTemperature`) when active/non-zero. Explicitly setting `holdingTemperature=0.0` or `delayedStart=0` can cause firmware validation failure.
- On ChefSteps, stream envelopes for control commands (`StartProgramRequest`, `StopCirculatorRequest`, `ClearErrorRequest`, `DropFoodRequest`, `UpdateProgramRequest`) must use empty sender/recipient addresses (`msg.senderAddress = b""`, `msg.recipientAddress = b""`) and a randomized 32-bit handle `random.randint(1, 2**31 - 1)` (matching the official mobile app).

### 7. ChefSteps Optimistic Concurrency & Dual Response Recognition
- `StartProgramRequest` and `StopCirculatorRequest` **MUST** include `feedId` and `sequenceNumber` populated from the latest incoming `CirculatorDataPoint`. Omission causes the firmware to silently drop the request.
- Stale Concurrency Protection: Reset `_latest_feed_id` and `_latest_seq_num` to 0 on disconnect. When initiating `start_cook` on a freshly connected ChefSteps device, wait for the first live `CirculatorDataPoint` feed session to arrive before dispatching `StartProgramRequest` to prevent `CS_ERROR_NOT_FOUND` (code 5).
- Dual response recognition: ChefSteps firmware frequently transitions directly into `programStep = PRE_HEAT` without emitting a separate `StartProgramReply` (or `IDLE` without `StopCirculatorReply`). When a `CirculatorDataPoint` reports the expected state change while a command future is pending, resolve the pending future immediately with `CS_SUCCESS`.

### 8. Tolerant State Handling on Stop and Clear Errors
- Sending `StopCirculatorRequest` to an idle or already-stopped circulator returns `CS_ERROR_INVALID_STATE` (code 8). Treat this as success.
- Sending `ClearErrorRequest` when no hardware fault is active returns `CS_ERROR_INVALID_STATE` (code 8), `CS_ERROR_INTERNAL` (code 3), or `CS_ERROR_NOT_FOUND` (code 5). Treat these as successful no-ops.
- Pre-flight State Hygiene: ChefSteps firmware rejects `StartProgramRequest` with `CS_ERROR_INVALID_STATE` (code 8) if the circulator is non-idle (e.g. already cooking or halted in `CookState.ERROR`). Proactively call `stop_cook()` and `clear_errors()` before `start_cook()` to return the hardware state machine to `IDLE`.
- Recovery Retry on Code 8: In `start_cook()`, if the firmware still returns `CS_ERROR_INVALID_STATE` (code 8), attempt automatic recovery by sending `StopCirculatorRequest` and retrying `StartProgramRequest` once with an updated handle and sequence number.

### 9. Climate Entity Setpoint & Mode Orchestration
- Maintain a separate local setpoint `_attr_target_temperature` on the climate entity. Changing the setpoint dial while `hvac_mode` is `off` must update the setpoint without prematurely starting cook commands.
- Only initiate `start_cook` from `async_set_temperature` if `hvac_mode == HEAT` is explicitly passed in `kwargs`.
- Guard `async_set_hvac_mode(HEAT)`: if the circulator is already actively cooking or starting (`self.coordinator.is_cooking`), treat subsequent mode calls as a no-op to prevent duplicate command collisions resulting in `CS_ERROR_INVALID_STATE` (code 8).
- Synchronous Coordinator State Updates: Call `self.async_set_updated_data(self.client.state)` immediately after `start_cook()`, `stop_cook()`, `set_temperature()`, `clear_errors()`, and `drop_food()` so that Home Assistant entities synchronously observe state changes before sequential service calls execute.
- Redundant Update Avoidance: In `set_temperature()`, if the bath is already cooking at the requested target temperature, avoid redundant BLE writes.
- Unconditional Stop on OFF: In `async_set_hvac_mode(OFF)`, call `async_stop_cook()` unconditionally without gating on `is_cooking`, enabling users to turn off and reset the circulator even when halted in `ERROR` state.
- Register explicit `joule.stop_cook` service alongside `joule.start_cook`.

### 10. Config Flow Pairing & Proximity Verification
- Always prompt the user before initiating `start_key_exchange(timeout=30.0)` so they are aware that the Joule's LED will flash and they have 30 seconds to physically press the top button.
- **Never swallow `JouleTimeoutError` in the config flow**: if the user does not press the button in time, display a retryable `pairing_timeout` error in the form. Creating an unverified config entry without an `auth_key` causes the Joule firmware to reject or silently ignore subsequent cook commands (`StartProgramRequest`).
- Persist the 64-bit secret key in the config entry `data["auth_key"]` (as hex string) so reconnections authenticate seamlessly via `SubmitKeyRequest` without requiring another physical button press.
- In Home Assistant 2024+, `OptionsFlow.config_entry` is a read-only property; never assign `self.config_entry = ...` directly in `__init__`. Use a private attribute `self._config_entry` and access via a safe property.

### 11. Immediate Background Connection on Integration Setup
- Schedule a background task in `async_setup()` / `async_setup_entry()` to call `async_ensure_connected()`.
- On connection, `JouleClient` automatically authenticates with the saved secret key and starts the live cook data feed (`describeFeedRequest` + `beginLiveFeed`), streaming temperature, RPM, and status to immediately populate all Home Assistant entities.

### 12. Model-Specific Entity Partitioning & Orphan Clean-up
- Hardware feature partitioning: Only expose entities that correspond to physical features supported by the target device.
  - `turbo_cook_state`: Only register for Breville Joule Turbo (`CS30001`, `coordinator.client.is_breville_profile`). Never instantiate for ChefSteps Original Joule (`CS10001`/`CS20001`), which lacks turbo overshoot algorithms.
  - Automatic Orphan Registry Clean-up: If an entity is excluded on a specific model, call `ent_reg.async_remove(entity_id)` on setup to purge any legacy or orphaned unique IDs (e.g. `{address}_turbo_cook_state`) from Home Assistant's entity registry.
  - Active Heating Tracking: `JouleState.is_heating` must remain `True` across `PRE_HEATING`, `WAITING_FOR_FOOD`, and `COOKING` so that `binary_sensor.heating` and `HVACAction.HEATING` accurately reflect active temperature maintenance during cooking without UI flickering.

### 13. Running Tests & Quality Checks
```bash
# Lint & format
uv run ruff check src tests
uv run ruff format --check src tests

# Type check
uv run --extra dev mypy src/joule_ble

# Run test suite
uv run --extra dev pytest tests/ -v
```

### 14. Graceful Offline Handling & Dynamic Availability Tracking
- **Never raise `ConfigEntryNotReady` when the circulator is unavailable at startup**: When the Joule is unplugged or powered off, `bluetooth.async_ble_device_from_address` returns `None`. Instead of failing setup and blocking entity loading, initialize with a fallback `BLEDevice(address, name, None)` so Home Assistant loads all platforms cleanly (`climate`, `sensor`, `binary_sensor`, `button`, `number`, `switch`), keeping entity IDs, dashboard cards, and automations intact.
- **Dynamic Entity Availability**: All hardware telemetry and control entities inherit `JouleEntity` and follow `coordinator.available`:
  - Returns `True` when actively connected over BLE (`client.is_connected`), OR when cleanly idle-disconnected (`_was_idle_disconnected`) and the device is actively advertising in range (`bluetooth.async_address_present`).
  - Returns `False` when the device is unplugged, powered off, or disconnected unexpectedly. Entities transition smoothly to `unavailable` in Lovelace.
  - Software settings (`target_cook_time`, `auto_start_timer`) remain available at all times so users can configure settings prior to plugging in.
- **Automatic Reconnection on Advertisement**: Register `bluetooth.async_register_callback` and `bluetooth.async_track_unavailable`. When the circulator is plugged in and begins broadcasting BLE advertisements, the coordinator automatically reconnects in the background, starts the live cook data feed, and transitions all entities from `unavailable` to live data without requiring an integration reload.

