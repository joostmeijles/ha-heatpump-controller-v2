"""Shared fixtures for heatpump_controller tests."""

import sys
import os

# Make custom_components importable from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock, AsyncMock


def make_state(state_str: str, attributes: dict = None):
    """Create a mock HA State object."""
    state = MagicMock()
    state.state = state_str
    state.attributes = attributes or {}
    return state


def make_hass(states: dict = None):
    """Create a minimal mock hass instance."""
    hass = MagicMock()
    hass.services = MagicMock()
    hass.services.async_call = AsyncMock()
    hass.async_create_task = MagicMock()

    states_map = states or {}
    hass.states.get = lambda entity_id: states_map.get(entity_id)

    return hass


BASE_CONFIG = {
    "on_off_switch": "switch.heatpump",
    "initial_target_temperature": 20.0,
    "hysteresis_on": 0.5,
    "hysteresis_off": 0.5,
    "min_switch_interval": 3600,
    "setpoint_delta": 2.0,
    "rooms": [
        {"entity": "climate.living_room", "weight": 2.0},
        {"entity": "climate.bedroom", "weight": 1.0},
    ],
}


@pytest.fixture
def base_config():
    return dict(BASE_CONFIG)


@pytest.fixture
def mock_hass():
    return make_hass()


@pytest.fixture
def coordinator(mock_hass):
    from custom_components.heatpump_controller.coordinator import HeatpumpCoordinator
    return HeatpumpCoordinator(mock_hass, BASE_CONFIG)
