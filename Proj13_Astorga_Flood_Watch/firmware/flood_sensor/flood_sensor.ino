/*
 * Astorga Central -- Flood Watch node
 * ESP32 + JSN-SR04T waterproof ultrasonic sensor.
 *
 * Measures the distance from the sensor down to the water surface and POSTs it
 * to the backend, which converts distance -> water level and decides
 * normal / watch / critical. This node is choke point #1 ("live ESP32 node"
 * seeded by seed.py); the other points on the map are simulated.
 *
 * WIRING (JSN-SR04T, Mode 1 -- default, behaves like an HC-SR04):
 *   Sensor VCC   -> ESP32 5V (VIN)   (the board needs 5V; ESP32 logic is 3.3V)
 *   Sensor GND   -> ESP32 GND
 *   Sensor Trig  -> GPIO 5
 *   Sensor Echo  -> GPIO 18   (prototype: wired directly)
 *      This prototype connects Echo straight to GPIO 18 for the demo. Echo
 *      idles LOW and only pulses to ~5V briefly, which the pin tolerates for
 *      short-term testing. For a PERMANENT outdoor install, protect the 3.3V
 *      input with a divider (Echo --[1k]--+--[2k]--GND, tap the junction to
 *      GPIO 18) or a level shifter.
 *
 * MOUNTING: the JSN-SR04T has a ~20 cm blind zone. Mount it high above the
 * canal floor so normal water never comes within 20 cm of the sensor face.
 * The backend already treats any reading < 20 cm as CRITICAL (fail-safe).
 *
 * WIFI PROVISIONING (self-hosted, no cloud broker):
 *   On boot the node tries the WiFi credentials saved in flash. If none work
 *   (first boot, moved to a new site, router changed), it starts its own
 *   access point named "AstorgaFloodNode" (password set by AP_PASSWORD below) and serves
 *   a captive portal. Join that AP with a phone, and the config page lets you:
 *     - pick the site WiFi and enter its password
 *     - set the backend URL (API base) and this node's choke-point id
 *   Everything is stored on the device -- no code edits or reflashing to point
 *   a node at a new network or backend. Hold the BOOT button (GPIO 0) for
 *   ~3 s at power-up to wipe saved settings and force the portal again.
 *
 * DEPENDENCY: Library Manager -> install "WiFiManager" by tzapu (>= 2.0.x).
 *
 * Arduino IDE: Board = "ESP32 Dev Module". Needs the ESP32 board package.
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <WiFiManager.h>   // tzapu/WiFiManager -- captive-portal provisioning
#include <Preferences.h>   // ESP32 NVS key-value store for our custom fields

// ---- DEFAULTS (used only until overridden via the captive portal) ---------
// These are seed values written to flash on first boot. After that the values
// saved through the portal win, so you normally never touch this file again.
const char* DEFAULT_API_BASE       = "http://192.168.1.20:8000";
const char* DEFAULT_CHOKE_POINT_ID = "1";   // must match the live node in seed.py

// Config-portal access point (shown when there are no working WiFi creds).
const char* AP_SSID     = "AstorgaFloodNode";
const char* AP_PASSWORD = "change-me-before-flashing";  // >= 8 chars, or the AP is left open
const int   PORTAL_TIMEOUT_S = 180;          // give up on the portal after 3 min

const int TRIG_PIN = 5;
const int ECHO_PIN = 18;
const int RESET_PIN = 0;   // BOOT button -- hold at power-up to clear settings

const unsigned long SEND_INTERVAL_MS = 15000;  // matches the sim tick / dashboard refresh
const int   SAMPLES = 5;                        // median-of-N to reject bad echoes
const float SOUND_CM_PER_US = 0.0343;           // speed of sound, cm per microsecond
// ---------------------------------------------------------------------------

// Runtime config, loaded from NVS in setup(). Not const: the portal can change it.
String  apiBase;
int     chokePointId;

Preferences prefs;          // namespace "flood" in NVS
unsigned long lastSend = 0;

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(RESET_PIN, INPUT_PULLUP);

  loadConfig();
  provisionWiFi();
}

void loop() {
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

// Load our custom fields (API base + choke-point id) from flash, seeding them
// with the defaults above on the very first boot.
void loadConfig() {
  prefs.begin("flood", false);
  apiBase      = prefs.getString("api_base", DEFAULT_API_BASE);
  chokePointId = prefs.getInt("cp_id", atoi(DEFAULT_CHOKE_POINT_ID));
  prefs.end();
  Serial.printf("Config: API_BASE=%s  CHOKE_POINT_ID=%d\n", apiBase.c_str(), chokePointId);
}

// Bring up WiFi via the captive portal. WiFiManager reconnects silently using
// creds saved in flash; only an unprovisioned/moved node opens the AP portal.
void provisionWiFi() {
  WiFiManager wm;

  // Hold BOOT (GPIO 0) at power-up to wipe saved WiFi + custom settings.
  if (digitalRead(RESET_PIN) == LOW) {
    Serial.println("BOOT held: clearing saved settings, opening config portal.");
    wm.resetSettings();
    prefs.begin("flood", false);
    prefs.clear();
    prefs.end();
    apiBase = DEFAULT_API_BASE;
    chokePointId = atoi(DEFAULT_CHOKE_POINT_ID);
  }

  // Extra portal fields for our backend URL and this node's choke-point id.
  char cpBuf[8];
  snprintf(cpBuf, sizeof(cpBuf), "%d", chokePointId);
  WiFiManagerParameter pApiBase("api_base", "Backend URL (http://ip:port)", apiBase.c_str(), 96);
  WiFiManagerParameter pChokeId("cp_id", "Choke point id (from seed.py)", cpBuf, 6);
  wm.addParameter(&pApiBase);
  wm.addParameter(&pChokeId);

  wm.setConfigPortalTimeout(PORTAL_TIMEOUT_S);

  // Blocks here: reconnects, or serves the portal until configured / timed out.
  bool ok = wm.autoConnect(AP_SSID, AP_PASSWORD);

  // Persist whatever the portal collected (WiFiManager saved the WiFi creds
  // itself; the two custom fields are ours to store).
  String newApi = pApiBase.getValue();
  int    newCp  = atoi(pChokeId.getValue());
  if (newApi.length() > 0 && (newApi != apiBase || newCp != chokePointId)) {
    prefs.begin("flood", false);
    prefs.putString("api_base", newApi);
    prefs.putInt("cp_id", newCp);
    prefs.end();
    apiBase = newApi;
    chokePointId = newCp;
    Serial.printf("Saved new config: API_BASE=%s  CHOKE_POINT_ID=%d\n",
                  apiBase.c_str(), chokePointId);
  }

  if (ok) {
    Serial.printf("Connected. IP: %s\n", WiFi.localIP().toString().c_str());
  } else {
    // Portal timed out with no connection. Reboot and try the saved creds
    // again rather than sitting idle -- the router may just be slow to appear.
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
  // simple insertion sort, then take the middle element
  for (int i = 1; i < n; i++) {
    float key = vals[i];
    int j = i - 1;
    while (j >= 0 && vals[j] > key) { vals[j + 1] = vals[j]; j--; }
    vals[j + 1] = key;
  }
  return vals[n / 2];
}

void postReading(float distanceCm) {
  // If WiFi dropped, let WiFiManager reconnect using the saved creds (it won't
  // reopen the portal unless there are none).
  if (WiFi.status() != WL_CONNECTED) provisionWiFi();

  HTTPClient http;
  String url = apiBase + "/api/flood/readings";
  http.begin(url);
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
