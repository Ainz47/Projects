/*
 * Astorga Central -- Flood Watch node  (ESP8266 / ESP-12E port)
 * ESP8266 (NodeMCU / Wemos, ESP-12E module) + JSN-SR04T ultrasonic sensor.
 *
 * Functionally identical to the ESP32 sketch (flood_sensor.ino): measures the
 * distance down to the water and POSTs it to the backend, which converts it to
 * water level and classifies normal / watch / critical. This is choke point #1.
 *
 * WHY A SEPARATE SKETCH: the ESP8266 uses different core libraries
 * (ESP8266WiFi / ESP8266HTTPClient / EEPROM instead of WiFi / HTTPClient /
 * Preferences) and a different GPIO map. The ESP32 sketch will NOT compile here.
 *
 * WIRING (JSN-SR04T, Mode 1 -- default, behaves like an HC-SR04):
 *   Sensor VCC   -> 5V pin (VIN / VU on NodeMCU)   (sensor needs 5V)
 *   Sensor GND   -> GND
 *   Sensor Trig  -> GPIO 5  (NodeMCU label D1)
 *   Sensor Echo  -> GPIO 4  (NodeMCU label D2)     (prototype: wired directly)
 *      NOTE: ESP8266 pins are 3.3V and NOT 5V-tolerant. Echo idles LOW and
 *      pulses to ~5V only briefly; the bench prototype wires it directly for
 *      the demo. For a permanent install add a 1k/2k divider (Echo --[1k]--+--
 *      [2k]--GND, tap the junction to D2) or a level shifter.
 *
 * MOUNTING: the JSN-SR04T has a ~20 cm blind zone. Mount it high enough that
 * normal water never comes within 20 cm of the sensor face. The backend treats
 * any reading < 20 cm as CRITICAL (fail-safe).
 *
 * PROVISIONING (self-hosted, no cloud): on boot the node tries saved WiFi creds;
 * if none work it starts its own AP "AstorgaFloodNode" (pw "astorga123") with a
 * captive portal to set the WiFi, the backend URL, and this node's choke-point id.
 *
 * RE-PROVISION (change WiFi / backend without re-flashing): while the board is
 * RUNNING, hold the onboard FLASH button (GPIO0) for ~3 seconds. It wipes the
 * saved WiFi + config and reboots straight into the captive portal. The onboard
 * LED flashes to confirm the wipe. NOTE: this is the FLASH button, not RST (RST
 * only reboots and can't be read by software). Do NOT hold FLASH while powering
 * on -- GPIO0 low at boot puts the chip in flash-upload mode; the hold must
 * happen after it has booted.
 *
 * DEPENDENCIES (Library Manager): "WiFiManager" by tzapu. Board package:
 *   "esp8266 by ESP8266 Community". Board = "NodeMCU 1.0 (ESP-12E Module)".
 */

#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <WiFiManager.h>   // tzapu/WiFiManager -- captive-portal provisioning
#include <EEPROM.h>        // ESP8266 has no Preferences; emulate storage in flash

// ---- DEFAULTS (used only until overridden via the captive portal) ---------
const char* DEFAULT_API_BASE       = "http://192.168.1.20:8000";
const char* DEFAULT_CHOKE_POINT_ID = "1";   // must match the live node in seed.py

const char* AP_SSID     = "AstorgaFloodNode";
const char* AP_PASSWORD = "change-me-before-flashing";  // >= 8 chars, or the AP is left open
const int   PORTAL_TIMEOUT_S = 180;          // give up on the portal after 3 min

const int TRIG_PIN  = 5;   // D1
const int ECHO_PIN  = 4;   // D2
const int RESET_BTN = 0;   // D3 / onboard FLASH button -- hold 3s to re-provision
const unsigned long RESET_HOLD_MS = 3000;

const unsigned long SEND_INTERVAL_MS = 1000;   // ~1 Hz live feedback for the demo
                                               // (a full 5-sample read takes ~0.4s, so 1s has headroom)
const int   SAMPLES = 5;                        // median-of-N to reject bad echoes
const float SOUND_CM_PER_US = 0.0343;           // speed of sound, cm per microsecond
// ---------------------------------------------------------------------------

// Persisted config layout in EEPROM. `magic` marks a written record so a blank
// chip falls back to the DEFAULT_* values above instead of reading garbage.
struct Config {
  char magic[4];       // "AC1\0" once written
  char apiBase[96];
  int  chokePointId;
};
const char* CFG_MAGIC = "AC1";
const int   EEPROM_SIZE = 512;

String  apiBase;
int     chokePointId;
unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RESET_BTN, INPUT_PULLUP);   // FLASH button reads LOW when pressed
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);    // onboard LED is active-LOW; start off

  loadConfig();
  provisionWiFi();
}

void loop() {
  checkResetButton();

  if (millis() - lastSend >= SEND_INTERVAL_MS) {
    lastSend = millis();
    float distance = readDistanceCm();
    if (distance > 0) {
      Serial.printf("Distance: %.1f cm\n", distance);
      postReading(distance);
    } else {
      Serial.println("No valid echo this cycle; skipping.");
    }
  }
}

// Read our custom fields from EEPROM, seeding with the defaults on a blank chip.
void loadConfig() {
  EEPROM.begin(EEPROM_SIZE);
  Config cfg;
  EEPROM.get(0, cfg);
  if (strncmp(cfg.magic, CFG_MAGIC, 3) == 0) {
    apiBase      = String(cfg.apiBase);
    chokePointId = cfg.chokePointId;
  } else {
    apiBase      = DEFAULT_API_BASE;
    chokePointId = atoi(DEFAULT_CHOKE_POINT_ID);
  }
  EEPROM.end();
  Serial.printf("Config: API_BASE=%s  CHOKE_POINT_ID=%d\n", apiBase.c_str(), chokePointId);
}

void saveConfig(const String& api, int cp) {
  Config cfg;
  memset(&cfg, 0, sizeof(cfg));
  strncpy(cfg.magic, CFG_MAGIC, sizeof(cfg.magic) - 1);
  strncpy(cfg.apiBase, api.c_str(), sizeof(cfg.apiBase) - 1);
  cfg.chokePointId = cp;
  EEPROM.begin(EEPROM_SIZE);
  EEPROM.put(0, cfg);
  EEPROM.commit();   // ESP8266: writes are staged until commit()
  EEPROM.end();
}

// Non-blocking: if the FLASH button is held for RESET_HOLD_MS, wipe everything
// and reboot into the portal. Called every loop so it never stalls the readings.
void checkResetButton() {
  static unsigned long heldSince = 0;
  if (digitalRead(RESET_BTN) == LOW) {          // button down
    if (heldSince == 0) heldSince = millis();
    else if (millis() - heldSince >= RESET_HOLD_MS) {
      factoryReset();                            // does not return (reboots)
    }
  } else {
    heldSince = 0;                               // released before threshold
  }
}

// Clear saved WiFi creds + our EEPROM config, flash the LED, and restart. On the
// next boot autoConnect() finds nothing saved and opens the captive portal.
void factoryReset() {
  Serial.println("FLASH held 3s: wiping WiFi + config, reopening portal...");
  for (int i = 0; i < 6; i++) {                  // visible confirmation blink
    digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
    delay(120);
  }
  WiFiManager wm;
  wm.resetSettings();                            // clear saved WiFi credentials
  EEPROM.begin(EEPROM_SIZE);
  for (int i = 0; i < EEPROM_SIZE; i++) EEPROM.write(i, 0);  // clear our config
  EEPROM.commit();
  EEPROM.end();
  delay(300);
  ESP.restart();
}

// Bring up WiFi via the captive portal. WiFiManager reconnects silently from
// saved creds; an unprovisioned/moved node (or wrong creds) opens the AP portal.
void provisionWiFi() {
  WiFiManager wm;

  char cpBuf[8];
  snprintf(cpBuf, sizeof(cpBuf), "%d", chokePointId);
  WiFiManagerParameter pApiBase("api_base", "Backend URL (http://ip:port)", apiBase.c_str(), 96);
  WiFiManagerParameter pChokeId("cp_id", "Choke point id (from seed.py)", cpBuf, 6);
  wm.addParameter(&pApiBase);
  wm.addParameter(&pChokeId);

  wm.setConfigPortalTimeout(PORTAL_TIMEOUT_S);

  bool ok = wm.autoConnect(AP_SSID, AP_PASSWORD);

  // Persist whatever the portal collected (WiFiManager stores the WiFi creds
  // itself; the two custom fields are ours to save).
  String newApi = pApiBase.getValue();
  int    newCp  = atoi(pChokeId.getValue());
  if (newApi.length() > 0 && (newApi != apiBase || newCp != chokePointId)) {
    saveConfig(newApi, newCp);
    apiBase = newApi;
    chokePointId = newCp;
    Serial.printf("Saved new config: API_BASE=%s  CHOKE_POINT_ID=%d\n",
                  apiBase.c_str(), chokePointId);
  }

  if (ok) {
    Serial.printf("Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("WiFi provisioning failed/timed out; restarting.");
    delay(1000);
    ESP.restart();
  }
}

// One ultrasonic ping -> distance in cm. Returns -1 on timeout.
float pingOnce() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  // 30 ms timeout ~= 5 m max range; returns 0 on timeout.
  unsigned long duration = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (duration == 0) return -1;
  return (duration * SOUND_CM_PER_US) / 2.0;
}

// Median of SAMPLES pings -- one spurious reflection off ripples won't swing it.
float readDistanceCm() {
  float vals[SAMPLES];
  int n = 0;
  for (int i = 0; i < SAMPLES; i++) {
    float d = pingOnce();
    if (d > 0) vals[n++] = d;
    delay(60);
  }
  if (n == 0) return -1;
  for (int i = 1; i < n; i++) {
    float key = vals[i];
    int j = i - 1;
    while (j >= 0 && vals[j] > key) { vals[j + 1] = vals[j]; j--; }
    vals[j + 1] = key;
  }
  return vals[n / 2];
}

void postReading(float distanceCm) {
  if (WiFi.status() != WL_CONNECTED) provisionWiFi();

  WiFiClient client;                 // ESP8266 HTTPClient needs an explicit client
  HTTPClient http;
  String url = apiBase + "/api/flood/readings";
  http.begin(client, url);
  http.addHeader("Content-Type", "application/json");

  String body = "{\"choke_point_id\":" + String(chokePointId) +
                ",\"distance_cm\":" + String(distanceCm, 1) + "}";

  int code = http.POST(body);
  if (code > 0) {
    Serial.printf("POST %d: %s\n", code, http.getString().c_str());
  } else {
    Serial.printf("POST failed: %s\n", http.errorToString(code).c_str());
  }
  http.end();
}
