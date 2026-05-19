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

## Quick start

```bash
git clone https://github.com/Sidharth-Asthana/lucknow-iot.git
cd lucknow-iot
cp .env.example .env        # fill in your passwords
bash scripts/setup.sh       # init Docker volumes + copy configs
docker compose up -d        # start HA + Mosquitto + Frigate
open http://localhost:8123  # complete HA onboarding
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
