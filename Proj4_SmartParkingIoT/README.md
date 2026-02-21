🚗 SMART PARK: IoT Sensor Fusion & LoRa Data Pipeline
📊 Project Overview
SMART PARK is an end-to-end IoT system designed to eliminate urban parking congestion by providing real-time space availability. Built as an academic research project at the University of Southeastern Philippines (USeP), this system replaces expensive, single-modality sensors with a highly cost-effective, custom Sensor Fusion Edge Architecture.

The system accurately detects vehicular presence, filters out environmental "noise" (pedestrians, debris), and orchestrates the data over a long-range, low-power network (LoRa) to a cloud-based mobile dashboard.

🏗️ System Architecture & Data Flow
This project demonstrates a complete hardware-to-cloud data pipeline:

Data Generation (The Edge): Independent battery-operated Sensor Nodes are deployed at each parking slot.

Sensor Fusion Validation: The Heltec ESP32 microcontrollers process raw analog data at the edge. By utilizing a Boolean "AND" logic gate, the system requires both spatial proximity (Ultrasonic) and magnetic field disturbance (Magnetometer) to register a valid vehicle, virtually eliminating false positives.

Data Transmission (LPWAN): Validated state changes are packaged and transmitted via LoRa (Long Range) modulation at 915MHz. This ensures secure, obstacle-penetrating data delivery across large outdoor facilities without the power drain of Wi-Fi or Cellular networks.

Data Aggregation (The Gateway): A centralized Receiver Gateway aggregates the LoRa packets from up to 20 nodes and acts as the network backbone.

Cloud Visualization: The Gateway synchronizes the aggregated state data via Wi-Fi to the Blynk IoT Cloud, updating a real-time mobile dashboard with a latency of less than 3.6 seconds.

⚙️ Key Engineering Highlights
Advanced Sensor Fusion: Fused acoustic (JSN-SR04T) and magnetic field (GY-271) data to achieve 100% detection accuracy in prototype trials, filtering out non-ferrous soft obstacles.

Listen-After-Talk (LAT) Bidirectional Protocol: Engineered a custom communication logic allowing the Gateway to send Over-The-Air (OTA) calibration commands to specific nodes during a brief 500ms receive window, maximizing battery life.

Remote Debugging & Modularity: Implemented an administrative serial interface to dynamically add/remove nodes, adjust sensor sensitivity, and filter logs without reflashing firmware.

High ROI Infrastructure: Designed the custom hardware stack to cost approximately $36 per node, representing an 80%+ cost reduction compared to commercial industrial-grade alternatives ($180-$230).

🛠️ Technology Stack
Edge Compute: Heltec WiFi LoRa 32 V2 (ESP32)

Sensors: JSN-SR04T (Ultrasonic), GY-271 / HMC5883L (Magnetometer)

Protocols: LoRa (SX1276), I2C, SPI, Wi-Fi (802.11 b/g/n)

Cloud & UI: Blynk IoT Platform, OLED (SSD1306)

Power Management: 18650 Lithium-Ion, BMS, SX1808 Boost Converter

📄 Full Documentation
For a deep dive into the system schematics, latency statistical analysis, and C++ firmware code, please view the full academic paper included in this repository: SMART PARK IoT Sensor Fusion & LoRa Data Pipeline.
