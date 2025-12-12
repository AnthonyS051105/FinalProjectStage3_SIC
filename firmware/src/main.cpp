#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <DHT.h>
#include <Wire.h>
#include "MAX30105.h"

// --- Configuration ---
const char* ssid = "NAMA_WIFI_ANDA";
const char* password = "PASSWORD_WIFI";
const char* mqtt_server = "broker.hivemq.com";
const int mqtt_port = 1883;
const char* mqtt_topic_bp = "sic/stage3/bp_data";
const char* mqtt_topic_stress = "sic/stage3/stress_data";

// --- Sensors ---
#define DHTPIN 27
#define DHTTYPE DHT11
DHT dht(DHTPIN, DHTTYPE);

MAX30105 particleSensor;

// --- MQTT & WiFi ---
WiFiClient espClient;
PubSubClient client(espClient);

// --- Sampling Configuration ---
#define PPG_SAMPLE_RATE 100      // 100Hz for PPG
#define TEMP_SAMPLE_RATE 4       // 4Hz for Temperature
#define DATA_COLLECTION_TIME 10000 // 10 seconds

#define PPG_BUFFER_SIZE 1000     // 100Hz * 10s
#define TEMP_BUFFER_SIZE 40      // 4Hz * 10s

// --- Data Buffers ---
uint32_t ppgBuffer[PPG_BUFFER_SIZE];
float tempBuffer[TEMP_BUFFER_SIZE];
int ppgIndex = 0;
int tempIndex = 0;

unsigned long lastPPGSample = 0;
unsigned long lastTempSample = 0;
unsigned long dataCollectionStart = 0;

bool collectingData = false;
bool simulateSensors = false;

// --- Helper Functions ---
void downsamplePPG(uint32_t* input, int inputSize, uint32_t* output, int outputSize) {
  // Downsample from 100Hz to 64Hz
  // Take every 100/64 = 1.5625th sample (use decimation)
  float ratio = (float)inputSize / (float)outputSize;
  
  for (int i = 0; i < outputSize; i++) {
    int srcIndex = (int)(i * ratio);
    if (srcIndex < inputSize) {
      output[i] = input[srcIndex];
    }
  }
}

void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("\nWiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("\nWiFi connection failed. Entering simulation mode.");
    simulateSensors = true;
  }
}

void reconnect() {
  int attempts = 0;
  while (!client.connected() && attempts < 3) {
    Serial.print("Attempting MQTT connection...");
    String clientId = "ESP32Client-";
    clientId += String(random(0xffff), HEX);
    
    if (client.connect(clientId.c_str())) {
      Serial.println("connected");
      return;
    } else {
      Serial.print("failed, rc=");
      Serial.print(client.state());
      Serial.println(" retrying in 3 seconds");
      delay(3000);
      attempts++;
    }
  }
}

void sendBPData() {
  // Create JSON with 1000 PPG samples @ 100Hz
  DynamicJsonDocument doc(16384); // Larger buffer for array
  JsonArray ppgArray = doc.createNestedArray("ppg");
  
  for (int i = 0; i < PPG_BUFFER_SIZE; i++) {
    ppgArray.add(ppgBuffer[i]);
  }
  
  doc["device_id"] = "ESP32_SIC_01";
  doc["timestamp"] = millis();
  
  String output;
  serializeJson(doc, output);
  
  Serial.println("Sending BP data...");
  
  if (client.publish(mqtt_topic_bp, output.c_str())) {
    Serial.println("BP data sent successfully");
  } else {
    Serial.println("Failed to send BP data");
  }
}

void sendStressData() {
  // Downsample PPG from 100Hz to 64Hz
  const int STRESS_PPG_SIZE = 640;
  uint32_t ppgDownsampled[STRESS_PPG_SIZE];
  downsamplePPG(ppgBuffer, PPG_BUFFER_SIZE, ppgDownsampled, STRESS_PPG_SIZE);
  
  // Create JSON with 640 PPG samples @ 64Hz and 40 temp samples @ 4Hz
  DynamicJsonDocument doc(16384);
  JsonArray ppgArray = doc.createNestedArray("ppg");
  JsonArray tempArray = doc.createNestedArray("temperature");
  
  for (int i = 0; i < STRESS_PPG_SIZE; i++) {
    ppgArray.add(ppgDownsampled[i]);
  }
  
  for (int i = 0; i < TEMP_BUFFER_SIZE; i++) {
    tempArray.add(tempBuffer[i]);
  }
  
  doc["device_id"] = "ESP32_SIC_01";
  doc["timestamp"] = millis();
  
  String output;
  serializeJson(doc, output);
  
  Serial.println("Sending Stress data...");
  
  if (client.publish(mqtt_topic_stress, output.c_str())) {
    Serial.println("Stress data sent successfully");
  } else {
    Serial.println("Failed to send Stress data");
  }
}

void setup() {
  Serial.begin(115200);
  
  Serial.println("\n=== SIC Stage 3 - PPG & Temperature Sampler ===");
  
  // Init DHT
  dht.begin();
  
  // Init MAX30102
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("MAX30102 not found. Using SIMULATION mode.");
    simulateSensors = true;
  } else {
    Serial.println("MAX30102 detected!");
    particleSensor.setup();
    particleSensor.setPulseAmplitudeRed(0x1F); // Higher amplitude for better signal
    particleSensor.setPulseAmplitudeGreen(0);
  }

  // WiFi scan (debug)
  Serial.println("Scanning WiFi networks...");
  int n = WiFi.scanNetworks();
  if (n == 0) {
    Serial.println("No networks found");
  } else {
    Serial.printf("%d networks found:\n", n);
    for (int i = 0; i < n && i < 5; ++i) {
      Serial.printf("  %d: %s (%d dBm)\n", i + 1, WiFi.SSID(i).c_str(), WiFi.RSSI(i));
    }
  }

  setup_wifi();
  
  if (!simulateSensors) {
    client.setServer(mqtt_server, mqtt_port);
    client.setBufferSize(16384); // Increase buffer for large messages
  }
  
  Serial.println("\nStarting data collection in 3 seconds...");
  delay(3000);
  
  dataCollectionStart = millis();
  collectingData = true;
  ppgIndex = 0;
  tempIndex = 0;
  lastPPGSample = micros();
  lastTempSample = micros();
  
  Serial.println("=== COLLECTING DATA (10 seconds) ===");
}

void loop() {
  unsigned long nowMicros = micros(); // Use micros for better precision
  unsigned long nowMillis = millis();
  
  // Handle MQTT outside of tight timing loop
  static unsigned long lastMQTTCheck = 0;
  if (nowMillis - lastMQTTCheck > 100) { // Check MQTT every 100ms
    if (!simulateSensors && !client.connected()) {
      reconnect();
    }
    client.loop();
    lastMQTTCheck = nowMillis;
  }
  
  if (collectingData) {
    // Sample PPG at 100Hz (every 10000 microseconds = 10ms)
    if ((nowMicros - lastPPGSample) >= 10000) {
      lastPPGSample = nowMicros;
      
      if (ppgIndex < PPG_BUFFER_SIZE) {
        if (simulateSensors) {
          // Simulate PPG signal (sine wave + noise)
          float t = ppgIndex / 100.0;
          ppgBuffer[ppgIndex] = 50000 + 10000 * sin(2 * PI * 1.2 * t) + random(-500, 500);
        } else {
          ppgBuffer[ppgIndex] = particleSensor.getIR();
        }
        ppgIndex++;
      }
    }
    
    // Sample Temperature at 4Hz (every 250ms = 250000 microseconds)
    if ((nowMicros - lastTempSample) >= 250000) {
      lastTempSample = nowMicros;
      
      if (tempIndex < TEMP_BUFFER_SIZE) {
        if (simulateSensors) {
          // Simulate temperature
          tempBuffer[tempIndex] = 36.5 + random(-10, 10) / 20.0;
        } else {
          float t = dht.readTemperature();
          if (!isnan(t)) {
            tempBuffer[tempIndex] = t;
          } else {
            tempBuffer[tempIndex] = 36.5; // Default if read fails
          }
        }
        tempIndex++;
      }
    }
    
    // Check if 10 seconds elapsed
    if (nowMillis - dataCollectionStart >= DATA_COLLECTION_TIME) {
      collectingData = false;
      
      Serial.println("=== DATA COLLECTION COMPLETE ===");
      Serial.printf("PPG samples collected: %d / %d (expected 1000)\n", ppgIndex, PPG_BUFFER_SIZE);
      Serial.printf("Temperature samples collected: %d / %d (expected 40)\n", tempIndex, TEMP_BUFFER_SIZE);
      
      // Validate sample counts
      if (ppgIndex < 900) {
        Serial.println("WARNING: PPG sample count too low! Check sensor or timing.");
      }
      if (tempIndex < 35) {
        Serial.println("WARNING: Temperature sample count too low!");
      }
      
      // Send data
      if (!simulateSensors) {
        sendBPData();
        delay(500); // Give time between messages
        sendStressData();
      } else {
        Serial.println("SIMULATION MODE: Data not sent to MQTT");
        Serial.println("Sample PPG values:");
        for (int i = 0; i < 10 && i < ppgIndex; i++) {
          Serial.printf("  PPG[%d] = %u\n", i, ppgBuffer[i]);
        }
        Serial.println("Sample Temp values:");
        for (int i = 0; i < 5 && i < tempIndex; i++) {
          Serial.printf("  Temp[%d] = %.2f\n", i, tempBuffer[i]);
        }
      }
      
      // Reset for next collection
      Serial.println("\nRestarting collection in 5 seconds...");
      delay(5000);
      
      dataCollectionStart = millis();
      collectingData = true;
      ppgIndex = 0;
      tempIndex = 0;
      lastPPGSample = micros();
      lastTempSample = micros();
      
      Serial.println("=== COLLECTING DATA (10 seconds) ===");
    }
  }
}
