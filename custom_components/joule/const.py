"""Constants for the ChefSteps / Breville Joule integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "joule"

DEFAULT_NAME = "Joule"

# Platforms
PLATFORMS: list[Platform] = [
    Platform.CLIMATE,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SWITCH,
]

# Configuration and options
CONF_AUTO_START_TIMER = "auto_start_timer"
CONF_IDLE_TIMEOUT = "idle_timeout"
CONF_AUTH_SECRET = "auth_secret"
CONF_AUTH_TOKEN = "auth_token"
CONF_MODEL = "model"
CONF_HARDWARE_ID = "hardware_id"

# Defaults
DEFAULT_AUTO_START_TIMER = False
DEFAULT_IDLE_TIMEOUT = 300  # 5 minutes idle before BLE disconnect
DEFAULT_COOK_TIME_MINUTES = 60
DEFAULT_TARGET_TEMP_C = 56.0
MIN_TEMP_C = 20.0
MAX_TEMP_C = 98.0

# Bluetooth GATT Service UUIDs
UUID_CHEFSTEP_STREAM_SERVICE = "700b4321-9836-4383-a2b2-31a9098d1473"
UUID_BREVILLE_SERVICE = "c6f2d9e3-49e7-4125-9014-bfc6d669ff00"

# Custom Events
EVENT_WATER_AT_TEMPERATURE = f"{DOMAIN}_water_at_temperature"
EVENT_COOK_COMPLETED = f"{DOMAIN}_cook_completed"
EVENT_LOW_WATER = f"{DOMAIN}_low_water"

# Services
SERVICE_START_COOK = "start_cook"
SERVICE_DROP_FOOD = "drop_food"
SERVICE_CLEAR_ERROR = "clear_error"
SERVICE_IDENTIFY = "identify"

ATTR_TARGET_TEMP = "target_temperature"
ATTR_COOK_TIME = "cook_time"
ATTR_DELAYED_START = "delayed_start"
ATTR_HOLDING_TEMP = "holding_temperature"

# Device Trigger Types
TRIGGER_TYPE_WATER_AT_TEMPERATURE = "water_at_temperature"
TRIGGER_TYPE_COOK_COMPLETED = "cook_completed"
TRIGGER_TYPE_LOW_WATER = "low_water_detected"
