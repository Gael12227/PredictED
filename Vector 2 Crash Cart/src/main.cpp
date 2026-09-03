#include <WiFi.h>
#include <HTTPClient.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_Sensor.h>
#include <Wire.h>
#include <ArduinoJson.h>

const char* ssid = "iPhone";
const char* password = "bruh25179";
const char* serverUrl = "http://172.16.138.169:5000/api/sensors";

Adafruit_MPU6050 mpu;
unsigned long lastSendTime = 0;

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  if (!mpu.begin()) {
    Serial.println("Failed to find MPU6050 chip!");
    while (1) delay(10);
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_8_G);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nESP32 Crash Cart Ready!");
}

void loop() {
  sensors_event_t a, g, temp;
  mpu.getEvent(&a, &g, &temp);

  float rawMag = sqrt(a.acceleration.x * a.acceleration.x + 
                      a.acceleration.y * a.acceleration.y + 
                      a.acceleration.z * a.acceleration.z);
  float accelStress = abs(rawMag - 9.81);
  if (accelStress > 4.0 && (millis() - lastSendTime > 1000)) {
    if (WiFi.status() == WL_CONNECTED) {
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");

      StaticJsonDocument<200> doc;
      doc["device_id"] = "esp32_crash_cart";
      doc["patient_delta"] = 0;
      doc["cart_stress_level"] = round(accelStress * 10.0) / 10.0;

      String jsonString;
      serializeJson(doc, jsonString);

      int httpResponseCode = http.POST(jsonString);
      Serial.printf("Crash Cart Stress Sent: %.2f | Response: %d\n", accelStress, httpResponseCode);
      http.end();
      lastSendTime = millis();
    }
  }

  delay(100);
}