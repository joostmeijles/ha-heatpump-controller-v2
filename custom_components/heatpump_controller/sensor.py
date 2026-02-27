"""Diagnostic sensors for Heatpump Controller."""

from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up Heatpump Controller sensors."""
    coordinator = hass.data[DOMAIN]
    async_add_entities([
        WeightedAverageTemperatureSensor(coordinator),
        CooldownRemainingSensor(coordinator),
    ], update_before_add=True)


class _BaseCoordinatorSensor(SensorEntity):
    """Base sensor that listens to the coordinator."""

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class WeightedAverageTemperatureSensor(_BaseCoordinatorSensor):
    """Sensor reporting the current weighted average temperature."""

    _attr_name = "Heatpump Controller Weighted Average Temperature"
    _attr_unique_id = "heatpump_controller_weighted_avg_temp"
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    @property
    def native_value(self) -> Optional[float]:
        avg = self._coordinator.weighted_average_temperature
        if avg is None:
            return None
        return round(avg, 2)


class CooldownRemainingSensor(_BaseCoordinatorSensor):
    """Sensor reporting the seconds remaining in the cooldown period."""

    _attr_name = "Heatpump Controller Cooldown Remaining"
    _attr_unique_id = "heatpump_controller_cooldown_remaining"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_icon = "mdi:timer"

    @property
    def native_value(self) -> float:
        return round(self._coordinator.cooldown_remaining)
