/**
 * beehive_esp32.ino
 * Lucknow Smart Residence — System 3: Beehive Passive Cooling
 *
 * Hardware:
 *   - ESP32-WROOM-32 dev board
 *   - SHT31-D indoor  (I2C addr 0x44, GPIO21=SDA, GPIO22=SCL)
 *   - SHT31-D outdoor (I2C addr 0x45, same bus)
 *   - DS18B20 inlet duct temp (1-Wire, GPIO4, 4.7kΩ pull-up to 3.3V)
 *   - Vegetronix VH400 soil moisture E (0–3V analog, GPIO34)
 *   - Vegetronix VH400 soil moisture S (0–3V analog, GPIO35)
 *   - EC fan E speed (0–10V via DAC, GPIO25 → op-amp 0–10V output)
 *   - EC fan S speed (0–10V via DAC, GPIO26 → op-amp 0–10V output)
 *   - Damper E relay (GPIO32, active HIGH → 24V transformer → Belimo LMQ24A)
 *   - Damper S relay (GPIO33, active HIGH → 24V transformer)
 *
 * Required libraries (install via Arduino IDE Library Manager):
 *   - PubSubClient by Nick O'Leary     (MQTT)
 *   - Adafruit SHT31 Library           (SHT31 sensor)
 *   - Adafruit Unified Sensor          (dependency)
 *   - OneWire by Paul Stoffregen       (DS18B20 bus)
 *   - DallasTemperature by Miles Burton (DS18B20)
 *   - ArduinoJson by Benoit Blanchon   (JSON payloads)
 *
 * Install:
 *   1. Open Arduino IDE, add ESP32 board support (Espressif boards manager)
 *   2. Install libraries above
 *   3. Edit WIFI_SSID, WIFI_PASS, MQTT_SERVER below
 *   4. Upload to ESP32, open Serial Monitor @ 115200 baud
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <Wire.h>
#include <Adafruit_SHT31.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <ArduinoJson.h>

// ── Configuration ────────────────────────────────────────────────────────────
#define WIFI_SSID      "LucknowHome_5G"
#define WIFI_PASS      "changeme"
#define MQTT_SERVER    "10.0.0.10"
#define MQTT_PORT      1883
#define MQTT_CLIENT_ID "esp32_beehive"
#define NODE_NAME      "beehive"

// ── Pin definitions ──────────────────────────────────────────────────────────
#define PIN_ONE_WIRE    4       // DS18B20 data
#define PIN_FAN_E_DAC  25       // DAC output → op-amp → 0–10V EC fan E
#define PIN_FAN_S_DAC  26       // DAC output → op-amp → 0–10V EC fan S
#define PIN_DAMPER_E   32       // Relay for damper E (active HIGH)
#define PIN_DAMPER_S   33       // Relay for damper S (active HIGH)
#define PIN_SOIL_E     34       // ADC: VH400 soil moisture E (0–3V)
#define PIN_SOIL_S     35       // ADC: VH400 soil moisture S (0–3V)

// ── MQTT topic paths ─────────────────────────────────────────────────────────
#define TOPIC_INDOOR_TEMP   "homeassistant/sensor/beehive/indoor_temp"
#define TOPIC_INDOOR_RH     "homeassistant/sensor/beehive/indoor_rh"
#define TOPIC_OUTDOOR_TEMP  "homeassistant/sensor/beehive/outdoor_temp"
#define TOPIC_OUTDOOR_RH    "homeassistant/sensor/beehive/outdoor_rh"
#define TOPIC_INLET_TEMP    "homeassistant/sensor/beehive/inlet_temp"
#define TOPIC_SOIL_E        "homeassistant/sensor/beehive/soil_e"
#define TOPIC_SOIL_S        "homeassistant/sensor/beehive/soil_s"

#define TOPIC_FAN_E_STATE   "homeassistant/fan/beehive/fan_e/state"
#define TOPIC_FAN_E_SPEED   "homeassistant/fan/beehive/fan_e/speed"
#define TOPIC_FAN_S_STATE   "homeassistant/fan/beehive/fan_s/state"
#define TOPIC_FAN_S_SPEED   "homeassistant/fan/beehive/fan_s/speed"
#define TOPIC_DAMPER_E_STATE "homeassistant/switch/beehive/damper_e/state"
#define TOPIC_DAMPER_S_STATE "homeassistant/switch/beehive/damper_s/state"

// HA command subscriptions
#define TOPIC_FAN_E_SET     "homeassistant/fan/beehive/fan_e/set"
#define TOPIC_FAN_E_SPEED_SET "homeassistant/fan/beehive/fan_e/speed_set"
#define TOPIC_FAN_S_SET     "homeassistant/fan/beehive/fan_s/set"
#define TOPIC_FAN_S_SPEED_SET "homeassistant/fan/beehive/fan_s/speed_set"
#define TOPIC_DAMPER_E_SET  "homeassistant/switch/beehive/damper_e/set"
#define TOPIC_DAMPER_S_SET  "homeassistant/switch/beehive/damper_s/set"

// ── Globals ───────────────────────────────────────────────────────────────────
WiFiClient         wifiClient;
PubSubClient       mqtt(wifiClient);
Adafruit_SHT31     sht31_indoor;
Adafruit_SHT31     sht31_outdoor;
OneWire            oneWire(PIN_ONE_WIRE);
DallasTemperature  ds18b20(&oneWire);

unsigned long lastPublish = 0;
const unsigned long PUBLISH_INTERVAL_MS = 15000;  // publish every 15 s

// Current actuator state
uint8_t fanE_pct = 0;       // 0–100
uint8_t fanS_pct = 0;
bool    damperE_open = false;
bool    damperS_open = false;

// ── Helpers ───────────────────────────────────────────────────────────────────

/**
 * Convert a fan percentage (0–100) to ESP32 DAC value (0–255).
 * DAC output feeds an op-amp that scales 0–3.3V → 0–10V for the EC fan.
 */
uint8_t pctToDac(uint8_t pct) {
  return (uint8_t)((uint32_t)pct * 255 / 100);
}

/**
 * Read VH400 soil moisture: ADC counts → volts → % saturation.
 * VH400 output: 0.0V = 0% VWC, 3.0V = 100% VWC (volumetric water content).
 */
float readSoilMoisture(uint8_t adcPin) {
  int raw = analogRead(adcPin);
  float voltage = raw * 3.3f / 4095.0f;
  float vwc = (voltage / 3.0f) * 100.0f;
  return constrain(vwc, 0.0f, 100.0f);
}

void publishSensor(const char* topic, float value, int decimals = 1) {
  StaticJsonDocument<64> doc;
  doc["value"] = round(value * pow(10, decimals)) / pow(10, decimals);
  char payload[64];
  serializeJson(doc, payload);
  mqtt.publish(topic, payload, true);   // retain=true so HA always has a value
}

void setFan(uint8_t pin, uint8_t pct, const char* state_topic,
            const char* speed_topic) {
  dacWrite(pin, pctToDac(pct));
  mqtt.publish(state_topic, pct > 0 ? "ON" : "OFF", true);
  char spd[8];
  snprintf(spd, sizeof(spd), "%d", pct);
  mqtt.publish(speed_topic, spd, true);
}

void setDamper(uint8_t relayPin, bool open,
               const char* state_topic) {
  digitalWrite(relayPin, open ? HIGH : LOW);
  mqtt.publish(state_topic, open ? "ON" : "OFF", true);
}

// ── MQTT callback (commands from HA) ─────────────────────────────────────────
void onMessage(char* topic, byte* payload, unsigned int length) {
  char msg[64] = {0};
  memcpy(msg, payload, min((size_t)length, sizeof(msg) - 1));
  Serial.printf("[MQTT] %s → %s\n", topic, msg);

  if (strcmp(topic, TOPIC_FAN_E_SET) == 0) {
    bool on = (strcmp(msg, "ON") == 0);
    fanE_pct = on ? max((int)fanE_pct, 20) : 0;
    setFan(PIN_FAN_E_DAC, fanE_pct, TOPIC_FAN_E_STATE, TOPIC_FAN_E_SPEED);

  } else if (strcmp(topic, TOPIC_FAN_E_SPEED_SET) == 0) {
    fanE_pct = (uint8_t)constrain(atoi(msg), 0, 100);
    setFan(PIN_FAN_E_DAC, fanE_pct, TOPIC_FAN_E_STATE, TOPIC_FAN_E_SPEED);

  } else if (strcmp(topic, TOPIC_FAN_S_SET) == 0) {
    bool on = (strcmp(msg, "ON") == 0);
    fanS_pct = on ? max((int)fanS_pct, 20) : 0;
    setFan(PIN_FAN_S_DAC, fanS_pct, TOPIC_FAN_S_STATE, TOPIC_FAN_S_SPEED);

  } else if (strcmp(topic, TOPIC_FAN_S_SPEED_SET) == 0) {
    fanS_pct = (uint8_t)constrain(atoi(msg), 0, 100);
    setFan(PIN_FAN_S_DAC, fanS_pct, TOPIC_FAN_S_STATE, TOPIC_FAN_S_SPEED);

  } else if (strcmp(topic, TOPIC_DAMPER_E_SET) == 0) {
    damperE_open = (strcmp(msg, "ON") == 0);
    setDamper(PIN_DAMPER_E, damperE_open, TOPIC_DAMPER_E_STATE);

  } else if (strcmp(topic, TOPIC_DAMPER_S_SET) == 0) {
    damperS_open = (strcmp(msg, "ON") == 0);
    setDamper(PIN_DAMPER_S, damperS_open, TOPIC_DAMPER_S_STATE);
  }
}

// ── WiFi ──────────────────────────────────────────────────────────────────────
void connectWiFi() {
  Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] Connected, IP: %s\n", WiFi.localIP().toString().c_str());
}

// ── MQTT ──────────────────────────────────────────────────────────────────────
void connectMQTT() {
  while (!mqtt.connected()) {
    Serial.printf("[MQTT] Connecting to %s:%d ... ", MQTT_SERVER, MQTT_PORT);
    if (mqtt.connect(MQTT_CLIENT_ID)) {
      Serial.println("connected");
      // Subscribe to all command topics
      mqtt.subscribe(TOPIC_FAN_E_SET);
      mqtt.subscribe(TOPIC_FAN_E_SPEED_SET);
      mqtt.subscribe(TOPIC_FAN_S_SET);
      mqtt.subscribe(TOPIC_FAN_S_SPEED_SET);
      mqtt.subscribe(TOPIC_DAMPER_E_SET);
      mqtt.subscribe(TOPIC_DAMPER_S_SET);
      // Republish current state on reconnect
      setFan(PIN_FAN_E_DAC, fanE_pct, TOPIC_FAN_E_STATE, TOPIC_FAN_E_SPEED);
      setFan(PIN_FAN_S_DAC, fanS_pct, TOPIC_FAN_S_STATE, TOPIC_FAN_S_SPEED);
      setDamper(PIN_DAMPER_E, damperE_open, TOPIC_DAMPER_E_STATE);
      setDamper(PIN_DAMPER_S, damperS_open, TOPIC_DAMPER_S_STATE);
    } else {
      Serial.printf("failed (rc=%d), retry in 5s\n", mqtt.state());
      delay(5000);
    }
  }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  Serial.println("\n[Boot] Beehive ESP32 node starting...");

  // Output pins
  pinMode(PIN_DAMPER_E, OUTPUT);
  pinMode(PIN_DAMPER_S, OUTPUT);
  digitalWrite(PIN_DAMPER_E, LOW);
  digitalWrite(PIN_DAMPER_S, LOW);

  // DAC pins — start fans stopped
  dacWrite(PIN_FAN_E_DAC, 0);
  dacWrite(PIN_FAN_S_DAC, 0);

  // ADC resolution
  analogReadResolution(12);

  // I2C sensors
  Wire.begin(21, 22);   // SDA=21, SCL=22
  if (!sht31_indoor.begin(0x44)) {
    Serial.println("[ERROR] SHT31 indoor not found at 0x44");
  }
  if (!sht31_outdoor.begin(0x45)) {
    Serial.println("[ERROR] SHT31 outdoor not found at 0x45");
  }

  // DS18B20
  ds18b20.begin();
  ds18b20.setResolution(12);

  connectWiFi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setCallback(onMessage);
  mqtt.setKeepAlive(60);
  mqtt.setBufferSize(512);
}

// ── Loop ──────────────────────────────────────────────────────────────────────
void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Reconnecting...");
    connectWiFi();
  }
  if (!mqtt.connected()) {
    connectMQTT();
  }
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastPublish >= PUBLISH_INTERVAL_MS) {
    lastPublish = now;

    // ── SHT31 indoor ────────────────────────────────────────────────────────
    float t_indoor = sht31_indoor.readTemperature();
    float rh_indoor = sht31_indoor.readHumidity();
    if (!isnan(t_indoor)) {
      publishSensor(TOPIC_INDOOR_TEMP, t_indoor);
    }
    if (!isnan(rh_indoor)) {
      publishSensor(TOPIC_INDOOR_RH, rh_indoor);
    }

    // ── SHT31 outdoor ────────────────────────────────────────────────────────
    float t_outdoor = sht31_outdoor.readTemperature();
    float rh_outdoor = sht31_outdoor.readHumidity();
    if (!isnan(t_outdoor)) {
      publishSensor(TOPIC_OUTDOOR_TEMP, t_outdoor);
    }
    if (!isnan(rh_outdoor)) {
      publishSensor(TOPIC_OUTDOOR_RH, rh_outdoor);
    }

    // ── DS18B20 inlet ────────────────────────────────────────────────────────
    ds18b20.requestTemperatures();
    float t_inlet = ds18b20.getTempCByIndex(0);
    if (t_inlet != DEVICE_DISCONNECTED_C) {
      publishSensor(TOPIC_INLET_TEMP, t_inlet);
    }

    // ── Soil moisture ────────────────────────────────────────────────────────
    publishSensor(TOPIC_SOIL_E, readSoilMoisture(PIN_SOIL_E), 1);
    publishSensor(TOPIC_SOIL_S, readSoilMoisture(PIN_SOIL_S), 1);

    Serial.printf("[Sensors] Tin=%.1f°C RHin=%.1f%% Tout=%.1f°C RHout=%.1f%% "
                  "Tinlet=%.1f°C SoilE=%.0f%% SoilS=%.0f%%\n",
                  t_indoor, rh_indoor, t_outdoor, rh_outdoor, t_inlet,
                  readSoilMoisture(PIN_SOIL_E), readSoilMoisture(PIN_SOIL_S));
  }
}
