// ─────────────────────────────────────────────────────────
//  Doctor.X IoT — ESP32 Water Intake Button Firmware
//  Mỗi lần nhấn nút BOOT (GPIO0) = 1 ly nước (250 ml)
//  POST JSON lên backend qua WiFi + OTA update khi boot
//
//  Cấu hình: sao chép config.h.example → config.h
//  rồi điền WiFi/API key vào config.h (file đó đã gitignore)
// ─────────────────────────────────────────────────────────

#include <WiFi.h>
#include <HTTPClient.h>
#include <HTTPUpdate.h>
#include <WiFiClientSecure.h>
#include <ArduinoJson.h>
#include "config.h"   // WiFi credentials + API key (gitignored)

#define BTN_PIN  0
#define LED_PIN  2

bool btnPrev = HIGH;

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  Serial.printf("\n[Doctor.X] Khởi động... v%s\n", FIRMWARE_VERSION);
  connectWiFi();

  if (WiFi.status() == WL_CONNECTED) {
    checkOTA();
  }
}

void loop() {
  bool btnNow = digitalRead(BTN_PIN);

  // Phát hiện falling edge (nhấn xuống)
  if (btnPrev == HIGH && btnNow == LOW) {
    delay(50); // debounce
    if (digitalRead(BTN_PIN) == LOW) {
      Serial.printf("[BTN] Nhấn nút → ghi %d ml\n", ML_PER_PRESS);
      postWater(ML_PER_PRESS);
      // Chờ nhả nút
      while (digitalRead(BTN_PIN) == LOW) delay(10);
    }
  }
  btnPrev = btnNow;

  // Tự kết nối lại WiFi nếu bị mất
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Mất kết nối, đang kết nối lại...");
    connectWiFi();
  }

  delay(10);
}

void connectWiFi() {
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.printf("[WiFi] Đang kết nối tới %s", WIFI_SSID);
  int tries = 0;
  while (WiFi.status() != WL_CONNECTED && tries < 30) {
    delay(500);
    Serial.print(".");
    tries++;
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\n[WiFi] Kết nối thành công! IP: %s\n", WiFi.localIP().toString().c_str());
    blinkLed(2, 150);
  } else {
    Serial.println("\n[WiFi] Không kết nối được. Thử lại sau...");
  }
}

void checkOTA() {
  Serial.println("[OTA] Kiểm tra firmware mới...");

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, OTA_CHECK_URL);
  http.addHeader("X-Device-ID", DEVICE_ID);
  http.addHeader("X-API-Key", API_KEY);
  http.addHeader("X-Current-Version", FIRMWARE_VERSION);
  http.setTimeout(8000);

  int code = http.GET();
  if (code != 200) {
    Serial.printf("[OTA] Không kiểm tra được (HTTP %d)\n", code);
    http.end();
    return;
  }

  StaticJsonDocument<256> doc;
  deserializeJson(doc, http.getString());
  http.end();

  if (!doc["update_available"].as<bool>()) {
    Serial.println("[OTA] Đang dùng phiên bản mới nhất.");
    return;
  }

  String newVersion = doc["version"].as<String>();
  String downloadUrl = doc["download_url"].as<String>();
  Serial.printf("[OTA] Phiên bản mới: %s — đang cập nhật...\n", newVersion.c_str());

  // Nháy LED liên tục trong khi cập nhật
  for (int i = 0; i < 5; i++) { blinkLed(1, 100); delay(100); }

  WiFiClientSecure updateClient;
  updateClient.setInsecure();

  httpUpdate.setLedPin(LED_PIN, LOW);
  t_httpUpdate_return ret = httpUpdate.update(updateClient, downloadUrl);

  switch (ret) {
    case HTTP_UPDATE_FAILED:
      Serial.printf("[OTA] Lỗi: %s\n", httpUpdate.getLastErrorString().c_str());
      blinkError();
      break;
    case HTTP_UPDATE_NO_UPDATES:
      Serial.println("[OTA] Không có cập nhật.");
      break;
    case HTTP_UPDATE_OK:
      Serial.println("[OTA] Cập nhật thành công! Đang reboot...");
      // ESP32 tự reboot sau khi update thành công
      break;
  }
}

void postWater(int ml) {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[ERR] Không có WiFi, bỏ qua lần ghi này.");
    blinkError();
    return;
  }

  digitalWrite(LED_PIN, HIGH);

  StaticJsonDocument<256> doc;
  doc["device_id"]   = DEVICE_ID;
  doc["api_key"]     = API_KEY;
  doc["metric_type"] = "water_intake_ml";
  doc["value"]       = (float)ml;
  JsonObject payload = doc.createNestedObject("payload");
  payload["source"]  = "button";
  payload["glasses"] = ml / 250;

  String body;
  serializeJson(doc, body);

  WiFiClientSecure client;
  client.setInsecure();
  HTTPClient http;
  http.begin(client, SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(8000);

  int code = http.POST(body);

  if (code == 200) {
    Serial.printf("[OK] Posted %d ml — HTTP %d\n", ml, code);
    digitalWrite(LED_PIN, LOW);
    blinkLed(1, 80);
  } else {
    String resp = http.getString();
    Serial.printf("[ERR] HTTP %d: %s\n", code, resp.c_str());
    digitalWrite(LED_PIN, LOW);
    blinkError();
  }

  http.end();
}

void blinkLed(int times, int ms) {
  for (int i = 0; i < times; i++) {
    digitalWrite(LED_PIN, HIGH);
    delay(ms);
    digitalWrite(LED_PIN, LOW);
    delay(ms);
  }
}

void blinkError() {
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH); delay(80);
    digitalWrite(LED_PIN, LOW);  delay(80);
  }
}
