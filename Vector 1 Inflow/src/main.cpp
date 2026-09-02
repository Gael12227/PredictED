#include <ESP8266WiFi.h>
#include <ESP8266HTTPClient.h>
#include <WiFiClient.h>
#include <ArduinoJson.h>

const char* ssid = "iPhone";
const char* password = "bruh25179";
const char* serverUrl = "http://172.16.138.169:5000/api/sensors";

const int TRIG_PIN = 14; // D5
const int ECHO_PIN = 12; // D6

unsigned long lastPulseTime = 0;
int pulseCountInWindow = 0;
unsigned long windowStartTime = 0;
bool objectDetected = false;

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);

  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100); 

  WiFi.begin(ssid, password);
  Serial.print("Connecting to WiFi");
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if(WiFi.status() == WL_CONNECTED) {
      Serial.println("\nConnected to WiFi!");
      Serial.print("IP Address: ");
      Serial.println(WiFi.localIP());
  } else {
      Serial.println("\nFailed to connect. Please check credentials or hotspot settings.");
  }
}

float readDistanceCM() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH, 30000);
  if (duration == 0) return 999.0;
  return duration * 0.034 / 2.0;
}

void sendDoorwayEvent(int delta, int velocity) {
  if (WiFi.status() == WL_CONNECTED) {
    WiFiClient client;
    HTTPClient http;
    http.begin(client, serverUrl);
    http.addHeader("Content-Type", "application/json");

    StaticJsonDocument<200> doc;
    doc["device_id"] = "nodemcu_doorway";
    doc["patient_delta"] = delta;
    doc["arrival_velocity"] = velocity;

    String jsonString;
    serializeJson(doc, jsonString);

    int httpResponseCode = http.POST(jsonString);
    Serial.printf("POST Sent. Response code: %d\n", httpResponseCode);
    http.end();
  }
}

void loop() {
  float distance = readDistanceCM();

  // Trigger on objects closer than 10 cm
  if (distance < 10.0 && !objectDetected) {
    objectDetected = true;
    pulseCountInWindow++;
    Serial.printf("Door Triggered! Distance: %.1f cm | Window Pings: %d\n", distance, pulseCountInWindow);
    delay(150);
  } else if (distance >= 15.0 && objectDetected) {
    objectDetected = false;
  }

  // Evaluate rolling 3-second window for frantic arrival velocity
  if (millis() - windowStartTime >= 3000) {
    if (pulseCountInWindow > 0) {
      int delta = pulseCountInWindow;
      sendDoorwayEvent(delta, pulseCountInWindow);
    }
    pulseCountInWindow = 0;
    windowStartTime = millis();
  }

  delay(50);
}