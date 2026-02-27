"""Heatpump Controller custom integration."""

from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.core import HomeAssistant
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN
from .config import CONFIG_SCHEMA as DOMAIN_CONFIG_SCHEMA
from .coordinator import HeatpumpCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: DOMAIN_CONFIG_SCHEMA},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Heatpump Controller integration."""
    if DOMAIN not in config:
        return True

    conf = config[DOMAIN]
    _LOGGER.info("Setting up Heatpump Controller with config: %s", conf)

    coordinator = HeatpumpCoordinator(hass, conf)
    hass.data[DOMAIN] = coordinator

    await coordinator.async_setup()

    # Load platforms
    for platform in ("sensor", "binary_sensor", "climate"):
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    return True
