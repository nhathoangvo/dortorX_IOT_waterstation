// ─────────────────────────────────────────────────────────
//  Doctor.X IoT — ESP32 Water Station Firmware v2.0
//  Hardware: Button(35), DHT11(34), OLED SH1106 SPI 1.3"
//
//  Lưu ý: GPIO 34, 35 là INPUT ONLY — cần trở kéo ngoài:
//    - BTN: 10k pull-up lên 3.3V, nút nối GPIO35 → GND
//    - DHT11: 4.7k pull-up lên 3.3V trên data pin
// ─────────────────────────────────────────────────────────

#include <WiFi.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include <U8g2lib.h>
#include <SPI.h>
#include "config.h"

// ── Pins ─────────────────────────────────────────────────
#define BTN_PIN     35   // INPUT ONLY, external 10k pull-up required
#define LED_PIN     2

#define OLED_MOSI   23
#define OLED_CLK    18
#define OLED_DC     16
#define OLED_RESET  17
#define OLED_CS     5

// ── Hardware ─────────────────────────────────────────────
// 1.3" OLED thường dùng chip SH1106 — đổi sang SSD1306 nếu màn không hiển thị đúng
U8G2_SH1106_128X64_NONAME_F_4W_HW_SPI u8g2(U8G2_R0, OLED_CS, OLED_DC, OLED_RESET);

// ── State ────────────────────────────────────────────────
bool    btnPrev        = HIGH;
float   tempC          = NAN;
float   humidity       = NAN;
char    weatherDesc[24] = "...";
unsigned long lastWeatherFetch = 0;
unsigned long progressStart    = 0;
bool    showProgress   = false;

const unsigned long PROGRESS_MS      = 5000;
const unsigned long WEATHER_INTERVAL = 600000; // 10 phút

// ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT);   // GPIO35: INPUT ONLY, no internal pullup
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  u8g2.begin();
  drawBoot("Khoi dong...");

  Serial.printf("\n[Doctor.X] Boot v%s\n", FIRMWARE_VERSION);

  drawBoot("Ket noi WiFi...");
  connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    drawBoot("Kiem tra OTA...");
    checkOTA();
    drawBoot("Lay thoi tiet...");
    fetchWeather();
  }

  lastWeatherFetch = millis();
}

void loop() {
  unsigned long now = millis();

  // ── Button ──────────────────────────────────────────────
  bool btnNow = digitalRead(BTN_PIN);
  if (btnPrev == HIGH && btnNow == LOW) {
    delay(50);
    if (digitalRead(BTN_PIN) == LOW) {
      Serial.printf("[BTN] Nhan nut -> ghi %d ml\n", ML_PER_PRESS);
      progressStart = now;
      showProgress   = true;
      drawProgress(0);        // Hiển thị ngay trước khi HTTP block
      postWater(ML_PER_PRESS);
      while (digitalRead(BTN_PIN) == LOW) delay(10);
    }
  }
  btnPrev = btnNow;

  // ── Kết thúc animation ───────────────────────────────────
  if (showProgress && now - progressStart >= PROGRESS_MS) {
    showProgress = false;
  }

  // ── Fetch thời tiết mỗi 10 phút ─────────────────────────
  if (now - lastWeatherFetch >= WEATHER_INTERVAL) {
    fetchWeather();
    lastWeatherFetch = now;
  }

  // ── OLED ─────────────────────────────────────────────────
  if (showProgress) {
    drawProgress(now - progressStart);
  } else {
    drawNormal();
  }

  // ── WiFi reconnect ───────────────────────────────────────
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Mat ket noi, ket noi lai...");
    connectWiFi();
  }

  delay(50);
}

// ─────────────── OLED ────────────────────────────────────

void drawBoot(const char* msg) {
  u8g2.clearBuffer();
  u8g2.setFont(u8g2_font_ncenB10_tr);
  u8g2.drawStr(15, 28, "Doctor.X");
  u8g2.setFont(u8g2_font_6x10_tr);
  u8g2.drawStr(8, 50, msg);
  u8g2.sendBuffer();
}

void drawNormal() {
  char buf[32];
  u8g2.clearBuffer();

  // Header
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawStr(0, 10, "Doctor.X");
  const char* wifiStatus = (WiFi.status() == WL_CONNECTED) ? "WiFi OK" : "No WiFi";
  u8g2.drawStr(74, 10, wifiStatus);
  u8g2.drawHLine(0, 13, 128);

  u8g2.setFont(u8g2_font_6x10_tr);

  // Nhiệt độ & độ ẩm từ internet
  if (!isnan(tempC)) {
    snprintf(buf, sizeof(buf), "Nhiet do: %.1f C", tempC);
    u8g2.drawStr(0, 28, buf);
    snprintf(buf, sizeof(buf), "Do am:   %.0f %%", humidity);
    u8g2.drawStr(0, 42, buf);
    u8g2.drawStr(0, 57, weatherDesc);
  } else {
    u8g2.drawStr(0, 28, "Dang lay thoi tiet...");
    u8g2.drawStr(4, 48, "Nhan nut = 250ml");
  }
  u8g2.sendBuffer();
}

void drawProgress(unsigned long elapsed) {
  unsigned long safeElapsed = min(elapsed, PROGRESS_MS);
  char buf[16];

  u8g2.clearBuffer();

  // Tiêu đề
  u8g2.setFont(u8g2_font_ncenB08_tr);
  u8g2.drawStr(16, 13, "Dang rot nuoc...");

  // Progress bar: viền + fill
  u8g2.drawFrame(2, 20, 124, 16);
  int filled = (int)(122.0f * safeElapsed / PROGRESS_MS);
  if (filled > 0) u8g2.drawBox(3, 21, filled, 14);

  // 250 ml
  u8g2.setFont(u8g2_font_7x14B_tr);
  u8g2.drawStr(36, 50, "250 ml");

  // Đếm ngược
  u8g2.setFont(u8g2_font_6x10_tr);
  int remain = (int)((PROGRESS_MS - safeElapsed + 999) / 1000);
  snprintf(buf, sizeof(buf), "%d giay", remain > 0 ? remain : 0);
  u8g2.drawStr(48, 63, buf);

  u8g2.sendBuffer();
}

// ─────────────── WiFi ────────────────────────────────────

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[WiFi] Dang ket noi %s", WIFI_SSID);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500); Serial.print("."); tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] OK! IP: %s\n", WiFi.localIP().toString().c_str());
    blinkLed(2, 150);
  } else {
    Serial.println("\n[WiFi] Khong ket noi duoc.");
  }
}

// ─────────────── WEATHER ─────────────────────────────────

void fetchWeather() {
  if (WiFi.status() != WL_CONNECTED) return;
  WiFiClientSecure client; client.setInsecure();
  HTTPClient http;
  String url = String(SERVER_BASE_URL) + "/weather";
  http.begin(client, url);
  http.setTimeout(8000);
  int code = http.GET();
  if (code == 200) {
    StaticJsonDocument<512> doc;
    DeserializationError err = deserializeJson(doc, http.getString());
    if (!err) {
      tempC    = doc["temperature_c"] | NAN;
      humidity = doc["humidity_pct"]  | NAN;
      const char* desc = doc["description"] | "";
      strncpy(weatherDesc, desc, sizeof(weatherDesc) - 1);
      weatherDesc[sizeof(weatherDesc) - 1] = '\0';
      Serial.printf("[WX] %.1fC  %.0f%%  %s\n", tempC, humidity, weatherDesc);
    }
  } else {
    Serial.printf("[WX] HTTP %d\n", code);
  }
  http.end();
}

// ─────────────── HTTP ────────────────────────────────────

void postWater(int ml) {
  if (WiFi.status() != WL_CONNECTED) { blinkError(); return; }
  digitalWrite(LED_PIN, HIGH);

  StaticJsonDocument<256> doc;
  doc["device_id"]   = DEVICE_ID;
  doc["api_key"]     = API_KEY;
  doc["metric_type"] = "water_intake_ml";
  doc["value"]       = (float)ml;
  JsonObject p = doc.createNestedObject("payload");
  p["source"]  = "button";
  p["glasses"] = ml / 250;

  String body; serializeJson(doc, body);
  WiFiClientSecure client; client.setInsecure();
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(8000);
  int code = http.POST(body);
  http.end();

  digitalWrite(LED_PIN, LOW);
  if (code == 200) {
    Serial.printf("[OK] Posted %d ml\n", ml);
    blinkLed(1, 80);
  } else {
    Serial.printf("[ERR] HTTP %d\n", code);
    blinkError();
  }
}


// ─────────────── OTA ─────────────────────────────────────

void checkOTA() {
  Serial.println("[OTA] Kiem tra firmware moi...");
  WiFiClientSecure client; client.setInsecure();
  HTTPClient http;
  http.begin(client, OTA_CHECK_URL);
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("X-Current-Version", FIRMWARE_VERSION);
  http.setTimeout(8000);
  int code = http.GET();
  if (code != 200) { http.end(); return; }

  StaticJsonDocument<256> doc;
  deserializeJson(doc, http.getString());
  http.end();
  if (!doc["update_available"].as<bool>()) {
    Serial.println("[OTA] Dang dung phien ban moi nhat.");
    return;
  }
  String dlUrl = doc["download_url"].as<String>();
  Serial.printf("[OTA] Cap nhat: %s\n", doc["version"].as<String>().c_str());
  WiFiClientSecure upClient; upClient.setInsecure();
  httpUpdate.setLedPin(LED_PIN, LOW);
  httpUpdate.update(upClient, dlUrl);
}

// ─────────────── Utils ────────────────────────────────────

void blinkLed(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH); delay(ms);
    digitalWrite(LED_PIN, LOW);  delay(ms);
  }
}

void blinkError() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH); delay(80);
    digitalWrite(LED_PIN, LOW);  delay(80);
  }
}
