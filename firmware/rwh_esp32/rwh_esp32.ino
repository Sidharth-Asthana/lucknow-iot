/**
 * rwh_esp32.ino
 * Lucknow Smart Residence — System 2: Rainwater Harvesting
 *
 * Hardware:
 *   - ESP32-WROOM-32 dev board
 *   - MaxBotix MB7389 ultrasonic level sensor
 *       (TTL serial, 9600 baud → ESP32 UART2 RX=GPIO16)
 *   - YF-S201 domestic flow meter (pulse, GPIO18, internal pull-up)
 *   - YF-S201 beehive flow meter  (pulse, GPIO19, internal pull-up)
 *   - Pump relay    (GPIO25, active HIGH → Shelly 2.5 dry contact override
 *                    OR direct relay to pump contactor)
 *   - Valve domestic relay (GPIO26, active HIGH → 24V solenoid valve)
 *   - Valve beehive relay  (GPIO27, active HIGH → 24V solenoid valve)
 *
 * Tank geometry (4 × 3 × 1.5 m):
 *   Max depth: 1.5 m (1500 mm). Sensor mounted at top of tank.
 *   Level % = (1500 - sensor_mm) / 1500 * 100
 *
 * Required libraries:
 *   - PubSubClient by Nick O'Leary
 *   - ArduinoJson by Benoit Blanchon
 *
 * Install:
 *   1. Add ESP32 board support in Arduino IDE
 *   2. Install libraries above
 *   3. Edit WIFI_SSID, WIFI_PASS, MQTT_SERVER below
 *   4. Upload, open Serial Monitor @ 115200 baud
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>

// ── Configuration ─────────────────────────────────────────────────────────────
#define WIFI_SSID       "LucknowHome_5G"
#define WIFI_PASS       "changeme"
#define MQTT_SERVER     "10.0.0.10"
#define MQTT_PORT       1883
#define MQTT_CLIENT_ID  "esp32_rwh"

// Tank physical parameters
#define TANK_DEPTH_MM   1500    // max measurable depth (mm)
#define FLOW_PULSE_PER_L 7.5f  // YF-S201: 7.5 pulses per litre

// ── Pin definitions ───────────────────────────────────────────────────────────
#define PIN_MB7389_RX   16      // UART2 RX ← MaxBotix TTL serial
#define PIN_FLOW_DOM    18      // YF-S201 domestic pulse
#define PIN_FLOW_BH     19      // YF-S201 beehive pulse
#define PIN_PUMP_RELAY  25      // Active HIGH → pump relay
#define PIN_VALVE_DOM   26      // Active HIGH → domestic solenoid valve
#define PIN_VALVE_BH    27      // Active HIGH → beehive solenoid valve

// ── MQTT topics ───────────────────────────────────────────────────────────────
#define TOPIC_LEVEL         "homeassistant/sensor/rwh/level"
#define TOPIC_FLOW_DOM      "homeassistant/sensor/rwh/flow_domestic"
#define TOPIC_FLOW_BH       "homeassistant/sensor/rwh/flow_beehive"

#define TOPIC_PUMP_STATE    "homeassistant/switch/rwh/pump/state"
#define TOPIC_VALVE_DOM_STATE "homeassistant/switch/rwh/valve_domestic/state"
#define TOPIC_VALVE_BH_STATE  "homeassistant/switch/rwh/valve_beehive/state"

// HA command subscriptions
#define TOPIC_PUMP_SET      "homeassistant/switch/rwh/pump/set"
#define TOPIC_VALVE_DOM_SET "homeassistant/switch/rwh/valve_domestic/set"
#define TOPIC_VALVE_BH_SET  "homeassistant/switch/rwh/valve_beehive/set"

// ── Globals ───────────────────────────────────────────────────────────────────
WiFiClient   wifiClient;
PubSubClient mqtt(wifiClient);
HardwareSerial MB7389(2);   // UART2 for MaxBotix sensor

// Flow pulse counters (ISR-safe)
volatile uint32_t pulseCountDom = 0;
volatile uint32_t pulseCountBH  = 0;

// Actuator state
bool pumpOn      = false;
bool valveDomOn  = false;
bool valveBHOn   = false;

// Publish timing
unsigned long lastPublish    = 0;
unsigned long lastFlowCalc   = 0;
const unsigned long PUBLISH_MS   = 15000;  // publish sensors every 15 s
const unsigned long FLOW_CALC_MS = 10000;  // flow rate window 10 s

// Flow rate (L/min)
float flowDomLpm = 0;
float flowBHLpm  = 0;

// ── ISRs (flow meter pulse counting) ─────────────────────────────────────────
void IRAM_ATTR isrDomFlow() { pulseCountDom++; }
void IRAM_ATTR isrBHFlow()  { pulseCountBH++;  }

// ── MaxBotix MB7389 read ─────────────────────────────────────────────────────
/**
 * MB7389 sends ASCII "R1234\r" (range in mm) at 9600 baud continuously.
 * We read one full frame and parse the integer.
 * Returns -1 on parse error.
 */
int readMB7389() {
  char buf[16] = {0};
  int i = 0;
  unsigned long t0 = millis();
  while (millis() - t0 < 500) {   // 500 ms timeout
    if (MB7389.available()) {
      char c = MB7389.read();
      if (c == 'R') { i = 0; }    // start of frame
      else if (c == '\r') {
        buf[i] = 0;
        int mm = atoi(buf);
        if (mm > 0 && mm < 9000) return mm;
        return -1;
      } else {
        if (i < (int)sizeof(buf) - 1) buf[i++] = c;
      }
    }
  }
  return -1;
}

// ── Actuator helpers ─────────────────────────────────────────────────────────
void setPump(bool on) {
  pumpOn = on;
  digitalWrite(PIN_PUMP_RELAY, on ? HIGH : LOW);
  mqtt.publish(TOPIC_PUMP_STATE, on ? "ON" : "OFF", true);
  Serial.printf("[Pump] %s\n", on ? "ON" : "OFF");
}

void setValveDom(bool on) {
  valveDomOn = on;
  digitalWrite(PIN_VALVE_DOM, on ? HIGH : LOW);
  mqtt.publish(TOPIC_VALVE_DOM_STATE, on ? "ON" : "OFF", true);
  Serial.printf("[ValveDom] %s\n", on ? "ON" : "OFF");
}

void setValveBH(bool on) {
  valveBHOn = on;
  digitalWrite(PIN_VALVE_BH, on ? HIGH : LOW);
  mqtt.publish(TOPIC_VALVE_BH_STATE, on ? "ON" : "OFF", true);
  Serial.printf("[ValveBH] %s\n", on ? "ON" : "OFF");
}

void publishFloat(const char* topic, float value, int decimals = 1) {
  StaticJsonDocument<64> doc;
  float factor = pow(10, decimals);
  doc["value"] = round(value * factor) / factor;
  char payload[64];
  serializeJson(doc, payload);
  mqtt.publish(topic, payload, true);
}

// ── MQTT callback ─────────────────────────────────────────────────────────────
void onMessage(char* topic, byte* payload, unsigned int length) {
  char msg[16] = {0};
  memcpy(msg, payload, min((size_t)length, sizeof(msg) - 1));
  Serial.printf("[MQTT] %s → %s\n", topic, msg);

  if (strcmp(topic, TOPIC_PUMP_SET) == 0) {
    setPump(strcmp(msg, "ON") == 0);
  } else if (strcmp(topic, TOPIC_VALVE_DOM_SET) == 0) {
    setValveDom(strcmp(msg, "ON") == 0);
  } else if (strcmp(topic, TOPIC_VALVE_BH_SET) == 0) {
    setValveBH(strcmp(msg, "ON") == 0);
  }
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); Serial.print(".");
  }
  Serial.printf("\n[WiFi] IP: %s\n", WiFi.localIP().toString().c_str());
}

// ── MQTT ──────────────────────────────────────────────────────────────────────
void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.printf("[MQTT] Connecting to %s ... ", MQTT_SERVER);
    if (mqtt.connect(MQTT_CLIENT_ID)) {
      Serial.println("OK");
      mqtt.subscribe(TOPIC_PUMP_SET);
      mqtt.subscribe(TOPIC_VALVE_DOM_SET);
      mqtt.subscribe(TOPIC_VALVE_BH_SET);
      // Republish current actuator state on reconnect
      mqtt.publish(TOPIC_PUMP_STATE,       pumpOn     ? "ON" : "OFF", true);
      mqtt.publish(TOPIC_VALVE_DOM_STATE,  valveDomOn ? "ON" : "OFF", true);
      mqtt.publish(TOPIC_VALVE_BH_STATE,   valveBHOn  ? "ON" : "OFF", true);
    } else {
      Serial.printf("failed rc=%d, retry 5s\n", mqtt.state());
      delay(5000);
    }
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n[Boot] RWH ESP32 node starting...");

  // Output pins — all off on boot
  pinMode(PIN_PUMP_RELAY, OUTPUT);  digitalWrite(PIN_PUMP_RELAY, LOW);
  pinMode(PIN_VALVE_DOM,  OUTPUT);  digitalWrite(PIN_VALVE_DOM,  LOW);
  pinMode(PIN_VALVE_BH,   OUTPUT);  digitalWrite(PIN_VALVE_BH,   LOW);

  // Flow meter inputs with pull-up
  pinMode(PIN_FLOW_DOM, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_DOM), isrDomFlow, FALLING);
  pinMode(PIN_FLOW_BH, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_FLOW_BH), isrBHFlow, FALLING);

  // MaxBotix UART2: RX=16, TX=17 (TX not used)
  MB7389.begin(9600, SERIAL_8N1, PIN_MB7389_RX, 17);

  connectWiFi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setKeepAlive(60);
  mqtt.setBufferSize(256);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  unsigned long now = millis();

  // ── Flow rate calculation (10 s window) ────────────────────────────────────
  if (now - lastFlowCalc >= FLOW_CALC_MS) {
    float dt_min = (now - lastFlowCalc) / 60000.0f;

    // Disable interrupts briefly to safely read volatile counters
    noInterrupts();
    uint32_t pDom = pulseCountDom;  pulseCountDom = 0;
    uint32_t pBH  = pulseCountBH;   pulseCountBH  = 0;
    interrupts();

    flowDomLpm = (pDom / FLOW_PULSE_PER_L) / dt_min;
    flowBHLpm  = (pBH  / FLOW_PULSE_PER_L) / dt_min;
    lastFlowCalc = now;
  }

  // ── Sensor publish (15 s interval) ────────────────────────────────────────
  if (now - lastPublish >= PUBLISH_MS) {
    lastPublish = now;

    // Level sensor
    int sensorMM = readMB7389();
    float levelPct = -1;
    if (sensorMM > 0) {
      // sensor at top of tank; closer reading → fuller tank
      levelPct = (1.0f - (float)sensorMM / TANK_DEPTH_MM) * 100.0f;
      levelPct = constrain(levelPct, 0.0f, 100.0f);
      publishFloat(TOPIC_LEVEL, levelPct);
    } else {
      Serial.println("[WARN] MB7389 read failed");
    }

    // Flow rates
    publishFloat(TOPIC_FLOW_DOM, flowDomLpm, 2);
    publishFloat(TOPIC_FLOW_BH,  flowBHLpm,  2);

    Serial.printf("[Sensors] Level=%.1f%% (%dmm) DomFlow=%.2fL/min BHFlow=%.2fL/min\n",
                  levelPct, sensorMM, flowDomLpm, flowBHLpm);
  }
}
