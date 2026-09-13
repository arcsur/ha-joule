# Home Assistant Joule Integration (`ha-joule`)

[![HACS Custom Component](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/default)
[![GitHub Release](https://img.shields.io/github/v/release/arcsur/ha-joule)](https://github.com/arcsur/ha-joule/releases)
[![License](https://img.shields.io/github/license/arcsur/ha-joule)](LICENSE)

Home Assistant integration for ChefSteps and Breville Joule sous vide immersion circulators over local Bluetooth Low Energy (BLE), powered by [`joule-ble`](https://github.com/arcsur/joule-ble).

## Supported Hardware

- **Original ChefSteps Joule** (`CS10001`, `CS20001`)
- **Breville Joule Turbo** (`CS30001`)

## Features

- **Automatic Bluetooth Discovery**: Discovers nearby Joule devices via active/passive BLE advertisements.
- **Local Control**: Complete local control with no cloud dependency.
- **Appliance Control**:
  - Target water temperature setpoint control
  - Start / stop cooking programs
  - Fault and error monitoring (low water level, safety faults)
- **Live Telemetry & Sensors**:
  - Current water temperature
  - Heater temperature
  - Internal electronics / control board temperatures
  - Motor RPM and status

## Installation

### Via HACS (Recommended)

1. Ensure [HACS](https://hacs.xyz/) is installed.
2. Go to **HACS** > **Integrations** > **Custom repositories**.
3. Add `https://github.com/arcsur/ha-joule` with category **Integration**.
4. Click **Download**, then restart Home Assistant.

### Manual Installation

1. Download the latest release from the [Releases](https://github.com/arcsur/ha-joule/releases) page.
2. Copy the `custom_components/joule/` folder into your Home Assistant `<config>/custom_components/` directory.
3. Restart Home Assistant.

## Configuration

1. In the Home Assistant UI, go to **Settings** > **Devices & Services**.
2. If your Joule is powered on and within Bluetooth range, it will be discovered automatically. Click **Configure**.
3. Alternatively, click **Add Integration** and search for **ChefSteps / Breville Joule**.
