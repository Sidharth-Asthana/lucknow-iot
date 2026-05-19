#!/usr/bin/env bash
# setup.sh — First-time Docker volume init + config copy
# Run from the repo root: bash scripts/setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VOLS="$REPO_ROOT/volumes"

echo "==> Lucknow IoT Stack — first-time setup"
echo "    Repo: $REPO_ROOT"
echo ""

# ── 1. Create Docker volume directories ────────────────────────────────────────
echo "[1/5] Creating Docker volume directories..."
mkdir -p \
  "$VOLS/ha_config" \
  "$VOLS/mosquitto/config" \
  "$VOLS/mosquitto/data" \
  "$VOLS/mosquitto/log" \
  "$VOLS/frigate/config" \
  "$VOLS/frigate/media" \
  "$VOLS/wiegand"
echo "      ✓ volumes/ tree created"

# ── 2. Copy HA config + dashboard ─────────────────────────────────────────────
echo "[2/5] Copying Home Assistant config..."
cp -r "$REPO_ROOT/ha_config/." "$VOLS/ha_config/"
# Lovelace YAML mode: HA reads ui-lovelace.yaml directly from config dir
cp "$REPO_ROOT/dashboard/lovelace.yaml" "$VOLS/ha_config/ui-lovelace.yaml"
echo "      ✓ ha_config/ → volumes/ha_config/"
echo "      ✓ dashboard/lovelace.yaml → volumes/ha_config/ui-lovelace.yaml"

# ── 3. Copy Frigate config ────────────────────────────────────────────────────
echo "[3/5] Copying Frigate config..."
cp "$REPO_ROOT/frigate/config.yml" "$VOLS/frigate/config/config.yml"
echo "      ✓ frigate/config.yml → volumes/frigate/config/config.yml"

# ── 4. Generate Mosquitto config ──────────────────────────────────────────────
echo "[4/5] Writing Mosquitto config..."
cat > "$VOLS/mosquitto/config/mosquitto.conf" << 'EOF'
# Mosquitto MQTT broker — Lucknow Smart Residence
# LAN-only, no TLS (add TLS if exposing beyond local network)

listener 1883 0.0.0.0
listener 9001 0.0.0.0
protocol websockets

# Allow anonymous on LAN (tighten with password_file for production)
allow_anonymous true

persistence true
persistence_location /mosquitto/data/

log_dest file /mosquitto/log/mosquitto.log
log_dest stdout
log_type all

# Keep-alive 60 s — matches ESP32 firmware setting
max_keepalive 120
EOF
echo "      ✓ Mosquitto config written"

# ── 5. Load .env if present ───────────────────────────────────────────────────
echo "[5/5] Checking .env..."
if [[ -f "$REPO_ROOT/.env" ]]; then
  echo "      ✓ .env found — secrets will be loaded by docker compose"
else
  echo "      ⚠️  No .env found — copy .env.example to .env and set passwords"
  cat > "$REPO_ROOT/.env.example" << 'EOF'
# Rename to .env before running docker compose up
FRIGATE_RTSP_PASSWORD=change_me_strong
WIEGAND_DB_PATH=/data/fingerprint_users.sqlite3
RELOCK_DELAY_S=5
SERIAL_PORT=/dev/ttyUSB2
SERIAL_BAUD=9600
MQTT_HOST=mosquitto
MQTT_PORT=1883
TZ=Asia/Kolkata
EOF
  echo "      .env.example created — fill it in and rename to .env"
fi

echo ""
echo "==> Setup complete! Next steps:"
echo "    1. Edit .env with real passwords"
echo "    2. docker compose up -d"
echo "    3. Open http://localhost:8123 to complete HA onboarding"
echo "    4. Follow the checklist in CLAUDE.md"
