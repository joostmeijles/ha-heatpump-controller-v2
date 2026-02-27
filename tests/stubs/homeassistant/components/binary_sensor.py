"""Stub for homeassistant.components.binary_sensor."""

from enum import Enum


class BinarySensorDeviceClass(str, Enum):
    RUNNING = "running"


class BinarySensorEntity:
    pass
