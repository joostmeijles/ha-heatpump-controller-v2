# ha-heatpump-controller-v2

A Home Assistant custom integration that controls a heatpump based on a weighted average temperature derived from multiple climate entities.

This is a v2 of [ha-heatpump-controller](https://github.com/joostmeijles/ha-heatpump-controller), simplified and extended with:
- Minimum switch interval (cooldown) to protect the heatpump compressor
- Active setpoint management — room setpoints are always kept at `target + delta` to keep all valves open and make efficient use of the buffer
- Hysteresis-based on/off control

---

## How It Works

On every state change of any watched entity (and every 60 seconds as a fallback), the controller:

1. Calculates the **weighted average temperature** across all configured rooms.
2. Sets all room climate entity setpoints to `target_temperature + setpoint_delta`.
3. Evaluates whether to switch the heatpump on or off:

```
Turn ON  when: avg < target - hysteresis_on  AND heatpump is off AND cooldown elapsed
Turn OFF when: avg > target + hysteresis_off AND heatpump is on  AND cooldown elapsed
```

### Setpoint Management

Room setpoints are **always** maintained at `target + setpoint_delta`, regardless of whether the heatpump is running. This ensures:
- All TRVs/zone valves stay open so warm buffer water is distributed efficiently.
- No single room blocks flow by closing its valve.
- If a room overheats (e.g. from sunlight), its thermostat still closes naturally once it exceeds `target + delta`.

---

## Installation

1. Copy `custom_components/heatpump_controller/` into your HA `config/custom_components/` directory.
2. Add the configuration below to your `configuration.yaml`.
3. Restart Home Assistant.

---

## Configuration

```yaml
heatpump_controller:
  on_off_switch: switch.heatpump_power      # Switch entity controlling the heatpump
  initial_target_temperature: 20.5          # Initial setpoint in °C (adjustable via UI)
  hysteresis_on: 0.5                        # Turn ON when avg < target - this value
  hysteresis_off: 0.5                       # Turn OFF when avg > target + this value
  min_switch_interval: 3600                 # Minimum seconds between state changes
  setpoint_delta: 2.0                       # Room setpoints kept at target + this delta
  rooms:
    - entity: climate.living_room           # Climate entity (reads temp + sets setpoint)
      weight: 1.5                           # Weight proportional to room size
    - entity: climate.bedroom
      weight: 1.0
```

### Options

| Key | Required | Default | Description |
|---|---|---|---|
| `on_off_switch` | yes | — | Entity ID of the switch controlling the heatpump |
| `initial_target_temperature` | no | `20.0` | Starting target temperature in °C |
| `hysteresis_on` | no | `0.5` | Degrees below target to trigger heating |
| `hysteresis_off` | no | `0.5` | Degrees above target to stop heating |
| `min_switch_interval` | no | `3600` | Cooldown in seconds between switches |
| `setpoint_delta` | no | `2.0` | Offset added to target for room setpoints |
| `rooms[].entity` | yes | — | Climate entity ID for the room |
| `rooms[].weight` | yes | — | Relative weight in the average (e.g. room size) |

---

## Entities

After setup, the following entities are created:

| Entity | Type | Description |
|---|---|---|
| `climate.heatpump_controller` | Climate | Adjustable target temperature; current temp = weighted average; mode = heat/off |
| `sensor.heatpump_controller_weighted_average_temperature` | Sensor | Current weighted average of all room temperatures (°C) |
| `sensor.heatpump_controller_cooldown_remaining` | Sensor | Seconds until the next switch is allowed |
| `binary_sensor.heatpump_controller_active` | Binary sensor | Mirrors the state of the heatpump switch |
| `binary_sensor.heatpump_controller_in_cooldown` | Binary sensor | True while the cooldown period is active |

The target temperature on `climate.heatpump_controller` is persisted across restarts and can be adjusted from the HA UI or via automations.

---

## Logging

Set the log level for detailed debug output:

```yaml
logger:
  logs:
    custom_components.heatpump_controller: debug
```
