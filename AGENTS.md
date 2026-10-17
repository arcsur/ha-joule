# ha-joule Development & Architecture Guidelines

## Architecture Overview

`ha-joule` is a custom component integration for Home Assistant providing control and telemetry for ChefSteps and Breville Joule sous vide immersion circulators. It wraps the asynchronous `joule-ble` library.

---

## Hardware Differences & Pairing Logic

The integration manages two hardware profiles differently:

1. **ChefSteps Original Joule (`CS10001` / `CS20001`, Hardware `J7`)**
   - Discovered via service UUID `700b4321-9836-4383-a2b2-31a9098d1473`.
   - **No Key Exchange**: Onboarding immediately identifies the device without running cryptographic key exchange.
   - **No Required Button Press**: Pairing does not require the physical top button to be pressed.

2. **Breville Joule Turbo (`CS30001`)**
   - Discovered via service UUID `c6f2d9e3-49e7-4125-9014-bfc6d669ff00`.
   - **Key Exchange Required**: Session authentication requires key exchange and stores `auth_key` in the config entry data.

---

## Config Flow Rules (`config_flow.py`)

- **Safe Profile Check**:
  ```python
  if getattr(client, "is_breville_profile", False):
      auth_data = await client.pair_or_authenticate(timeout=30.0)
  ```
  Never unconditionally call `pair_or_authenticate()` without checking `is_breville_profile`. Sinking key exchange requests to a ChefSteps device causes the circulator to drop communication and results in a 30s timeout.

- **Non-Blocking Connect**:
  During config flow onboarding, always connect with `auto_start_feed=False` so telemetry subscription does not compete with the initial identification query:
  ```python
  await client.connect(timeout=15.0, auto_start_feed=False)
  ```

---

## Coordinator & Connection Management (`coordinator.py`)

- **Bluetooth Service Callbacks**:
  `async_setup()` registers an active Bluetooth callback via `bluetooth.async_register_callback`.
  When advertisement data is updated, the coordinator updates the client's `BLEDevice` and parses Manufacturer Data ID `345` to update `_recipient_address`.

- **On-Demand BLE Connection**:
  Cooking commands call `await self.async_ensure_connected()` which establishes the connection on demand and starts live feed telemetry.

- **Idle Disconnect**:
  To conserve Bluetooth adapter slots on the Home Assistant host, the coordinator initiates an idle disconnect when not cooking, after `idle_timeout_seconds`.

---

## Quality & Testing Commands

```bash
# Run pytest with Home Assistant test environment
uv run --python 3.12 \
  --with pytest \
  --with pytest-asyncio \
  --with pytest-homeassistant-custom-component \
  --with pyserial \
  --with pyserial-asyncio \
  python -m pytest tests/
```
