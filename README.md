# PredictED: Cyber-Physical Early Warning System

**PredictED** is an IoT-enabled machine learning pipeline that forecasts Emergency Department (ED) gridlock up to two hours in advance. By combining real-time physical edge telemetry with clinical hospital metrics, PredictED moves hospital administration from a reactive "code red" response to proactive capacity management.

## The Problem
Current hospital dashboards are dangerously reactive. By the time a dashboard flashes red, the system is already gridlocked, patients are boarding in hallways, and mortality rates are actively rising. Administrators lack the temporal foresight to intercept bottlenecks before they cascade.

## The Solution
PredictED acts as a digital twin for the Emergency Department. 
Instead of relying solely on static electronic health records (EHR), PredictED ingests live, multi-vector edge IoT data (ambient noise, physical equipment chaos, arrival velocity) and merges it with clinical baselines. A Random Forest model—anchored in the gold-standard **NEDOCS** (National ED Overcrowding Scale) formula—evaluates these metrics to predict capacity failures **two hours in the future**, while our Explainable AI (XAI) engine isolates the exact operational drivers causing the strain.

---

## Architecture & Tech Stack

### 1. Software Stack
*   **Frontend:** Streamlit (Python) for real-time dashboarding and interactive crisis simulation.
*   **Backend API:** Flask (Python) lightweight server to ingest high-frequency IoT telemetry.
*   **Database:** SQLite for temporal feature synthesis (calculating rolling averages of sensor data).
*   **Machine Learning:** `scikit-learn` (Random Forest Regressor) trained on synthesized Delhi clinical datasets (`delhi_Rural.csv` & `Delhi_urban.csv`).

### 2. Edge Hardware (The IoT Vectors)
*   **Vector 1 (Flow):** NodeMCU ESP8266 + HC-SR04 Ultrasonic Sensor tracking doorway *Arrival Velocity*.
*   **Vector 2 (Acuity):** ESP32 + MPU6050 IMU attached to a trauma crash cart measuring the *Equipment Disruption Index*.
*   **Vector 3 (Capacity & Environment):** Raspberry Pi 3A+ with an I2S microphone (Ambient Noise) and DIY copper-wire pressure pads monitoring *6-Bed Live Availability*.

---

## Features

*   **Temporal Forecasting:** Predicts ED capacity load (T+2 hours) using the clinical NEDOCS math model.
*   **Real-Time Explainable AI (XAI):** A dynamic "Clinical Impact Analysis" engine that translates black-box ML weights into actionable insights (e.g., explicitly alerting staff to an admit bottleneck vs. a surge in arrival velocity).
*   **"Code Orange" Mass Casualty Simulation:** A one-click event trigger that injects catastrophic trauma loads, extreme temperatures, and hazardous AQI into the system to demonstrate dynamic UI responsiveness.
*   **Contextual Risk Heuristics:** Automatically adjusts risk profiles based on regional demographics (e.g., Agricultural Harvest trauma risks for rural settings, Peak Tourist medical translation needs for urban settings).

---

## Local Setup & Installation

### Prerequisites
*   Python 3.9+
*   PlatformIO (for flashing ESP32/ESP8266 firmware)
*   Raspberry Pi OS (for audio/GPIO node)

### 1. Clone & Install Dependencies
```bash
git clone [https://github.com/yourusername/PredictED.git](https://github.com/yourusername/PredictED.git)
cd PredictED
pip install -r requirements.txt
