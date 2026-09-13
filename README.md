# Home Assistant Joule Integration (`ha-joule`)

[![HACS Custom Component](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/arcsur/ha-joule)](https://github.com/arcsur/ha-joule/releases)
[![License](https://img.shields.io/github/license/arcsur/ha-joule)](LICENSE)

Complete Home Assistant integration for **ChefSteps** and **Breville Joule** sous vide immersion circulators over local Bluetooth Low Energy (BLE), powered by [`joule-ble`](https://github.com/arcsur/joule-ble).

---

## Supported Hardware

- **Original ChefSteps Joule** (`CS10001`, `CS20001`)
- **Breville Joule Turbo** (`CS30001`)

---

## Key Features

- ⚡ **100% Local BLE Control**: Zero cloud dependencies or accounts required.
- 🔍 **Interactive Setup & In-Flow Pairing**: Discovered automatically by Home Assistant's Bluetooth integration with interactive pairing.
- 🌡️ **Thermostat / Climate Control**:
  - Full climate card support with setpoint dials and HVAC modes (`Heat` / `Off`).
  - Target temperature precision of 0.1°C / 0.5°F (Range: 20.0°C – 98.0°C).
- ⏱️ **Intelligent Cook Timers & "Add Food Now" Workflow**:
  - **Preheating Phase**: The circulator brings the water bath up to setpoint temperature.
  - **Add Food Now**: When the target temperature is reached, Joule enters `Add Food Now` (`WAITING_FOR_FOOD`) and beeps/alerts.
  - **Food Added Confirmation**: Tap the **Food Added (Start Timer)** button in Home Assistant (or press the button on the Joule) to start the cook timer.
  - **Auto-start Timer Option**: Toggle the `Auto-start Timer when at Temp` switch to automatically advance from preheating to active cook timer as soon as water is up to temperature.
  - **Live UI Countdown**: Dedicated `Cook Finish Time` timestamp sensor renders automatic live countdowns (`in 45 minutes`) on dashboards.
- 📊 **Telemetry & Diagnostic Suite**:
  - Water Bath Temperature
  - Heater Temperature & Power PWM (%)
  - Internal Electronics / Board PCB Temperatures (Upper & Lower)
  - Motor Speed (RPM)
  - Fault Detection (Low Water Level & Motor Stalls)
- 🔔 **Native Device Automations & Triggers**:
  - Trigger when water reaches target temperature (`water_at_temperature`).
  - Trigger when cook timer completes (`cook_completed`).
  - Trigger when low water is detected (`low_water_detected`).
- 🔋 **Smart BLE Connection Lifecycle**: Keeps an active, low-latency telemetry connection while cooking, and cleanly disconnects after an idle timeout to conserve Bluetooth adapter / proxy bandwidth.

---

## Exposed Entities

| Platform | Entity Name | Description |
| :--- | :--- | :--- |
| **Climate** | `climate.<name>_circulator` | Main dial for target temperature and start / stop. |
| **Sensor** | `sensor.<name>_water_temperature` | Live water temperature (°C). |
| **Sensor** | `sensor.<name>_cook_status` | Status: `Idle`, `Preheating`, `Add Food Now`, `Cooking`, `Ready to Remove`, `Error`. |
| **Sensor** | `sensor.<name>_cook_finish_time` | Timestamp sensor for live countdown timer. |
| **Sensor** | `sensor.<name>_time_remaining` | Cook time remaining in seconds. |
| **Sensor** *(Diag)* | `sensor.<name>_heater_temperature` | Internal heater thermistor temperature. |
| **Sensor** *(Diag)* | `sensor.<name>_heater_power` | Heater PWM output percentage (0–100%). |
| **Sensor** *(Diag)* | `sensor.<name>_motor_rpm` | Impeller motor speed in RPM. |
| **Sensor** *(Diag)* | `sensor.<name>_upper_board_temperature` | Upper PCB microcontroller temperature. |
| **Sensor** *(Diag)* | `sensor.<name>_lower_board_temperature` | Lower PCB thermistor temperature. |
| **Sensor** *(Diag)* | `sensor.<name>_error_severity` | Error state (`Normal`, `Soft Fault`, `Hardware Failure`). |
| **Binary Sensor** | `binary_sensor.<name>_heating` | Active when heater is warming water. |
| **Binary Sensor** | `binary_sensor.<name>_low_water_level` | Warning when water level is below minimum intake. |
| **Binary Sensor** | `binary_sensor.<name>_motor_fault` | Warning if circulator motor is stalled or blocked. |
| **Button** | `button.<name>_food_added` | Confirms food dropped and starts cook timer. |
| **Button** | `button.<name>_identify_device` | Flashes indicator LED and beeps circulator. |
| **Button** | `button.<name>_clear_error` | Clears soft errors / faults. |
| **Number** | `number.<name>_target_cook_time` | Desired cook timer duration in minutes. |
| **Switch** | `switch.<name>_auto_start_timer_when_at_temp` | Automatically start cook timer once water reaches temp. |

---

## Custom Services

### `joule.start_cook`
Starts cooking with a specific temperature, timer duration, and optional holding temp.

```yaml
service: joule.start_cook
data:
  target_temperature: 54.5
  cook_time: 90 # minutes
  delayed_start: 0 # minutes
  holding_temperature: 50.0 # Celsius
```

### `joule.drop_food`
Confirms food has been added and advances from preheating to active cooking.

```yaml
service: joule.drop_food
```

---

## Automation Example: Add Food Notification

```yaml
alias: "Joule: Water Up to Temperature Notification"
trigger:
  - platform: device
    domain: joule
    device_id: YOUR_JOULE_DEVICE_ID
    type: water_at_temperature
action:
  - service: notify.notify
    data:
      title: "Joule Sous Vide"
      message: "Water is at {{ trigger.event.data.target_temp_c }}°C! Drop your food and press Food Added."
      data:
        actions:
          - action: "JOULE_FOOD_ADDED"
            title: "Food Added"
```

---

## Installation

### Via HACS (Recommended)

1. Open **HACS** > **Integrations** > **Custom repositories**.
2. Add repository URL: `https://github.com/arcsur/ha-joule` with category **Integration**.
3. Click **Download**, then restart Home Assistant.

### Manual Installation

1. Download the latest release `.zip` from GitHub.
2. Extract the `custom_components/joule/` folder into `<config>/custom_components/joule/`.
3. Restart Home Assistant.
