"""Core control logic for Heatpump Controller."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util

from .const import (
    CONF_ON_OFF_SWITCH,
    CONF_HYSTERESIS_ON,
    CONF_HYSTERESIS_OFF,
    CONF_MIN_SWITCH_INTERVAL,
    CONF_SETPOINT_DELTA,
    CONF_ROOMS,
    CONF_ENTITY,
    CONF_WEIGHT,
)

_LOGGER = logging.getLogger(__name__)

FALLBACK_INTERVAL = timedelta(seconds=60)


class HeatpumpCoordinator:
    """Manages heatpump control logic."""

    def __init__(self, hass: HomeAssistant, config: dict) -> None:
        self.hass = hass
        self._on_off_switch: str = config[CONF_ON_OFF_SWITCH]
        self._hysteresis_on: float = config[CONF_HYSTERESIS_ON]
        self._hysteresis_off: float = config[CONF_HYSTERESIS_OFF]
        self._min_switch_interval: int = config[CONF_MIN_SWITCH_INTERVAL]
        self._setpoint_delta: float = config[CONF_SETPOINT_DELTA]
        self._rooms: list[dict] = config[CONF_ROOMS]

        self._target_temperature: float = config.get("initial_target_temperature", 20.0)
        self._last_switch_time: Optional[datetime] = None
        self._enabled: bool = True

        # Callbacks registered by platform entities to notify of coordinator updates
        self._listeners: list = []

    @property
    def target_temperature(self) -> float:
        return self._target_temperature

    @property
    def is_enabled(self) -> bool:
        """Return True if automatic heatpump control is active."""
        return self._enabled

    @property
    def weighted_average_temperature(self) -> Optional[float]:
        """Calculate current weighted average temperature from all room entities."""
        total_weight = 0.0
        weighted_sum = 0.0

        for room in self._rooms:
            entity_id = room[CONF_ENTITY]
            weight = room[CONF_WEIGHT]
            state = self.hass.states.get(entity_id)

            if state is None or state.state in ("unavailable", "unknown"):
                _LOGGER.debug("Room entity %s is unavailable, skipping", entity_id)
                continue

            current_temp = state.attributes.get("current_temperature")
            if current_temp is None:
                _LOGGER.debug("Room entity %s has no current_temperature attribute", entity_id)
                continue

            try:
                temp = float(current_temp)
            except (ValueError, TypeError):
                _LOGGER.warning("Room entity %s returned non-numeric temperature: %s", entity_id, current_temp)
                continue

            weighted_sum += temp * weight
            total_weight += weight

        if total_weight == 0:
            return None

        return weighted_sum / total_weight

    @property
    def is_heatpump_on(self) -> Optional[bool]:
        """Return True if the heatpump switch is on."""
        state = self.hass.states.get(self._on_off_switch)
        if state is None or state.state in ("unavailable", "unknown"):
            return None
        return state.state == "on"

    @property
    def cooldown_remaining(self) -> float:
        """Return seconds remaining in cooldown, or 0 if not in cooldown."""
        if self._last_switch_time is None:
            return 0.0
        elapsed = (dt_util.utcnow() - self._last_switch_time).total_seconds()
        remaining = self._min_switch_interval - elapsed
        return max(0.0, remaining)

    @property
    def in_cooldown(self) -> bool:
        """Return True if currently in cooldown period."""
        return self.cooldown_remaining > 0

    async def async_setup(self) -> None:
        """Set up event subscriptions and periodic fallback."""
        entities_to_watch = [room[CONF_ENTITY] for room in self._rooms] + [self._on_off_switch]

        async_track_state_change_event(
            self.hass,
            entities_to_watch,
            self._async_state_changed,
        )

        async_track_time_interval(
            self.hass,
            self._async_periodic_check,
            FALLBACK_INTERVAL,
        )

        _LOGGER.debug("Heatpump coordinator set up, watching: %s", entities_to_watch)

        # Run initial evaluation after setup
        await self.async_evaluate()

    @callback
    def _async_state_changed(self, event) -> None:
        """Handle state change of a watched entity."""
        entity_id = event.data.get("entity_id")
        _LOGGER.debug("State changed for %s, re-evaluating", entity_id)
        self.hass.async_create_task(self.async_evaluate())

    @callback
    def _async_periodic_check(self, now) -> None:
        """Periodic fallback check."""
        _LOGGER.debug("Periodic fallback evaluation at %s", now)
        self.hass.async_create_task(self.async_evaluate())

    async def async_evaluate(self) -> None:
        """Main control loop: update setpoints and evaluate heatpump on/off."""
        await self._async_update_room_setpoints()
        await self._async_control_heatpump()
        self._notify_listeners()

    async def _async_update_room_setpoints(self) -> None:
        """Set all room climate entities to target_temperature + setpoint_delta."""
        desired_setpoint = self._target_temperature + self._setpoint_delta
        for room in self._rooms:
            entity_id = room[CONF_ENTITY]
            state = self.hass.states.get(entity_id)
            if state is None or state.state in ("unavailable", "unknown"):
                continue

            current_setpoint = state.attributes.get("temperature")
            if current_setpoint is not None:
                try:
                    if abs(float(current_setpoint) - desired_setpoint) < 0.01:
                        continue  # Already at desired setpoint
                except (ValueError, TypeError):
                    pass

            _LOGGER.debug(
                "Setting %s setpoint to %.1f (target=%.1f + delta=%.1f)",
                entity_id, desired_setpoint, self._target_temperature, self._setpoint_delta,
            )
            await self.hass.services.async_call(
                "climate",
                "set_temperature",
                {"entity_id": entity_id, "temperature": desired_setpoint},
                blocking=False,
            )

    async def async_set_enabled(self, enabled: bool) -> None:
        """Enable or disable automatic control. When disabling, turns off the switch."""
        self._enabled = enabled
        if not enabled:
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": self._on_off_switch}, blocking=False
            )
        self._notify_listeners()

    async def _async_control_heatpump(self) -> None:
        """Evaluate conditions and switch heatpump on or off."""
        if not self._enabled:
            return
        avg_temp = self.weighted_average_temperature
        if avg_temp is None:
            _LOGGER.debug("No valid room temperatures available, skipping control")
            return

        is_on = self.is_heatpump_on
        if is_on is None:
            _LOGGER.debug("Heatpump switch state unavailable, skipping control")
            return

        target = self._target_temperature

        if not is_on and avg_temp < (target - self._hysteresis_on):
            if self.in_cooldown:
                _LOGGER.debug(
                    "Would turn ON (avg=%.2f < target=%.2f - hysteresis=%.2f) but in cooldown (%.0fs remaining)",
                    avg_temp, target, self._hysteresis_on, self.cooldown_remaining,
                )
                return
            _LOGGER.info(
                "Turning heatpump ON: avg=%.2f < %.2f (target=%.2f - hysteresis=%.2f)",
                avg_temp, target - self._hysteresis_on, target, self._hysteresis_on,
            )
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": self._on_off_switch}, blocking=False
            )
            self._last_switch_time = dt_util.utcnow()

        elif is_on and avg_temp > (target + self._hysteresis_off):
            if self.in_cooldown:
                _LOGGER.debug(
                    "Would turn OFF (avg=%.2f > target=%.2f + hysteresis=%.2f) but in cooldown (%.0fs remaining)",
                    avg_temp, target, self._hysteresis_off, self.cooldown_remaining,
                )
                return
            _LOGGER.info(
                "Turning heatpump OFF: avg=%.2f > %.2f (target=%.2f + hysteresis=%.2f)",
                avg_temp, target + self._hysteresis_off, target, self._hysteresis_off,
            )
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": self._on_off_switch}, blocking=False
            )
            self._last_switch_time = dt_util.utcnow()

        else:
            _LOGGER.debug(
                "No switch needed: avg=%.2f, on_threshold=%.2f, off_threshold=%.2f, heatpump_on=%s",
                avg_temp,
                target - self._hysteresis_on,
                target + self._hysteresis_off,
                is_on,
            )

    async def async_set_target_temperature(self, temperature: float) -> None:
        """Update the target temperature and re-evaluate immediately."""
        _LOGGER.info("Target temperature changed: %.1f -> %.1f", self._target_temperature, temperature)
        self._target_temperature = temperature
        await self.async_evaluate()

    def register_listener(self, callback_fn) -> None:
        """Register a callback to be notified on coordinator updates."""
        self._listeners.append(callback_fn)

    def _notify_listeners(self) -> None:
        """Notify all registered listeners of a state update."""
        for listener in self._listeners:
            listener()
