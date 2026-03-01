"""Tests for HeatpumpCoordinator core control logic."""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

from custom_components.heatpump_controller.coordinator import HeatpumpCoordinator
from tests.conftest import make_hass, make_state, BASE_CONFIG

# Fixed "now" used across cooldown/switch tests
NOW = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
COORDINATOR_MODULE = "custom_components.heatpump_controller.coordinator"


def coord_with_states(states: dict, config_overrides: dict = None) -> HeatpumpCoordinator:
    """Convenience: build a coordinator with given entity states."""
    config = {**BASE_CONFIG, **(config_overrides or {})}
    return HeatpumpCoordinator(make_hass(states), config)


# ---------------------------------------------------------------------------
# weighted_average_temperature
# ---------------------------------------------------------------------------


class TestWeightedAverageTemperature:
    def test_single_room(self):
        coord = coord_with_states(
            {"climate.living_room": make_state("heat", {"current_temperature": 19.0})},
            config_overrides={"rooms": [{"entity": "climate.living_room", "weight": 1.0}]},
        )
        assert coord.weighted_average_temperature == pytest.approx(19.0)

    def test_two_rooms_correct_weights(self):
        # living_room weight=2, bedroom weight=1
        # (19.0 * 2 + 22.0 * 1) / 3 = 60 / 3 = 20.0
        coord = coord_with_states({
            "climate.living_room": make_state("heat", {"current_temperature": 19.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 22.0}),
        })
        expected = (19.0 * 2 + 22.0 * 1) / 3
        assert coord.weighted_average_temperature == pytest.approx(expected)

    def test_unavailable_room_is_skipped(self):
        coord = coord_with_states({
            "climate.living_room": make_state("unavailable"),
            "climate.bedroom": make_state("heat", {"current_temperature": 21.0}),
        })
        assert coord.weighted_average_temperature == pytest.approx(21.0)

    def test_unknown_state_room_is_skipped(self):
        coord = coord_with_states({
            "climate.living_room": make_state("unknown"),
            "climate.bedroom": make_state("heat", {"current_temperature": 20.0}),
        })
        assert coord.weighted_average_temperature == pytest.approx(20.0)

    def test_all_rooms_unavailable_returns_none(self):
        coord = coord_with_states({
            "climate.living_room": make_state("unavailable"),
            "climate.bedroom": make_state("unknown"),
        })
        assert coord.weighted_average_temperature is None

    def test_missing_current_temperature_attribute_skipped(self):
        coord = coord_with_states({
            "climate.living_room": make_state("heat", {}),  # no current_temperature key
            "climate.bedroom": make_state("heat", {"current_temperature": 20.0}),
        })
        assert coord.weighted_average_temperature == pytest.approx(20.0)

    def test_entity_not_in_states_skipped(self):
        # living_room is absent from hass states entirely
        coord = coord_with_states({
            "climate.bedroom": make_state("heat", {"current_temperature": 20.0}),
        })
        assert coord.weighted_average_temperature == pytest.approx(20.0)

    def test_non_numeric_temperature_skipped(self):
        coord = coord_with_states({
            "climate.living_room": make_state("heat", {"current_temperature": "bad"}),
            "climate.bedroom": make_state("heat", {"current_temperature": 20.0}),
        })
        assert coord.weighted_average_temperature == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# is_heatpump_on
# ---------------------------------------------------------------------------


class TestIsHeatpumpOn:
    def test_switch_on(self):
        coord = coord_with_states({"switch.heatpump": make_state("on")})
        assert coord.is_heatpump_on is True

    def test_switch_off(self):
        coord = coord_with_states({"switch.heatpump": make_state("off")})
        assert coord.is_heatpump_on is False

    def test_switch_unavailable_returns_none(self):
        coord = coord_with_states({"switch.heatpump": make_state("unavailable")})
        assert coord.is_heatpump_on is None

    def test_switch_unknown_returns_none(self):
        coord = coord_with_states({"switch.heatpump": make_state("unknown")})
        assert coord.is_heatpump_on is None

    def test_switch_missing_returns_none(self):
        coord = coord_with_states({})
        assert coord.is_heatpump_on is None


# ---------------------------------------------------------------------------
# Cooldown
# ---------------------------------------------------------------------------


class TestCooldown:
    def test_no_last_switch_not_in_cooldown(self, coordinator):
        assert coordinator.in_cooldown is False
        assert coordinator.cooldown_remaining == pytest.approx(0.0)

    def test_recent_switch_in_cooldown(self, coordinator):
        coordinator._last_switch_time = NOW - timedelta(seconds=1800)  # 30 min ago; interval=3600
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            assert coordinator.in_cooldown is True
            assert coordinator.cooldown_remaining == pytest.approx(1800.0)

    def test_exactly_elapsed_not_in_cooldown(self, coordinator):
        coordinator._last_switch_time = NOW - timedelta(seconds=3600)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            assert coordinator.in_cooldown is False
            assert coordinator.cooldown_remaining == pytest.approx(0.0)

    def test_past_interval_not_in_cooldown(self, coordinator):
        coordinator._last_switch_time = NOW - timedelta(seconds=7200)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            assert coordinator.in_cooldown is False
            assert coordinator.cooldown_remaining == pytest.approx(0.0)

    def test_cooldown_remaining_never_negative(self, coordinator):
        coordinator._last_switch_time = NOW - timedelta(seconds=9999)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            assert coordinator.cooldown_remaining >= 0.0


# ---------------------------------------------------------------------------
# is_enabled / async_set_enabled
# ---------------------------------------------------------------------------


class TestEnabled:
    def test_is_enabled_defaults_to_true(self, coordinator):
        assert coordinator.is_enabled is True

    async def test_set_enabled_false_disables_and_turns_off_switch(self, coordinator):
        await coordinator.async_set_enabled(False)
        assert coordinator.is_enabled is False
        coordinator.hass.services.async_call.assert_awaited_once_with(
            "switch", "turn_off", {"entity_id": "switch.heatpump"}, blocking=False
        )

    async def test_set_enabled_true_enables_without_turning_off_switch(self, coordinator):
        coordinator._enabled = False
        await coordinator.async_set_enabled(True)
        assert coordinator.is_enabled is True
        coordinator.hass.services.async_call.assert_not_awaited()

    async def test_control_heatpump_skipped_when_disabled(self):
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0, "temperature": 22.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 22.0}),
            "switch.heatpump": make_state("off"),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        coord._enabled = False
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# _async_control_heatpump
# ---------------------------------------------------------------------------


class TestControlHeatpump:
    def _make(self, avg_temp, heatpump_on, last_switch_ago_s=None):
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": avg_temp, "temperature": 22.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": avg_temp, "temperature": 22.0}),
            "switch.heatpump": make_state("on" if heatpump_on else "off"),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        if last_switch_ago_s is not None:
            coord._last_switch_time = NOW - timedelta(seconds=last_switch_ago_s)
        return coord

    async def test_turns_on_below_threshold(self):
        # target=20, hysteresis_on=0.5 → turn on when avg < 19.5
        coord = self._make(avg_temp=19.0, heatpump_on=False)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord._async_control_heatpump()

        coord.hass.services.async_call.assert_awaited_once_with(
            "switch", "turn_on", {"entity_id": "switch.heatpump"}, blocking=False
        )
        assert coord._last_switch_time == NOW

    async def test_turns_off_above_threshold(self):
        # target=20, hysteresis_off=0.5 → turn off when avg > 20.5
        coord = self._make(avg_temp=21.0, heatpump_on=True)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord._async_control_heatpump()

        coord.hass.services.async_call.assert_awaited_once_with(
            "switch", "turn_off", {"entity_id": "switch.heatpump"}, blocking=False
        )
        assert coord._last_switch_time == NOW

    async def test_no_action_within_hysteresis_band(self):
        coord = self._make(avg_temp=20.0, heatpump_on=True)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_no_action_at_on_threshold_boundary(self):
        # avg == target - hysteresis_on → not strictly less than, no action
        coord = self._make(avg_temp=19.5, heatpump_on=False)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_no_action_at_off_threshold_boundary(self):
        # avg == target + hysteresis_off → not strictly greater than, no action
        coord = self._make(avg_temp=20.5, heatpump_on=True)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_cooldown_prevents_turn_on(self):
        coord = self._make(avg_temp=19.0, heatpump_on=False, last_switch_ago_s=1800)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_cooldown_prevents_turn_off(self):
        coord = self._make(avg_temp=21.0, heatpump_on=True, last_switch_ago_s=1800)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_elapsed_cooldown_allows_switch(self):
        coord = self._make(avg_temp=19.0, heatpump_on=False, last_switch_ago_s=3601)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_awaited()

    async def test_no_action_when_avg_unavailable(self):
        states = {
            "climate.living_room": make_state("unavailable"),
            "climate.bedroom": make_state("unavailable"),
            "switch.heatpump": make_state("off"),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_no_action_when_switch_unavailable(self):
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0}),
            "switch.heatpump": make_state("unavailable"),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_heatpump_already_on_does_not_double_switch(self):
        # avg is cold but heatpump is already ON → no action
        coord = self._make(avg_temp=19.0, heatpump_on=True)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_heatpump_already_off_does_not_double_switch(self):
        # avg is hot but heatpump is already OFF → no action
        coord = self._make(avg_temp=21.0, heatpump_on=False)
        await coord._async_control_heatpump()
        coord.hass.services.async_call.assert_not_awaited()


# ---------------------------------------------------------------------------
# _async_update_room_setpoints
# ---------------------------------------------------------------------------


class TestSetpointManagement:
    async def test_sets_rooms_to_target_plus_delta(self):
        # target=20.0, delta=2.0 → desired=22.0; rooms currently at 18.0
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0, "temperature": 18.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 18.0}),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_update_room_setpoints()

        assert coord.hass.services.async_call.await_count == 2
        calls = coord.hass.services.async_call.await_args_list
        entities_updated = {c.args[2]["entity_id"] for c in calls}
        assert entities_updated == {"climate.living_room", "climate.bedroom"}
        for c in calls:
            assert c.args[0] == "climate"
            assert c.args[1] == "set_temperature"
            assert c.args[2]["temperature"] == pytest.approx(22.0)

    async def test_skips_rooms_already_at_correct_setpoint(self):
        # Rooms are already at 22.0 (target=20 + delta=2) → no service calls
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0, "temperature": 22.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 22.0}),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_update_room_setpoints()
        coord.hass.services.async_call.assert_not_awaited()

    async def test_skips_unavailable_rooms(self):
        states = {
            "climate.living_room": make_state("unavailable"),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 18.0}),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_update_room_setpoints()

        assert coord.hass.services.async_call.await_count == 1
        assert coord.hass.services.async_call.await_args.args[2]["entity_id"] == "climate.bedroom"

    async def test_updates_room_with_missing_current_setpoint(self):
        # No "temperature" attribute → should still attempt to set it
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 22.0}),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        await coord._async_update_room_setpoints()

        assert coord.hass.services.async_call.await_count == 1
        assert coord.hass.services.async_call.await_args.args[2]["entity_id"] == "climate.living_room"

    async def test_setpoint_reflects_custom_delta(self):
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 19.0, "temperature": 18.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 19.0, "temperature": 18.0}),
        }
        config = {**BASE_CONFIG, "setpoint_delta": 3.0}  # target=20 + delta=3 → 23.0
        coord = HeatpumpCoordinator(make_hass(states), config)
        await coord._async_update_room_setpoints()

        for c in coord.hass.services.async_call.await_args_list:
            assert c.args[2]["temperature"] == pytest.approx(23.0)


# ---------------------------------------------------------------------------
# async_set_target_temperature
# ---------------------------------------------------------------------------


class TestSetTargetTemperature:
    async def test_updates_target_temperature(self, coordinator):
        with patch.object(coordinator, "async_evaluate", new_callable=AsyncMock):
            await coordinator.async_set_target_temperature(21.0)
        assert coordinator.target_temperature == pytest.approx(21.0)

    async def test_triggers_re_evaluation(self, coordinator):
        with patch.object(coordinator, "async_evaluate", new_callable=AsyncMock) as mock_eval:
            await coordinator.async_set_target_temperature(21.0)
        mock_eval.assert_awaited_once()

    async def test_new_setpoints_use_updated_target(self):
        # After changing target to 21.0, setpoints should be 21.0 + 2.0 = 23.0
        states = {
            "climate.living_room": make_state("heat", {"current_temperature": 20.0, "temperature": 22.0}),
            "climate.bedroom": make_state("heat", {"current_temperature": 20.0, "temperature": 22.0}),
            "switch.heatpump": make_state("on"),
        }
        coord = HeatpumpCoordinator(make_hass(states), BASE_CONFIG)
        with patch(f"{COORDINATOR_MODULE}.dt_util.utcnow", return_value=NOW):
            await coord.async_set_target_temperature(21.0)

        climate_calls = [
            c for c in coord.hass.services.async_call.await_args_list
            if c.args[0] == "climate"
        ]
        assert len(climate_calls) == 2
        for c in climate_calls:
            assert c.args[2]["temperature"] == pytest.approx(23.0)


# ---------------------------------------------------------------------------
# async_evaluate (integration)
# ---------------------------------------------------------------------------


class TestAsyncEvaluate:
    async def test_evaluate_calls_setpoints_and_control(self, coordinator):
        with (
            patch.object(coordinator, "_async_update_room_setpoints", new_callable=AsyncMock) as mock_setpoints,
            patch.object(coordinator, "_async_control_heatpump", new_callable=AsyncMock) as mock_control,
        ):
            await coordinator.async_evaluate()

        mock_setpoints.assert_awaited_once()
        mock_control.assert_awaited_once()

    async def test_evaluate_notifies_listeners(self, coordinator):
        notified = []
        coordinator.register_listener(lambda: notified.append(True))

        with (
            patch.object(coordinator, "_async_update_room_setpoints", new_callable=AsyncMock),
            patch.object(coordinator, "_async_control_heatpump", new_callable=AsyncMock),
        ):
            await coordinator.async_evaluate()

        assert len(notified) == 1


# ---------------------------------------------------------------------------
# Listeners
# ---------------------------------------------------------------------------


class TestListeners:
    def test_register_and_notify_single_listener(self, coordinator):
        called = []
        coordinator.register_listener(lambda: called.append(True))
        coordinator._notify_listeners()
        assert len(called) == 1

    def test_multiple_listeners_all_notified(self, coordinator):
        results = []
        coordinator.register_listener(lambda: results.append(1))
        coordinator.register_listener(lambda: results.append(2))
        coordinator._notify_listeners()
        assert results == [1, 2]

    def test_no_listeners_no_error(self, coordinator):
        coordinator._notify_listeners()  # should not raise
