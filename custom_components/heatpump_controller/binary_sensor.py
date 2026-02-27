"""Binary sensors for Heatpump Controller."""

from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
    """Set up Heatpump Controller binary sensors."""
    coordinator = hass.data[DOMAIN]
    async_add_entities([
        HeatpumpActiveBinarySensor(coordinator),
        InCooldownBinarySensor(coordinator),
    ], update_before_add=True)


class _BaseCoordinatorBinarySensor(BinarySensorEntity):
    """Base binary sensor that listens to the coordinator."""

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        self._coordinator.register_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()


class HeatpumpActiveBinarySensor(_BaseCoordinatorBinarySensor):
    """Binary sensor that mirrors the heatpump on/off switch state."""

    _attr_name = "Heatpump Controller Active"
    _attr_unique_id = "heatpump_controller_active"
    _attr_device_class = BinarySensorDeviceClass.RUNNING

    @property
    def is_on(self) -> Optional[bool]:
        return self._coordinator.is_heatpump_on


class InCooldownBinarySensor(_BaseCoordinatorBinarySensor):
    """Binary sensor indicating whether the controller is in the cooldown period."""

    _attr_name = "Heatpump Controller In Cooldown"
    _attr_unique_id = "heatpump_controller_in_cooldown"
    _attr_icon = "mdi:timer-sand"

    @property
    def is_on(self) -> bool:
        return self._coordinator.in_cooldown
