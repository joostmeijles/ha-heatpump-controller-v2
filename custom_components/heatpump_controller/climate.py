"""Climate entity for Heatpump Controller."""

from __future__ import annotations

import logging
from typing import Optional

from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    config: dict,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
) -> None:
    """Set up the Heatpump Controller climate entity."""
    coordinator = hass.data[DOMAIN]
    async_add_entities([HeatpumpControllerClimate(coordinator)], update_before_add=True)


class HeatpumpControllerClimate(ClimateEntity, RestoreEntity):
    """Climate entity representing the heatpump controller."""

    _attr_name = "Heatpump Controller"
    _attr_unique_id = "heatpump_controller_climate"
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5.0
    _attr_max_temp = 30.0
    _attr_target_temperature_step = 0.5

    def __init__(self, coordinator) -> None:
        self._coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Restore previous state and register coordinator listener."""
        await super().async_added_to_hass()

        # Restore persisted target temperature
        last_state = await self.async_get_last_state()
        if last_state is not None:
            try:
                restored_temp = float(last_state.attributes.get("temperature", self._coordinator.target_temperature))
                _LOGGER.debug("Restoring target temperature: %.1f", restored_temp)
                await self._coordinator.async_set_target_temperature(restored_temp)
            except (ValueError, TypeError):
                pass

        self._coordinator.register_listener(self._handle_coordinator_update)

    @callback
    def _handle_coordinator_update(self) -> None:
        self.async_write_ha_state()

    @property
    def current_temperature(self) -> Optional[float]:
        return self._coordinator.weighted_average_temperature

    @property
    def target_temperature(self) -> float:
        return self._coordinator.target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        is_on = self._coordinator.is_heatpump_on
        return HVACMode.HEAT if is_on else HVACMode.OFF

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get("temperature")
        if temperature is not None:
            await self._coordinator.async_set_target_temperature(float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Map HVAC mode to heatpump switch directly."""
        coordinator = self._coordinator
        if hvac_mode == HVACMode.HEAT:
            await coordinator.hass.services.async_call(
                "switch", "turn_on",
                {"entity_id": coordinator._on_off_switch},
                blocking=True,
            )
        elif hvac_mode == HVACMode.OFF:
            await coordinator.hass.services.async_call(
                "switch", "turn_off",
                {"entity_id": coordinator._on_off_switch},
                blocking=True,
            )

    @property
    def extra_state_attributes(self) -> dict:
        return {
            "weighted_average_temperature": self._coordinator.weighted_average_temperature,
            "cooldown_remaining": self._coordinator.cooldown_remaining,
            "in_cooldown": self._coordinator.in_cooldown,
        }
