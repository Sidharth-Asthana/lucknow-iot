# Lucknow Smart Residence — IoT Stack

> **Auto-implementation spec for Claude Code.**  
> When you open this repo, read this file fully, then execute
> the **Implementation checklist** below in order.
> Commands marked **[dev]** run on any machine with Docker Desktop (Windows/Mac/Linux).
> Commands marked **[prod]** are Mac Mini A (macOS 14+) production only.

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
# [dev] Any machine — only Docker Desktop required for local testing
# Install: https://www.docker.com/products/docker-desktop/

# [prod] Mac Mini A (10.0.0.10) — full production stack
brew install docker python3
pip3 install paho-mqtt pyserial   # for wiegand_bridge.py
# Arduino IDE 2.x with ESP32 board support (for firmware)
```

---

## Compose file layout

Three compose files — always use the right overlay:

| Scenario | Command |
|----------|---------|
| **Local dev / Windows** (no hardware) | `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d` |
| **Mac Mini A production** (with USB devices) | `docker compose -f docker-compose.yml -f docker-compose.hw.yml up -d` |

`docker-compose.dev.yml` — no device passthrough; replaces Frigate + Wiegand bridge with no-op busybox containers; uses explicit port mapping (works on Windows Docker Desktop).  
`docker-compose.hw.yml` — adds USB device paths for ConBee II, SDM630, Wiegand serial; sets `network_mode: host` for KNX multicast.

---

## Development commands

```bash
# 1. [dev] First-time setup — create Docker volume tree + copy configs
bash scripts/setup.sh      # macOS/Linux
# Windows: run manually (see setup.sh for the mkdir + cp commands)

# 2. [dev] Start dev stack (no hardware required)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 3. [dev] Verify services
curl -s http://localhost:8123/api/     # Home Assistant → {"message":"API running."}
# Frigate is a busybox no-op in dev — skip

# 4. [dev] Simulate sensors — inject fake MQTT data (no ESP32 needed)
bash scripts/simulate.sh               # macOS/Linux
scripts\simulate.bat                   # Windows
# Scenarios: normal | monsoon | winter | lowwater
scripts\simulate.bat monsoon

# 5. [dev] Test scenarios from the dashboard
#    HA → Test Lab tab → click any scenario button
#    (calls script.scenario_* which publishes MQTT internally — no terminal needed)

# 6. [prod] Flash ESP32 firmware (repeat for each node)
#    Open firmware/beehive_esp32/beehive_esp32.ino in Arduino IDE
#    Select board: ESP32 Dev Module → Upload

# 7. [prod] Run fingerprint bridge as macOS service
sudo cp scripts/com.lucknow.wiegand_bridge.plist \
    /Library/LaunchDaemons/
sudo launchctl load \
    /Library/LaunchDaemons/com.lucknow.wiegand_bridge.plist

# 8. [dev/prod] Lovelace dashboard — loaded automatically from file
#    configuration.yaml sets lovelace: mode: yaml
#    HA reads volumes/ha_config/ui-lovelace.yaml on every refresh
#    No Raw Config Editor needed. After editing dashboard/lovelace.yaml:
cp dashboard/lovelace.yaml volumes/ha_config/ui-lovelace.yaml
#    Then refresh the browser — no HA restart required.
```

---

## File map

```
iot/
├── CLAUDE.md                     ← you are here
├── README.md                     ← human-readable overview
├── docker-compose.yml            ← base stack: HA + Mosquitto + Frigate + Wiegand
├── docker-compose.dev.yml        ← [dev] Windows/local override (no hardware)
├── docker-compose.hw.yml         ← [prod] Mac Mini A hardware overlay (USB devices)
├── scripts/
│   ├── setup.sh                  ← first-time volume + config init
│   ├── simulate.sh               ← inject fake MQTT sensor data (macOS/Linux)
│   ├── simulate.bat              ← inject fake MQTT sensor data (Windows)
│   ├── wiegand_bridge.py         ← fingerprint reader → MQTT service
│   └── com.lucknow.wiegand_bridge.plist  ← macOS launchd plist
├── ha_config/
│   ├── configuration.yaml        ← HA main config; lovelace: mode: yaml
│   ├── modbus.yaml               ← PV inverter + SDM630 grid meter registers
│   ├── mqtt_sensors.yaml         ← ESP32 sensor/switch/fan/lock entities
│   ├── scripts.yaml              ← 8 test scenario scripts (MQTT inject via HA)
│   └── automations/
│       ├── cooling_bypass.yaml   ← 4-mode cooling state machine
│       ├── rwh_pump.yaml         ← level-based pump + valve control
│       ├── security_alerts.yaml  ← PIR/Frigate → floodlights + notifications
│       └── elevator.yaml         ← fault alerts + call-relay pulses
├── dashboard/
│   └── lovelace.yaml             ← 9-view interactive Lovelace dashboard
│                                    Views: Overview · Energy · Water · Cooling ·
│                                           Security · Systems · Automations ·
│                                           Test Lab · Guide
├── frigate/
│   └── config.yml                ← 7-camera NVR (RTSP + detect zones)
└── firmware/
    ├── beehive_esp32/
    │   └── beehive_esp32.ino     ← SHT31×2, DS18B20, VH400×2, EC fans, dampers
    └── rwh_esp32/
        └── rwh_esp32.ino         ← MB7389 level, YF-S201 flow×2, pump+valves
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

Run these steps in order. **[dev]** = works on any machine. **[prod]** = Mac Mini A only.

### Phase 1 — Dev environment (any machine)

- [ ] **1. Clone repo** `[dev]`  
      `git clone https://github.com/Sidharth-Asthana/lucknow-iot.git && cd lucknow-iot`
- [ ] **2. Set secrets** `[dev]`  
      Copy `.env.example` → `.env`, set a strong `FRIGATE_RTSP_PASSWORD`
- [ ] **3. Run setup** `[dev]` (macOS/Linux only — Windows: run commands manually from setup.sh)  
      `bash scripts/setup.sh`  
      Verify: `ls volumes/` shows `ha_config/ mosquitto/ frigate/ wiegand/`
- [ ] **4. Start dev stack** `[dev]`  
      `docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d`  
      Verify: HA at `http://localhost:8123`, Mosquitto at `:1883`
- [ ] **5. HA onboarding** `[dev]`  
      Complete first-run wizard at `http://localhost:8123`  
      Location: Lucknow (26.85°N, 80.95°E), timezone: Asia/Kolkata
- [ ] **6. Copy HA config to volumes** `[dev]`  
      `cp -r ha_config/. volumes/ha_config/`  
      `cp dashboard/lovelace.yaml volumes/ha_config/ui-lovelace.yaml`  
      `docker compose -f docker-compose.yml -f docker-compose.dev.yml restart homeassistant`
- [ ] **7. Add MQTT integration** `[dev]`  
      HA → Settings → Devices & Services → + Add Integration → MQTT  
      Broker: `mosquitto` · Port: `1883` → Submit → Finish  
      *(no username/password — anonymous on LAN)*
- [ ] **8. Verify dashboard** `[dev]`  
      Refresh `http://localhost:8123` — 9 tabs should appear  
      Click **Test Lab** → **🌞 Normal Summer** → check sensor values populate in Water + Cooling tabs
- [ ] **9. Install HACS (optional — for full card styling)** `[dev]`  
      Follow https://hacs.xyz/docs/setup/download  
      Install: `power-flow-card-plus`, `mini-graph-card`, `button-card`,  
      `mushroom-cards`, `apexcharts-card`, `frigate-hass-card`

### Phase 2 — Production hardware (Mac Mini A)

- [ ] **10. Switch to hardware stack** `[prod]`  
      `docker compose -f docker-compose.yml -f docker-compose.hw.yml up -d`  
      Verify device paths: `ls /dev/tty.usbserial*` (ConBee II, SDM630, Wiegand)
- [ ] **11. Flash ESP32 nodes** `[prod]`  
      Edit WiFi + MQTT credentials in each `.ino` file first  
      Arduino IDE → select board ESP32 Dev Module → Upload (× 2)  
      Verify: sensors in HA → Developer Tools → States
- [ ] **12. Configure hardware integrations via HA UI** `[prod]`  
      KNX: Settings → Integrations → KNX → Tunneling → `10.0.0.20:3671`  
      Konnected #1: + Add → Konnected → IP `10.0.0.30`  
      Konnected #2: + Add → Konnected → IP `10.0.0.31`  
      NUT/UPS: + Add → Network UPS Tools → host `localhost`
- [ ] **13. Add cameras to Frigate** `[prod]`  
      Edit `volumes/frigate/config/config.yml` with real camera IPs/creds  
      (`frigate/config.yml` uses env var `FRIGATE_RTSP_PASSWORD`)  
      Verify: Frigate UI `http://localhost:5000` shows all 7 streams
- [ ] **14. Set inverter static IP** `[prod]`  
      Assign `10.0.0.40`, verify: `mbpoll -t 3 -r 40083 10.0.0.40`
- [ ] **15. Wire fingerprint reader** `[prod]`  
      `ls /dev/tty.usbserial*` → update `SERIAL_PORT` in `.env`  
      Test: `python3 scripts/wiegand_bridge.py` → scan finger → check MQTT  
      `mosquitto_sub -h localhost -t "homeassistant/lock/panel/#" -v`
- [ ] **16. Install launchd service** `[prod]`  
      `sudo cp scripts/com.lucknow.wiegand_bridge.plist /Library/LaunchDaemons/`  
      `sudo launchctl load /Library/LaunchDaemons/com.lucknow.wiegand_bridge.plist`
- [ ] **17. Smoke test automations** `[prod]`  
      Dashboard → Test Lab → 🌧️ Monsoon Bypass  
      HA → Logbook: confirm `automation.cooling_monsoon_bypass` fires within 3 min
- [ ] **18. Arm security** `[prod]`  
      Arm in `armed_away` mode → trigger a PIR zone  
      Confirm: siren entity → ON, floodlights → ON, push notification fires

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
