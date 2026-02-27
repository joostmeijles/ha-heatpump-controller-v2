"""Stub for homeassistant.components.sensor."""

from enum import Enum


class SensorDeviceClass(str, Enum):
    TEMPERATURE = "temperature"


class SensorStateClass(str, Enum):
    MEASUREMENT = "measurement"


class SensorEntity:
    pass
