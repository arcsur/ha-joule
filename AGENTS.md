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
  - If `cookTime` is active/positive (>0), `programType` **MUST** be set to `AUTOMATIC` (`1`).
  - If `cookTime` is 0 or not active (manual cook), `programType` **MUST** be set to `MANUAL` (`0`), and `cookTime` **MUST NOT** be serialized into the message.
  - Only populate optional fields (`delayedStart`, `holdingTemperature`) when active/non-zero. Explicitly setting `holdingTemperature=0.0` or `delayedStart=0` can cause firmware validation failure.

### 7. Tolerant State Handling on Stop and Clear Errors
- Sending `StopCirculatorRequest` to an idle or already-stopped circulator returns `CS_ERROR_INVALID_STATE` (code 8). Treat this as success.
- Sending `ClearErrorRequest` when no hardware fault is active returns `CS_ERROR_INVALID_STATE` (code 8) or `CS_ERROR_INTERNAL` (code 3). Treat these as successful no-ops.

### 8. Running Tests & Quality Checks
```bash
# Lint & format
uv run ruff check src tests
uv run ruff format --check src tests

# Type check
uv run --extra dev mypy src/joule_ble

# Run test suite
uv run --extra dev pytest tests/ -v
```
