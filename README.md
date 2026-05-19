# Lucknow Smart Residence — IoT Stack

Local-first IoT dashboard and automation stack for a 4-BHK G+1+T smart
self-sufficient residence in Lucknow, India.

**Platform:** Home Assistant (Docker on Apple Mac Mini M4)  
**Protocol:** KNX TP1 (wired) + MQTT (WiFi sensors) + Zigbee (fallback)  
**Principle:** Zero cloud dependency for any safety-critical function

---

## Six isolated subsystems

| System | Hardware | Dashboard |
|--------|----------|-----------|
| ☀️ PV + Battery (6 kWp / 12 kWh LFP) | Modbus TCP inverter + SDM630 meter | Power Flow Card |
| 💧 Rainwater Harvest (18,000 L tank) | ESP32 + MB7389 + YF-S201 flow meters | Tank gauge + valve controls |
| 🌬️ Beehive Passive Cooling | ESP32 + SHT31 + EC fans + Belimo dampers | Mode badge + ΔT readout |
| 🔒 Security (7 PoE cameras) | Frigate NVR + Konnected wired sensors | Camera grid + alarm panel |
| ⚙️ Central Console | Mac Mini A+B + ZKTeco fingerprint | Server health + access log |
| 🛗 Elevator Control | Dry-contact reed switches (brand-agnostic) | Floor indicator + call buttons |

---

## Quick start — dev / Windows (no hardware needed)

> Runs on any machine with Docker Desktop. No Mac Mini, no sensors, no cameras required.

```bash
git clone https://github.com/Sidharth-Asthana/lucknow-iot.git
cd lucknow-iot
bash scripts/setup.sh       # create volumes/ tree + write mosquitto.conf

# Start HA + Mosquitto only (Windows-compatible, no USB devices)
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Open HA, complete the onboarding wizard
start http://localhost:8123

# Feed all 6 subsystems with fake sensor data
scripts\simulate.bat                 # Windows
# bash scripts/simulate.sh           # Git Bash / WSL / macOS

# Test a specific scenario (triggers automations):
scripts\simulate.bat monsoon         # RH > 65% → bypass fires in 3 min
scripts\simulate.bat lowwater        # tank < 15% → valve cut alert
scripts\simulate.bat winter          # T < 18°C → winter bypass in 30 min
```

Watch automations fire in **HA → Settings → Automations** or **Logbook**.

---

## Production quick start (Mac Mini A)

```bash
cp .env.example .env        # fill in real passwords
bash scripts/setup.sh
docker compose up -d        # full stack: HA + Mosquitto + Frigate + Wiegand bridge
open http://10.0.0.10:8123
```

Then follow the full **Implementation checklist** in [`CLAUDE.md`](./CLAUDE.md).

---

## Architecture

```
Mac Mini A (10.0.0.10)               Mac Mini B (10.0.0.11)
┌─────────────────────────┐           ┌──────────────────────┐
│ Home Assistant :8123    │◄──────────│ Role: flexible       │
│ Mosquitto MQTT  :1883   │  LAN      │ (NVR / HA standby /  │
│ Frigate NVR     :5000   │           │  kiosk display)      │
│ KNX IP gateway          │           └──────────────────────┘
└──────────┬──────────────┘
           │
     ┌─────┼──────────────────┐
     │     │                  │
  Modbus  MQTT             KNX TP1
     │     │                  │
 Inverter ESP32s         KNX devices
 SDM630  (Beehive,RWH)  (lights,blinds)
```

---

## Claude Code integration

This repo contains a [`CLAUDE.md`](./CLAUDE.md) file — drop Claude Code
into this directory and it will read the spec, execute the checklist,
and implement or extend any subsystem automatically.

```bash
cd lucknow-iot
claude   # Claude Code reads CLAUDE.md and offers to implement
```

---

## Hardware procurement (India)

Total hardware cost (excl. PV panels, inverter, battery, KNX bus devices):
**~₹2,80,000**

See [iot.md §10](../iot.md#10-hardware-procurement-list) for the full
itemised list with Robu.in / Amazon.in sources.

---

## Connector recommendations

| Tool | Use case | Status |
|------|----------|--------|
| **Figma / FigJam** (MCP connected) | System architecture + IoT flow diagrams | ✅ Available now |
| **Wokwi** (browser) | ESP32 circuit simulation before hardware | 🌐 [wokwi.com](https://wokwi.com) |
| **KiCad 8** (local) | Proper schematic + PCB for custom boards | 🖥️ Free download |
| **draw.io** (browser/desktop) | Block diagrams + wiring schematics | 🌐 [drawio.com](https://drawio.com) |

---

## License

MIT — use freely for personal and commercial smart-home projects.
