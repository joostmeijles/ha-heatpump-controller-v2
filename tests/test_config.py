"""Tests for Voluptuous config schema validation."""

import pytest
import voluptuous as vol

from custom_components.heatpump_controller.config import CONFIG_SCHEMA

MINIMAL_CONFIG = {
    "on_off_switch": "switch.heatpump",
    "rooms": [{"entity": "climate.living_room", "weight": 1.0}],
}


class TestConfigSchemaValid:
    def test_minimal_config_is_accepted(self):
        config = CONFIG_SCHEMA(MINIMAL_CONFIG)
        assert config["on_off_switch"] == "switch.heatpump"
        assert len(config["rooms"]) == 1

    def test_defaults_are_applied(self):
        config = CONFIG_SCHEMA(MINIMAL_CONFIG)
        assert config["initial_target_temperature"] == pytest.approx(20.0)
        assert config["hysteresis_on"] == pytest.approx(0.5)
        assert config["hysteresis_off"] == pytest.approx(0.5)
        assert config["min_switch_interval"] == 3600
        assert config["setpoint_delta"] == pytest.approx(2.0)

    def test_full_config_overrides_defaults(self):
        config = CONFIG_SCHEMA({
            "on_off_switch": "switch.heatpump",
            "initial_target_temperature": 21.5,
            "hysteresis_on": 0.3,
            "hysteresis_off": 0.7,
            "min_switch_interval": 1800,
            "setpoint_delta": 3.0,
            "rooms": [
                {"entity": "climate.living_room", "weight": 1.5},
                {"entity": "climate.bedroom", "weight": 1.0},
            ],
        })
        assert config["initial_target_temperature"] == pytest.approx(21.5)
        assert config["hysteresis_on"] == pytest.approx(0.3)
        assert config["hysteresis_off"] == pytest.approx(0.7)
        assert config["min_switch_interval"] == 1800
        assert config["setpoint_delta"] == pytest.approx(3.0)
        assert len(config["rooms"]) == 2

    def test_multiple_rooms_accepted(self):
        config = CONFIG_SCHEMA({
            "on_off_switch": "switch.heatpump",
            "rooms": [
                {"entity": "climate.room1", "weight": 1.0},
                {"entity": "climate.room2", "weight": 2.0},
                {"entity": "climate.room3", "weight": 0.5},
            ],
        })
        assert len(config["rooms"]) == 3

    def test_weight_coerced_from_string(self):
        config = CONFIG_SCHEMA({
            "on_off_switch": "switch.heatpump",
            "rooms": [{"entity": "climate.living_room", "weight": "1"}],
        })
        assert isinstance(config["rooms"][0]["weight"], float)
        assert config["rooms"][0]["weight"] == pytest.approx(1.0)

    def test_temperature_coerced_from_string(self):
        config = CONFIG_SCHEMA({
            "on_off_switch": "switch.heatpump",
            "initial_target_temperature": "21",
            "rooms": [{"entity": "climate.living_room", "weight": 1.0}],
        })
        assert isinstance(config["initial_target_temperature"], float)
        assert config["initial_target_temperature"] == pytest.approx(21.0)

    def test_min_switch_interval_coerced_to_int(self):
        config = CONFIG_SCHEMA({
            "on_off_switch": "switch.heatpump",
            "min_switch_interval": "1800",
            "rooms": [{"entity": "climate.living_room", "weight": 1.0}],
        })
        assert isinstance(config["min_switch_interval"], int)
        assert config["min_switch_interval"] == 1800


class TestConfigSchemaInvalid:
    def test_missing_on_off_switch_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({"rooms": [{"entity": "climate.living_room", "weight": 1.0}]})

    def test_missing_rooms_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({"on_off_switch": "switch.heatpump"})

    def test_empty_rooms_list_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({"on_off_switch": "switch.heatpump", "rooms": []})

    def test_room_missing_entity_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({
                "on_off_switch": "switch.heatpump",
                "rooms": [{"weight": 1.0}],
            })

    def test_room_missing_weight_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({
                "on_off_switch": "switch.heatpump",
                "rooms": [{"entity": "climate.living_room"}],
            })

    def test_invalid_entity_id_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({
                "on_off_switch": "not_an_entity_id",
                "rooms": [{"entity": "climate.living_room", "weight": 1.0}],
            })

    def test_invalid_room_entity_id_raises(self):
        with pytest.raises(vol.Invalid):
            CONFIG_SCHEMA({
                "on_off_switch": "switch.heatpump",
                "rooms": [{"entity": "not_valid", "weight": 1.0}],
            })
