# 🚗 SMART PARK: IoT Sensor Fusion & LoRa Data Pipeline 📊

### Project Overview
**SMART PARK** is an end-to-end IoT system designed to eliminate urban parking congestion by providing real-time space availability. Developed as an academic research project at the **University of Southeastern Philippines (USeP)**, this system replaces expensive, single-modality sensors with a highly cost-effective, custom **Sensor Fusion Edge Architecture**.

The system accurately detects vehicular presence, filters out environmental "noise" (pedestrians, debris), and orchestrates the data over a long-range, low-power network (LoRa) to a cloud-based mobile dashboard.

---

## 🏗️ System Architecture & Data Flow
This project demonstrates a complete hardware-to-cloud data pipeline:

1.  **Data Generation (The Edge):** Independent battery-operated Sensor Nodes are deployed at each parking slot.
2.  **Sensor Fusion Validation:** Heltec ESP32 microcontrollers process raw analog data at the edge. By utilizing a **Boolean "AND" logic gate**, the system requires both spatial proximity (Ultrasonic) and magnetic field disturbance (Magnetometer) to register a valid vehicle, virtually eliminating false positives.
3.  **Data Transmission (LPWAN):** Validated state changes are transmitted via **LoRa (915MHz)**. This ensures obstacle-penetrating delivery across large facilities without the high power drain of Wi-Fi or Cellular networks.
4.  **Data Aggregation (The Gateway):** A centralized Receiver Gateway aggregates LoRa packets from multiple nodes and acts as the network backbone.
5.  **Cloud Visualization:** The Gateway synchronizes data via Wi-Fi to the **Blynk IoT Cloud**, updating a real-time mobile dashboard with a latency of **< 3.6 seconds**.



---

## ⚙️ Key Engineering Highlights

* **Advanced Sensor Fusion:** Fused acoustic (**JSN-SR04T**) and magnetic field (**GY-271**) data to achieve **100% detection accuracy** in prototype trials.
* **Listen-After-Talk (LAT) Protocol:** Engineered custom communication logic allowing the Gateway to send Over-The-Air (OTA) calibration commands during a brief 500ms receive window, maximizing battery life.
* **Remote Debugging & Modularity:** Implemented an administrative serial interface to dynamically add/remove nodes and adjust sensor sensitivity without reflashing firmware.
* **High ROI Infrastructure:** Designed the hardware stack at ~**$36 per node**, an **80%+ cost reduction** compared to industrial alternatives ($180–$230).

---

## 🛠️ Technology Stack

| Layer | Technology |
| :--- | :--- |
| **Edge Compute** | Heltec WiFi LoRa 32 V2 (ESP32) |
| **Sensors** | JSN-SR04T (Ultrasonic), GY-271 / HMC5883L (Magnetometer) |
| **Protocols** | LoRa (SX1276), I2C, SPI, Wi-Fi (802.11 b/g/n) |
| **Cloud & UI** | Blynk IoT Platform, OLED (SSD1306) |
| **Power** | 18650 Li-Ion, BMS, SX1808 Boost Converter |

---

## 📥 Installation & Setup

### 1. Firmware Configuration
Open the .ino files in the Arduino IDE.

Install the Heltec ESP32 and Blynk libraries.

Input your BLYNK_AUTH_TOKEN and Wi-Fi credentials in the Gateway script.

## 📄 Full Documentation
For a deep dive into the system schematics, latency statistical analysis, and C++ firmware code, please view the full academic paper included in this repository:
SMART PARK IoT Sensor Fusion & LoRa Data Pipeline

## 🛡️ Disclaimer
This project was developed for academic research purposes. Always ensure compliance with local radio frequency regulations (e.g., 915MHz ISM band usage) when deploying LoRa hardware.
