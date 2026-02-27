"""Stub for homeassistant.components.climate."""

from enum import Enum


class HVACMode(str, Enum):
    HEAT = "heat"
    OFF = "off"


class ClimateEntityFeature:
    TARGET_TEMPERATURE = 1


class ClimateEntity:
    pass
