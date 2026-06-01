#!/usr/bin/env python3
"""
Lucknow Smart Residence — MQTT Simulator
=========================================
Publishes continuous realistic sensor data to Mosquitto every SIM_INTERVAL seconds.
Run inside Docker (docker-compose.dev.yml) or standalone:

  pip install paho-mqtt
  python3 simulator.py

Environment variables:
  MQTT_HOST      broker hostname (default: localhost)
  MQTT_PORT      broker port     (default: 1883)
  SIM_INTERVAL   seconds between publishes (default: 10)

Topics simulated:
  homeassistant/sensor/rwh/{level,flow_domestic,flow_beehive}
  homeassistant/switch/rwh/{valve_domestic,valve_beehive}/state
  homeassistant/sensor/beehive/{indoor_temp,indoor_rh,outdoor_temp,outdoor_rh,inlet_temp,soil_e,soil_s}
  homeassistant/fan/beehive/fan_{e,s}/{state,speed}
  homeassistant/switch/beehive/damper_{e,s}/state
  homeassistant/lock/server_panel
"""

import os
import json
import time
import math
import random

import paho.mqtt.client as mqtt

# ── Config ─────────────────────────────────────────────────────────────────────
MQTT_HOST     = os.environ.get("MQTT_HOST",    "localhost")
MQTT_PORT     = int(os.environ.get("MQTT_PORT",    "1883"))
SIM_INTERVAL  = int(os.environ.get("SIM_INTERVAL", "10"))

# ── Persistent state ────────────────────────────────────────────────────────────
state = {
    "rwh_level":    65.0,   # % (18 kL tank, starts at 65%)
    "soil_e":       60.0,   # % (beehive-E panel moisture)
    "soil_s":       60.0,   # % (beehive-S panel moisture)
    "battery_soc":  60.0,   # % (12 kWh LFP)
    "tick":         0,
}


# ── Sensor models ───────────────────────────────────────────────────────────────

def _noise(scale=0.03):
    return 1.0 + random.uniform(-scale, scale)


def solar_power_w(h):
    """Bell curve: 0 W before 6am/after 6pm, 5800 W at noon. h = fractional hour."""
    if h < 6.0 or h > 18.0:
        return 0.0
    x = (h - 12.0) / 5.5
    return max(0.0, 5800.0 * (1.0 - x * x) * _noise(0.05))


def outdoor_temp_c(h):
    """Lucknow summer: 31°C pre-dawn → 42°C at 14:00."""
    # cosine-based diurnal: min at 5am, max at 2pm
    phase = (h - 5.0) / 24.0 * 2.0 * math.pi
    return 36.5 + 5.5 * math.cos(phase - math.pi) + random.gauss(0, 0.3)


def outdoor_rh_pct(h):
    """45% RH at noon, 65% overnight."""
    phase = (h - 5.0) / 24.0 * 2.0 * math.pi
    return 55.0 - 10.0 * math.cos(phase - math.pi) + random.gauss(0, 1.0)


def inlet_temp_c(outdoor):
    """Beehive evaporative cooling: ~14°C ΔT at design conditions."""
    delta = min(14.0, max(6.0, outdoor - 28.0))
    return max(20.0, outdoor - delta + random.gauss(0, 0.3))


def indoor_temp_c(inlet):
    """Living space: 1–2°C above inlet (internal gains)."""
    return inlet + random.uniform(1.0, 2.0)


def indoor_rh_pct(outdoor_rh):
    """Cooled air: ~15% lower RH than outdoor (evaporation removed water)."""
    return max(30.0, outdoor_rh - 15.0 + random.gauss(0, 2.0))


def fan_speed_pct(outdoor, inlet):
    """EC fan speed proportional to cooling delta (0→14°C maps to 20→100%)."""
    delta = max(0.0, outdoor - inlet)
    speed = 20.0 + (delta / 14.0) * 80.0
    return round(min(100.0, max(20.0, speed)), 0)


# ── Publish helpers ─────────────────────────────────────────────────────────────

def pub(client, topic, payload, retain=True):
    if isinstance(payload, (dict, list)):
        payload = json.dumps(payload)
    client.publish(topic, str(payload), retain=retain)


# ── Simulate one tick ────────────────────────────────────────────────────────────

def simulate(client):
    t   = state["tick"]
    now = time.localtime()
    h   = now.tm_hour + now.tm_min / 60.0

    # ─ Environment ─────────────────────────────────────────────────────────────
    out_t   = outdoor_temp_c(h)
    out_rh  = outdoor_rh_pct(h)
    inlet_t = inlet_temp_c(out_t)
    in_t    = indoor_temp_c(inlet_t)
    in_rh   = indoor_rh_pct(out_rh)

    # ─ PV & battery ────────────────────────────────────────────────────────────
    pv_w    = solar_power_w(h)
    load_w  = 1200.0 + random.gauss(0, 150.0)  # household baseload
    net_w   = pv_w - load_w

    bsoc = state["battery_soc"]
    if pv_w > 500:                              # daytime: charge
        bsoc = min(100.0, bsoc + 0.04)
    else:                                       # night: discharge
        bsoc = max(5.0,   bsoc - 0.025)
    state["battery_soc"] = bsoc

    grid_import_w = max(0.0, -net_w + random.gauss(0, 40))
    grid_export_w = max(0.0,  net_w + random.gauss(0, 40))

    # ─ RWH ─────────────────────────────────────────────────────────────────────
    state["rwh_level"] = max(5.0, state["rwh_level"] - 0.18)
    if state["rwh_level"] < 18.0:
        state["rwh_level"] = min(95.0, state["rwh_level"] + 30.0)  # rain/refill

    rwh_ok      = state["rwh_level"] > 10.0
    flow_dom    = round(random.uniform(9.0, 14.0),  2) if rwh_ok else 0.0
    flow_beehive= round(random.uniform(2.5,  4.5),  2) if rwh_ok and state["rwh_level"] > 15 else 0.0

    # ─ Soil moisture ────────────────────────────────────────────────────────────
    for key in ("soil_e", "soil_s"):
        state[key] = max(15.0, state[key] - 0.4)
        if state[key] < 22.0:
            state[key] = min(70.0, state[key] + 45.0)  # drip irrigation

    # ─ Cooling control ─────────────────────────────────────────────────────────
    monsoon_bypass = in_rh > 65.0
    damper_state   = "OFF" if monsoon_bypass else "ON"
    fan_state      = "OFF" if monsoon_bypass else "ON"
    fs             = fan_speed_pct(out_t, inlet_t) if fan_state == "ON" else 0.0

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLISH — RWH ESP32
    # ═══════════════════════════════════════════════════════════════════════════
    pub(client, "homeassistant/sensor/rwh/level",        {"value": round(state["rwh_level"], 1)})
    pub(client, "homeassistant/sensor/rwh/flow_domestic",{"value": flow_dom})
    pub(client, "homeassistant/sensor/rwh/flow_beehive", {"value": flow_beehive})
    pub(client, "homeassistant/switch/rwh/valve_domestic/state", "ON" if flow_dom    > 0 else "OFF")
    pub(client, "homeassistant/switch/rwh/valve_beehive/state",  "ON" if flow_beehive > 0 else "OFF")

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLISH — Beehive ESP32
    # ═══════════════════════════════════════════════════════════════════════════
    pub(client, "homeassistant/sensor/beehive/indoor_temp",  {"value": round(in_t,    1)})
    pub(client, "homeassistant/sensor/beehive/indoor_rh",    {"value": round(in_rh,   1)})
    pub(client, "homeassistant/sensor/beehive/outdoor_temp", {"value": round(out_t,   1)})
    pub(client, "homeassistant/sensor/beehive/outdoor_rh",   {"value": round(out_rh,  1)})
    pub(client, "homeassistant/sensor/beehive/inlet_temp",   {"value": round(inlet_t, 1)})
    pub(client, "homeassistant/sensor/beehive/soil_e",       {"value": round(state["soil_e"], 1)})
    pub(client, "homeassistant/sensor/beehive/soil_s",       {"value": round(state["soil_s"], 1)})
    pub(client, "homeassistant/fan/beehive/fan_e/state",     fan_state)
    pub(client, "homeassistant/fan/beehive/fan_e/speed",     str(int(fs)))
    pub(client, "homeassistant/fan/beehive/fan_s/state",     fan_state)
    pub(client, "homeassistant/fan/beehive/fan_s/speed",     str(int(fs)))
    pub(client, "homeassistant/switch/beehive/damper_e/state", damper_state)
    pub(client, "homeassistant/switch/beehive/damper_s/state", damper_state)

    # ═══════════════════════════════════════════════════════════════════════════
    # PUBLISH — Server panel lock
    # ═══════════════════════════════════════════════════════════════════════════
    if t % 180 == 30:  # access event ~every 30 min
        user = random.choice(["Admin", "Resident_1", "Resident_2", "Guest"])
        pub(client, "homeassistant/lock/server_panel",
            {"state": "UNLOCKED", "user": user, "time": time.strftime("%H:%M")})
        time.sleep(2)
        pub(client, "homeassistant/lock/server_panel",
            {"state": "LOCKED",   "user": user, "time": time.strftime("%H:%M")})
    else:
        pub(client, "homeassistant/lock/server_panel",
            {"state": "LOCKED",   "user": "Admin", "time": time.strftime("%H:%M")})

    state["tick"] += 1

    print(
        f"[{time.strftime('%H:%M:%S')}] "
        f"PV={pv_w:5.0f}W  SOC={bsoc:4.1f}%  "
        f"OutT={out_t:4.1f}°C  InT={in_t:4.1f}°C  "
        f"RH={in_rh:3.0f}%  RWH={state['rwh_level']:4.1f}%  "
        f"Fan={fs:3.0f}%  {'[BYPASS]' if monsoon_bypass else ''}",
        flush=True,
    )


# ── Main ─────────────────────────────────────────────────────────────────────────

def main():
    client = mqtt.Client(client_id="lucknow_simulator", protocol=mqtt.MQTTv311)

    connected = [False]

    def on_connect(c, userdata, flags, rc):
        if rc == 0:
            connected[0] = True
            print(f"[SIM] Connected to MQTT {MQTT_HOST}:{MQTT_PORT}", flush=True)
        else:
            print(f"[SIM] Connection failed rc={rc}", flush=True)

    def on_disconnect(c, userdata, rc):
        connected[0] = False
        if rc != 0:
            print(f"[SIM] Unexpected disconnect rc={rc}", flush=True)

    client.on_connect    = on_connect
    client.on_disconnect = on_disconnect

    print(f"[SIM] Starting — broker={MQTT_HOST}:{MQTT_PORT}  interval={SIM_INTERVAL}s",
          flush=True)

    while True:
        try:
            client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
            client.loop_start()

            # Wait for connection
            for _ in range(30):
                if connected[0]:
                    break
                time.sleep(0.5)

            if not connected[0]:
                raise ConnectionError("Could not connect to broker")

            while connected[0]:
                simulate(client)
                time.sleep(SIM_INTERVAL)

        except Exception as exc:
            print(f"[SIM] Error: {exc} — retrying in 15s", flush=True)
            try:
                client.loop_stop()
                client.disconnect()
            except Exception:
                pass
            time.sleep(15)


if __name__ == "__main__":
    main()
