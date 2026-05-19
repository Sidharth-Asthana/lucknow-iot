#!/usr/bin/env bash
# simulate.sh — Feed fake sensor data to MQTT for all 6 subsystems.
# Run this while the dev stack is up to populate the HA dashboard without hardware.
#
# Usage:
#   bash scripts/simulate.sh              # one-shot: publish current values
#   bash scripts/simulate.sh --loop       # continuous: re-publish every 15s
#   bash scripts/simulate.sh --scenario monsoon  # trigger specific scenario
#
# Requires: mosquitto_pub (apt install mosquitto-clients / brew install mosquitto)
# Or use the Mosquitto Docker container:
#   docker exec -it mosquitto mosquitto_pub -h localhost ...
#
set -euo pipefail

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
LOOP=false
SCENARIO="${2:-normal}"

[[ "${1:-}" == "--loop"     ]] && LOOP=true
[[ "${1:-}" == "--scenario" ]] && SCENARIO="${2:-normal}"

# ── Helper ────────────────────────────────────────────────────────────────────
pub() {
  local topic="$1"
  local payload="$2"
  # Try native mosquitto_pub first; fall back to Docker exec
  if command -v mosquitto_pub &>/dev/null; then
    mosquitto_pub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$topic" -m "$payload" -r
  else
    docker exec mosquitto mosquitto_pub -h localhost -p 1883 -t "$topic" -m "$payload" -r
  fi
}

# ── Scenario parameters ───────────────────────────────────────────────────────
case "$SCENARIO" in
  monsoon)
    # Triggers cooling_monsoon_bypass_on after 3 min
    OUTDOOR_TEMP=32; OUTDOOR_RH=80
    INDOOR_TEMP=29;  INDOOR_RH=72   # above 65% bypass threshold
    INLET_TEMP=28
    SOIL_E=55;       SOIL_S=60
    TANK_LEVEL=70
    PV_POWER=2400;   BATT_SOC=88
    echo "▶  Scenario: MONSOON — indoor RH 72% will trigger bypass in ~3 min"
    ;;
  winter)
    # Triggers cooling_winter_bypass_on after 30 min
    OUTDOOR_TEMP=12; OUTDOOR_RH=45
    INDOOR_TEMP=18;  INDOOR_RH=40
    INLET_TEMP=13
    SOIL_E=20;       SOIL_S=18      # dry — will also trigger drip
    TANK_LEVEL=85
    PV_POWER=900;    BATT_SOC=60
    echo "▶  Scenario: WINTER — outdoor T 12°C will trigger winter bypass in ~30 min"
    ;;
  lowwater)
    # Triggers rwh_beehive_valve_cut
    OUTDOOR_TEMP=44; OUTDOOR_RH=30
    INDOOR_TEMP=34;  INDOOR_RH=40
    INLET_TEMP=30
    SOIL_E=15;       SOIL_S=12
    TANK_LEVEL=10                   # below 15% — beehive valve cuts + alert
    PV_POWER=5500;   BATT_SOC=98
    echo "▶  Scenario: LOW WATER — tank 10% will cut beehive valve + send alert"
    ;;
  *)
    # Normal summer afternoon in Lucknow
    OUTDOOR_TEMP=44; OUTDOOR_RH=35
    INDOOR_TEMP=31;  INDOOR_RH=52
    INLET_TEMP=30
    SOIL_E=35;       SOIL_S=42
    TANK_LEVEL=68
    PV_POWER=4200;   BATT_SOC=76
    echo "▶  Scenario: NORMAL — hot summer afternoon, cooling mode active"
    ;;
esac

publish_all() {
  local ts
  ts=$(date +%T)
  echo ""
  echo "[$ts] Publishing sensor data → mqtt://$MQTT_HOST:$MQTT_PORT"

  # ── System 1: PV + Battery ──────────────────────────────────────────────────
  echo "  ☀️  PV: ${PV_POWER}W | Battery: ${BATT_SOC}%"
  pub "homeassistant/sensor/pv/power_w"        "{\"value\": $PV_POWER}"
  pub "homeassistant/sensor/pv/battery_soc"    "{\"value\": $BATT_SOC}"
  pub "homeassistant/sensor/pv/grid_import_w"  "{\"value\": 0}"
  pub "homeassistant/sensor/pv/grid_export_w"  "{\"value\": $(( PV_POWER > 3000 ? PV_POWER - 3000 : 0 ))}"
  pub "homeassistant/sensor/pv/daily_kwh"      "{\"value\": 18.4}"

  # ── System 2: Rainwater Harvest ──────────────────────────────────────────────
  echo "  💧 Tank: ${TANK_LEVEL}% | Domestic flow: 3.2 L/min"
  pub "homeassistant/sensor/rwh/level"          "{\"value\": $TANK_LEVEL}"
  pub "homeassistant/sensor/rwh/domestic_flow"  "{\"value\": 3.2}"
  pub "homeassistant/sensor/rwh/beehive_flow"   "{\"value\": 1.8}"
  pub "homeassistant/sensor/rwh/daily_domestic" "{\"value\": 320}"
  pub "homeassistant/sensor/rwh/daily_beehive"  "{\"value\": 85}"

  # ── System 3: Beehive Cooling ────────────────────────────────────────────────
  local delta
  delta=$(echo "$OUTDOOR_TEMP - $INLET_TEMP" | bc)
  local fan_pct
  fan_pct=$(echo "scale=0; v = $delta * 100 / 14; if (v > 100) v = 100; if (v < 20) v = 20; v" | bc)
  echo "  🌬️  Outdoor: ${OUTDOOR_TEMP}°C / ${OUTDOOR_RH}% RH | Indoor: ${INDOOR_TEMP}°C / ${INDOOR_RH}% RH | ΔT: ${delta}°C | Fan: ${fan_pct}%"
  pub "homeassistant/sensor/beehive/outdoor_temp" "{\"value\": $OUTDOOR_TEMP}"
  pub "homeassistant/sensor/beehive/outdoor_rh"   "{\"value\": $OUTDOOR_RH}"
  pub "homeassistant/sensor/beehive/indoor_temp"  "{\"value\": $INDOOR_TEMP}"
  pub "homeassistant/sensor/beehive/indoor_rh"    "{\"value\": $INDOOR_RH}"
  pub "homeassistant/sensor/beehive/inlet_temp"   "{\"value\": $INLET_TEMP}"
  pub "homeassistant/sensor/beehive/soil_e"       "{\"value\": $SOIL_E}"
  pub "homeassistant/sensor/beehive/soil_s"       "{\"value\": $SOIL_S}"
  # Report actuator state (ESP32 would normally publish these on reconnect)
  pub "homeassistant/fan/beehive/fan_e/state"     "ON"
  pub "homeassistant/fan/beehive/fan_e/speed"     "$fan_pct"
  pub "homeassistant/fan/beehive/fan_s/state"     "ON"
  pub "homeassistant/fan/beehive/fan_s/speed"     "$fan_pct"
  pub "homeassistant/switch/beehive/damper_e/state" "ON"
  pub "homeassistant/switch/beehive/damper_s/state" "ON"

  # ── System 4: Security ───────────────────────────────────────────────────────
  echo "  🔒 Alarm: armed_home | All zones: clear"
  pub "homeassistant/alarm_control_panel/lucknow/state" "armed_home"
  # Simulate all 8 PIR zones clear
  for i in $(seq 1 8); do
    pub "homeassistant/binary_sensor/pir_zone_${i}/state" "off"
  done
  # Simulate 4 IR beam zones clear
  for i in $(seq 1 4); do
    pub "homeassistant/binary_sensor/ir_beam_${i}/state"  "off"
  done

  # ── System 5: Central Console ────────────────────────────────────────────────
  echo "  ⚙️  Panel: locked | Mac Mini A: CPU 8% RAM 4.2 GB"
  pub "homeassistant/lock/server_panel"               "{\"state\": \"LOCKED\"}"
  pub "homeassistant/sensor/console/cpu_pct_a"        "{\"value\": 8}"
  pub "homeassistant/sensor/console/ram_gb_a"         "{\"value\": 4.2}"
  pub "homeassistant/sensor/console/cpu_temp_a"       "{\"value\": 42}"
  pub "homeassistant/sensor/ups/battery_charge"       "{\"value\": 100}"
  pub "homeassistant/sensor/ups/status"               "{\"value\": \"OL\"}"

  # ── System 6: Elevator ───────────────────────────────────────────────────────
  echo "  🛗  Elevator: Ground floor | Door: closed | No fault"
  pub "homeassistant/binary_sensor/elevator_floor_g/state"  "on"
  pub "homeassistant/binary_sensor/elevator_floor_f1/state" "off"
  pub "homeassistant/binary_sensor/elevator_floor_t/state"  "off"
  pub "homeassistant/binary_sensor/elevator_door/state"     "off"
  pub "homeassistant/binary_sensor/elevator_fault/state"    "off"

  echo ""
  echo "  ✅ All topics published. Check HA → Developer Tools → States"
}

# ── Run ───────────────────────────────────────────────────────────────────────
if $LOOP; then
  echo "Continuous mode — publishing every 15s. Ctrl+C to stop."
  while true; do
    publish_all
    sleep 15
  done
else
  publish_all
fi
