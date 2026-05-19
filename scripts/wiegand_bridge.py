"""
wiegand_bridge.py
Lucknow Smart Residence — System 5: Central Console Access Control

Reads Wiegand-26 frames from the ZKTeco SF100 fingerprint reader
(via a Wiegand→RS232 bridge board connected to Mac Mini A USB serial),
matches the card ID against a local SQLite database of enrolled users,
and publishes authentication results to Home Assistant via MQTT.

Physical wiring:
  ZKTeco SF100 Wiegand-26 DATA0/DATA1 → DFRobot serial bridge →
  RS232/USB adapter → Mac Mini A /dev/tty.usbserial-*

MQTT topics:
  Publish: homeassistant/lock/server_panel
           homeassistant/event/panel_access
  HA reads: lock.server_panel (LOCKED / UNLOCKED)

Auto-relock: RELOCK_DELAY_S seconds after unlock, relock published.
Access log:  /var/log/panel_access.log (or ./panel_access.log if /var/log
             is not writable — container-friendly fallback)

Install dependencies:
  pip3 install paho-mqtt pyserial

Run as macOS launchd service:
  1. Edit SERIAL_PORT and MQTT_HOST below (or set env vars)
  2. Copy to /usr/local/bin/wiegand_bridge.py
  3. Create /Library/LaunchDaemons/com.lucknow.wiegand_bridge.plist:
     <?xml version="1.0" encoding="UTF-8"?>
     <!DOCTYPE plist PUBLIC ...>
     <plist version="1.0"><dict>
       <key>Label</key><string>com.lucknow.wiegand_bridge</string>
       <key>ProgramArguments</key>
       <array><string>/usr/bin/python3</string>
              <string>/usr/local/bin/wiegand_bridge.py</string></array>
       <key>RunAtLoad</key><true/>
       <key>KeepAlive</key><true/>
       <key>StandardOutPath</key><string>/var/log/wiegand_bridge.log</string>
       <key>StandardErrorPath</key><string>/var/log/wiegand_bridge.log</string>
     </dict></plist>
  4. sudo launchctl load /Library/LaunchDaemons/com.lucknow.wiegand_bridge.plist

Docker run (inside docker-compose.yml):
  Configured as 'wiegand_bridge' service — see docker-compose.yml.
"""

import os
import json
import logging
import signal
import sqlite3
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import paho.mqtt.client as mqtt
import serial

# ── Configuration (override via environment variables) ───────────────────────
SERIAL_PORT   = os.getenv("SERIAL_PORT",   "/dev/tty.usbserial-Wiegand")
SERIAL_BAUD   = int(os.getenv("SERIAL_BAUD", "9600"))
MQTT_HOST     = os.getenv("MQTT_HOST",     "10.0.0.10")
MQTT_PORT     = int(os.getenv("MQTT_PORT", "1883"))
DB_PATH       = os.getenv("DB_PATH",       "./fingerprint_users.sqlite3")
RELOCK_DELAY  = int(os.getenv("RELOCK_DELAY_S", "5"))
LOG_PATH      = os.getenv("LOG_PATH",       "/var/log/panel_access.log")
MQTT_CLIENT_ID = "wiegand_bridge"

TOPIC_LOCK_STATE = "homeassistant/lock/server_panel"
TOPIC_LOCK_SET   = "homeassistant/lock/server_panel/set"
TOPIC_ACCESS_EVENT = "homeassistant/event/panel_access"

# ── Logging ───────────────────────────────────────────────────────────────────
log_path = Path(LOG_PATH)
try:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.touch()
    log_handler = logging.FileHandler(LOG_PATH)
except PermissionError:
    log_handler = logging.FileHandler("./panel_access.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[log_handler, logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("wiegand_bridge")

# ── SQLite user database ───────────────────────────────────────────────────────
def init_db(db_path: str) -> sqlite3.Connection:
    """
    Create the user database if it doesn't exist.
    Schema: users(card_id INTEGER PRIMARY KEY, name TEXT, enrolled_at TEXT)
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            card_id    INTEGER PRIMARY KEY,
            name       TEXT NOT NULL,
            enrolled_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            card_id    INTEGER,
            name       TEXT,
            granted    INTEGER,
            timestamp  TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    # Seed example users (edit or delete after first run)
    try:
        conn.execute("INSERT OR IGNORE INTO users (card_id, name) VALUES (1001, 'Primary Occupant')")
        conn.execute("INSERT OR IGNORE INTO users (card_id, name) VALUES (1002, 'Silk Artist')")
        conn.execute("INSERT OR IGNORE INTO users (card_id, name) VALUES (1003, 'Caretaker')")
        conn.commit()
    except sqlite3.Error:
        pass
    return conn


def lookup_user(conn: sqlite3.Connection, card_id: int) -> str | None:
    """Return user name if card_id is enrolled, else None."""
    cur = conn.execute("SELECT name FROM users WHERE card_id = ?", (card_id,))
    row = cur.fetchone()
    return row[0] if row else None


def log_access(conn: sqlite3.Connection, card_id: int, name: str | None, granted: bool):
    conn.execute(
        "INSERT INTO access_log (card_id, name, granted) VALUES (?, ?, ?)",
        (card_id, name or "unknown", int(granted)),
    )
    conn.commit()


# ── Wiegand-26 frame parser ───────────────────────────────────────────────────
def parse_wiegand26_frame(raw_bytes: bytes) -> tuple[int, int] | None:
    """
    Parse a 4-byte Wiegand-26 frame from the serial bridge.
    Frame format (DFRobot bridge output):
      Byte 0: 0xAA  (header)
      Byte 1: facility code (8-bit, upper bits of Wiegand data)
      Byte 2: card ID high byte
      Byte 3: card ID low byte
    Returns (facility_code, card_id) or None on invalid frame.

    NOTE: Actual serial bridge framing varies by manufacturer.
    This implementation assumes the DFRobot TEL0023 framing.
    Adjust FRAME_HEADER and byte ordering to match your bridge board.
    """
    FRAME_HEADER = 0xAA
    FRAME_LEN    = 4

    if len(raw_bytes) < FRAME_LEN:
        return None
    if raw_bytes[0] != FRAME_HEADER:
        return None

    facility = raw_bytes[1]
    card_id  = (raw_bytes[2] << 8) | raw_bytes[3]
    return facility, card_id


# ── MQTT client ───────────────────────────────────────────────────────────────
class MQTTBridge:
    def __init__(self):
        self.client = mqtt.Client(client_id=MQTT_CLIENT_ID, clean_session=True)
        self.client.on_connect    = self._on_connect
        self.client.on_message    = self._on_message
        self.client.on_disconnect = self._on_disconnect
        self._relock_timer: threading.Timer | None = None
        self._lock_state = "LOCKED"

    def connect(self):
        log.info("Connecting to MQTT broker %s:%d", MQTT_HOST, MQTT_PORT)
        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            log.info("MQTT connected")
            client.subscribe(TOPIC_LOCK_SET)
            # Publish current locked state on reconnect
            self.publish_lock_state("LOCKED")
        else:
            log.error("MQTT connection failed, rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc):
        log.warning("MQTT disconnected rc=%d, will auto-reconnect", rc)

    def _on_message(self, client, userdata, msg):
        """Handle manual lock/unlock commands from HA."""
        try:
            payload = json.loads(msg.payload.decode())
            state = payload.get("state", "").upper()
        except (json.JSONDecodeError, AttributeError):
            state = msg.payload.decode().upper()

        if state == "UNLOCKED":
            log.info("Manual unlock command received from HA")
            self.unlock(user="Manual (HA)")
        elif state == "LOCKED":
            self._cancel_relock()
            self.publish_lock_state("LOCKED")

    def unlock(self, user: str, card_id: int | None = None):
        """Publish unlock state and schedule auto-relock."""
        self._lock_state = "UNLOCKED"
        payload = json.dumps({
            "state": "UNLOCKED",
            "user": user,
            "card_id": card_id,
            "timestamp": datetime.now().isoformat(),
        })
        self.client.publish(TOPIC_LOCK_STATE, payload, retain=True)
        log.info("UNLOCKED for user '%s' (card %s)", user, card_id)

        # Also publish a transient event for HA logbook
        event_payload = json.dumps({
            "event_type": "access_granted",
            "user": user,
            "card_id": card_id,
        })
        self.client.publish(TOPIC_ACCESS_EVENT, event_payload)

        # Schedule auto-relock
        self._cancel_relock()
        self._relock_timer = threading.Timer(RELOCK_DELAY, self._auto_relock)
        self._relock_timer.daemon = True
        self._relock_timer.start()

    def deny(self, card_id: int):
        """Publish a denied access event."""
        payload = json.dumps({
            "event_type": "access_denied",
            "card_id": card_id,
            "timestamp": datetime.now().isoformat(),
        })
        self.client.publish(TOPIC_ACCESS_EVENT, payload)
        log.warning("ACCESS DENIED for unknown card %d", card_id)

    def _auto_relock(self):
        self.publish_lock_state("LOCKED")
        log.info("Auto-relock after %d s", RELOCK_DELAY)

    def _cancel_relock(self):
        if self._relock_timer and self._relock_timer.is_alive():
            self._relock_timer.cancel()

    def publish_lock_state(self, state: str):
        self._lock_state = state
        payload = json.dumps({"state": state})
        self.client.publish(TOPIC_LOCK_STATE, payload, retain=True)


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    db   = init_db(DB_PATH)
    bridge = MQTTBridge()
    bridge.connect()

    log.info("Opening serial port %s @ %d baud", SERIAL_PORT, SERIAL_BAUD)
    try:
        ser = serial.Serial(SERIAL_PORT, SERIAL_BAUD, timeout=2.0)
    except serial.SerialException as e:
        log.critical("Cannot open serial port: %s", e)
        sys.exit(1)

    log.info("Wiegand bridge running. Waiting for fingerprint scans...")

    # Graceful shutdown
    running = True
    def _shutdown(sig, frame):
        nonlocal running
        log.info("Shutting down...")
        running = False
    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    buf = bytearray()
    while running:
        try:
            byte = ser.read(1)
            if not byte:
                continue
            buf.extend(byte)

            # Scan buffer for valid 4-byte Wiegand frame starting with 0xAA
            while len(buf) >= 4:
                if buf[0] != 0xAA:
                    buf.pop(0)
                    continue

                frame = bytes(buf[:4])
                buf = buf[4:]

                result = parse_wiegand26_frame(frame)
                if result is None:
                    log.debug("Invalid frame: %s", frame.hex())
                    continue

                facility, card_id = result
                log.info("Wiegand-26 frame: facility=%d card_id=%d", facility, card_id)

                user = lookup_user(db, card_id)
                if user:
                    bridge.unlock(user=user, card_id=card_id)
                    log_access(db, card_id, user, granted=True)
                else:
                    bridge.deny(card_id)
                    log_access(db, card_id, None, granted=False)

        except serial.SerialException as e:
            log.error("Serial error: %s — retrying in 3 s", e)
            time.sleep(3)
            try:
                ser.close()
                ser.open()
            except serial.SerialException:
                pass

    ser.close()
    db.close()
    bridge.client.loop_stop()
    log.info("Wiegand bridge stopped.")


if __name__ == "__main__":
    main()
