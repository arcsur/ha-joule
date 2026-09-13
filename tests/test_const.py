"""Test constants and definitions."""

from custom_components.joule.const import (
    DOMAIN,
    DEFAULT_NAME,
    PLATFORMS,
    EVENT_WATER_AT_TEMPERATURE,
    EVENT_COOK_COMPLETED,
    EVENT_LOW_WATER,
    MIN_TEMP_C,
    MAX_TEMP_C,
)


def test_constants():
    """Verify core constants."""
    assert DOMAIN == "joule"
    assert DEFAULT_NAME == "Joule"
    assert len(PLATFORMS) == 6
    assert EVENT_WATER_AT_TEMPERATURE == "joule_water_at_temperature"
    assert EVENT_COOK_COMPLETED == "joule_cook_completed"
    assert EVENT_LOW_WATER == "joule_low_water"
    assert MIN_TEMP_C == 20.0
    assert MAX_TEMP_C == 98.0
