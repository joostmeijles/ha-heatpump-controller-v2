"""Voluptuous config schema for Heatpump Controller."""

import voluptuous as vol
import homeassistant.helpers.config_validation as cv

from .const import (
    CONF_ON_OFF_SWITCH,
    CONF_INITIAL_TARGET_TEMPERATURE,
    CONF_HYSTERESIS_ON,
    CONF_HYSTERESIS_OFF,
    CONF_MIN_SWITCH_INTERVAL,
    CONF_SETPOINT_DELTA,
    CONF_ROOMS,
    CONF_ENTITY,
    CONF_WEIGHT,
)

ROOM_SCHEMA = vol.Schema({
    vol.Required(CONF_ENTITY): cv.entity_id,
    vol.Required(CONF_WEIGHT): vol.Coerce(float),
})

CONFIG_SCHEMA = vol.Schema({
    vol.Required(CONF_ON_OFF_SWITCH): cv.entity_id,
    vol.Optional(CONF_INITIAL_TARGET_TEMPERATURE, default=20.0): vol.Coerce(float),
    vol.Optional(CONF_HYSTERESIS_ON, default=0.5): vol.Coerce(float),
    vol.Optional(CONF_HYSTERESIS_OFF, default=0.5): vol.Coerce(float),
    vol.Optional(CONF_MIN_SWITCH_INTERVAL, default=3600): vol.Coerce(int),
    vol.Optional(CONF_SETPOINT_DELTA, default=2.0): vol.Coerce(float),
    vol.Required(CONF_ROOMS): vol.All([ROOM_SCHEMA], vol.Length(min=1)),
})
