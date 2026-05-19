# Lucknow Smart Residence — IoT Stack

> **Auto-implementation spec for Claude Code.**  
> When you open this repo, read this file fully, then execute
> the **Implementation checklist** below in order.
> Every command is runnable as-is on a Mac Mini running macOS 14+.

---

## Project summary

Local-first IoT dashboard for a 4-BHK smart residence in Lucknow, India.
**Six isolated subsystems**, each with its own circuit, firmware, and HA
integration — all wired through a Home Assistant (Docker) core on Mac Mini A.
Zero cloud dependency for any safety-critical function.

| Subsystem | Hardware bridge | HA integration |
|-----------|----------------|----------------|
| PV + Battery | Modbus TCP (inverter) + RS485 (SDM630) | `modbus` |
| Rainwater harvest | ESP32 → MQTT | `mqtt` |
| Beehive cooling | ESP32 → MQTT | `mqtt` + `fan` |
| Security (7 cameras) | Frigate NVR + Konnected | `frigate` + `konnected` |
| Central console | Fingerprint → Wiegand → serial | custom MQTT bridge |
| Elevator | Dry-contact → Konnected | `konnected` |

---

## Prerequisites

```bash
# On Mac Mini A (10.0.0.10):
brew install docker          # or install Docker Desktop
brew install python3
pip3 install paho-mqtt pyserial   # for wiegand_bridge.py
# Arduino IDE 2.x with ESP32 board support (for firmware)
```

---

## Development commands

```bash
# 1. First-time setup — create Docker volume tree + copy configs
bash scripts/setup.sh

# 2. Start the full stack
docker compose up -d

# 3. Verify services are up
curl -s http://localhost:8123/api/ | head -c 80    # Home Assistant
curl -s http://localhost:5000/api/version          # Frigate
mosquitto_sub -h localhost -t "#" -v &             # MQTT wildcard

# 4. Flash ESP32 firmware (repeat for each node)
#    Open firmware/beehive_esp32/beehive_esp32.ino in Arduino IDE
#    Select board: ESP32 Dev Module → Upload

# 5. Run fingerprint bridge (development / test)
python3 scripts/wiegand_bridge.py

# 6. Run fingerprint bridge as macOS service (production)
sudo cp scripts/com.lucknow.wiegand_bridge.plist \
    /Library/LaunchDaemons/
sudo launchctl load \
    /Library/LaunchDaemons/com.lucknow.wiegand_bridge.plist

# 7. Load Lovelace dashboard
#    HA → Settings → Dashboards → Edit → Raw Config Editor
#    Paste contents of dashboard/lovelace.yaml

# 8. Simulate MQTT sensor (smoke test without hardware)
mosquitto_pub -h localhost -t homeassistant/sensor/rwh/level \
    -m '{"value":65}'
mosquitto_pub -h localhost -t homeassistant/sensor/beehive/indoor_rh \
    -m '{"value":70}'
```

---

## File map

```
iot/
├── CLAUDE.md                   ← you are here
├── README.md                   ← human-readable overview
├── docker-compose.yml          ← Mac Mini A: HA + Mosquitto + Frigate
├── scripts/
│   ├── setup.sh                ← first-time volume + config init
│   ├── wiegand_bridge.py       ← fingerprint reader → MQTT service
│   └── com.lucknow.wiegand_bridge.plist  ← macOS launchd plist
├── ha_config/
│   ├── configuration.yaml      ← HA main config (KNX, Konnected, NUT, helpers)
│   ├── modbus.yaml             ← PV inverter + SDM630 grid meter registers
│   ├── mqtt_sensors.yaml       ← ESP32 sensor/switch/fan/lock entities
│   └── automations/
│       ├── cooling_bypass.yaml ← 4-mode cooling state machine
│       ├── rwh_pump.yaml       ← level-based pump + valve control
│       ├── security_alerts.yaml← PIR/Frigate → floodlights + notifications
│       └── elevator.yaml       ← fault alerts + call-relay pulses
├── dashboard/
│   └── lovelace.yaml           ← 7-view interactive Lovelace dashboard
├── frigate/
│   └── config.yml              ← 7-camera NVR (RTSP + detect zones)
└── firmware/
    ├── beehive_esp32/
    │   └── beehive_esp32.ino   ← SHT31×2, DS18B20, VH400×2, EC fans, dampers
    └── rwh_esp32/
        └── rwh_esp32.ino       ← MB7389 level, YF-S201 flow×2, pump+valves
```

---

## Network addresses (assign as static DHCP leases)

| Device | IP | Notes |
|--------|-----|-------|
| Mac Mini A | `10.0.0.10` | HA server |
| Mac Mini B | `10.0.0.11` | Flexible role |
| KNX IP Router (Weinzierl 750) | `10.0.0.20` | KNX gateway |
| Konnected Pro #1 (security) | `10.0.0.30` | PIR + IR zones |
| Konnected Pro #2 (elevator) | `10.0.0.31` | Reed switches |
| Hybrid inverter | `10.0.0.40` | Modbus TCP :502 |
| Cameras (gate…garage) | `10.0.0.101–107` | PoE |
| ESP32 Beehive node | `10.0.0.50` | DHCP via MQTT ID |
| ESP32 RWH node | `10.0.0.51` | DHCP via MQTT ID |

---

## Secrets to set before first run

Create `iot/.env` (gitignored):

```bash
FRIGATE_RTSP_PASSWORD=changeme_strong_password
HA_TRUSTED_PROXY=10.0.0.0/24
MQTT_PASSWORD=                  # leave blank for LAN-only; add auth for production
WIEGAND_DB_PATH=/data/fingerprint_users.sqlite3
```

Update `docker-compose.yml` to load from `.env` if adding MQTT auth.

---

## Implementation checklist

Run these steps in order. Each step has a ✅ you can mark when done.

- [ ] **1. Clone repo** — `git clone <repo-url> && cd iot`
- [ ] **2. Set secrets** — create `.env` with real passwords above
- [ ] **3. Run setup** — `bash scripts/setup.sh`  
      Verify: `ls volumes/` shows `ha_config/ mosquitto/ frigate/ wiegand/`
- [ ] **4. Start stack** — `docker compose up -d`  
      Verify: HA at `http://localhost:8123`, Frigate at `http://localhost:5000`
- [ ] **5. HA onboarding** — complete the HA first-run wizard  
      Set location: Lucknow (26.85°N, 80.95°E), timezone Asia/Kolkata
- [ ] **6. Copy HA config** — copy `ha_config/` into the HA config volume,  
      then: `docker compose restart homeassistant`
- [ ] **7. Install HACS** — follow https://hacs.xyz/docs/setup/download  
      Install cards: `power-flow-card-plus`, `mini-graph-card`, `button-card`,  
      `mushroom-cards`, `apexcharts-card`, `frigate-hass-card`
- [ ] **8. Load Lovelace** — paste `dashboard/lovelace.yaml` into Raw Config Editor
- [ ] **9. Flash ESP32 nodes** — beehive + RWH (edit WiFi/MQTT creds first)  
      Verify: sensors appear in HA → Developer Tools → States
- [ ] **10. Configure Konnected panels** — add to HA via Integrations page  
      Set static IPs: 10.0.0.30, 10.0.0.31
- [ ] **11. Add cameras to Frigate** — set camera IPs 10.0.0.101–107  
      Verify: Frigate UI shows all 7 streams
- [ ] **12. Set inverter static IP** — assign 10.0.0.40, verify Modbus  
      Test: `mbpoll -t 3 -r 40083 10.0.0.40`
- [ ] **13. Wire fingerprint reader** — plug USB, verify port:  
      `ls /dev/tty.usbserial*`, update `SERIAL_PORT` in `.env`  
      Run: `python3 scripts/wiegand_bridge.py` — scan finger, check MQTT
- [ ] **14. Install launchd service** — `bash scripts/install_service.sh`
- [ ] **15. Smoke test automations** — simulate RH=70% via MQTT,  
      confirm dampers close within 30 s in HA → Logbook
- [ ] **16. Arm security** — arm in `armed_away`, trigger a PIR zone,  
      confirm siren + floodlights + push notification fire

---

## Architecture decisions

- **No cloud for core** — HA runs fully local; internet is optional
- **MQTT as universal bus** — ESP32 nodes, Frigate, and fingerprint bridge
  all speak MQTT; HA is the single consumer
- **KNX TP1 = hardwired backbone** for lights/blinds; Zigbee = fallback
- **Konnected panels** bridge traditional wired alarm sensors to HA natively
- **Frigate over cloud cameras** — all video stays local; 30-day NVR on-disk
- **Wiegand-26 fingerprint** — biometric stored on reader chip only,
  not transmitted or stored on Mac Mini
- **Dry-contact elevator** — brand-agnostic; works with any controller
  that exposes NO/NC dry contacts

---

## Extending this spec

To add a new subsystem:
1. Add hardware table + Mermaid circuit to the relevant section in `../iot.md`
2. Add MQTT sensor/switch entities to `ha_config/mqtt_sensors.yaml`
3. Add automation YAML to `ha_config/automations/`
4. Add a new Lovelace view to `dashboard/lovelace.yaml`
5. Update the checklist above
6. Commit with message: `feat(systems): add <system-name>`
