# SmartParkingIoT

An IoT parking-occupancy system built as a university capstone paper: ultrasonic and magnetometer sensors fused with an AND gate at the edge (ESP32), reporting over LoRa to a gateway that syncs to Blynk's cloud dashboard.

## Authorship

This is a four-author academic paper, not solo work: Michaela S. Abordaje, Chelsea B. Baltazar, Jhurald Hilary Lantape, and Glyzy M. Paña, all BS Electronics Engineering, University of Southeastern Philippines. The paper is the actual deliverable and is included in full in this repository (`SMART PARK IoT Sensor Fusion & LoRa Data Pipeline1.pdf`). What follows is a summary of what the paper itself reports, not an independent re-verification, since this is hardware that can't be re-run for a README.

## What it does

Two sensors per parking slot (JSN-SR04T ultrasonic for spatial presence, GY-271/HMC5883L magnetometer for ferrous-metal confirmation) feed an ESP32 running an AND-gate rule: a slot is only marked occupied when both the ultrasonic reading and the magnetic disturbance cross their thresholds at once. This is specifically meant to reject false positives from pedestrians and debris, which trip an ultrasonic-only sensor but not a magnetometer. Confirmed state changes go out over LoRa (915MHz) to a receiver gateway, which relays them over Wi-Fi to Blynk's cloud dashboard. A serial admin interface on the gateway supports adding/removing nodes and remote threshold calibration without reflashing firmware, using a Listen-After-Talk pattern (each node opens a 500ms receive window after transmitting, so the gateway can queue commands without keeping the radio on constantly and draining the battery).

## What the paper reports

- **Sensor fusion logic, verified in a controlled bench test (paper Section VI.II):** the AND gate was tested against three isolated scenarios (non-metallic object only, magnetic interference only, both signals together) before combined trials. All three behaved as designed: an object alone or a magnetic disturbance alone stayed "FREE," both together read "OCCUPIED."
- **100% detection accuracy, but scoped to 39 controlled trials (paper Table II, Section VI.III):** across 13 state-transition scenarios (arrivals, departures, simultaneous entries, rapid swaps), each run 3 times, every trial produced the correct FREE/OCCUPIED read. This is a lab/prototype result, not a claim about long-term accuracy in a real, unattended parking lot; the paper's own recommendations section calls for further field testing under real weather and traffic conditions as future work.
- **Response latency averaged 3.6 seconds across all trials (paper Table I, Section VII conclusion), with per-scenario averages ranging from 2.3s (fastest, a single-flag update) to 5.33s (slowest, both slots clearing at once).** The paper compares this to a cited 5-15 second range for other cloud-centric parking systems, calling its own result "superior," but that comparison is the paper's own citation-based framing, not a head-to-head benchmark run against another system here.
- **Cost: about ₱1,989.50 (~$36) per node, against a cited $180-$230 for commercial industrial units.** The paper states two different reduction percentages for this same comparison: "78%" in the conclusion and "80-85%" in the cost-benefit section. Doing the arithmetic on the paper's own numbers lands at roughly 80-84%, closer to the second figure; treat both percentages as the paper's own claims, not something independently re-derived here.

## What is NOT verified here

- This README was written by reading the paper and the firmware source in the PDF appendices, not by re-flashing or re-running the hardware. Nothing in this repository was re-tested for this rewrite.
- No automated tests, no CI, no field deployment beyond the paper's own prototype trials.
- The "both slots" and multi-node scenarios in the paper's Section VI.III photos show handheld sensor units on a bench, not sensors permanently installed under real parking spaces; a couple of the later trial photos (Scenes C-E) do show real parked cars at night, which suggests at least some trials moved outdoors, but the paper does not describe a permanent lot installation.
- Whether the firmware in the PDF appendices matches exactly what ran during the reported trials, or was cleaned up afterward for publication, isn't something this README can confirm either way.

## Stack

Heltec WiFi LoRa 32 V2 (ESP32) · JSN-SR04T ultrasonic sensor · GY-271/HMC5883L magnetometer · LoRa (SX1276, 915MHz) · I2C, SPI, Wi-Fi · Blynk IoT platform · OLED (SSD1306) · 18650 Li-Ion with a BMS and boost converter · Arduino/C++

## Documentation

The full paper, including system architecture diagrams, the complete latency and accuracy tables, firmware listings for both the transmitter node and the receiver gateway, and the cost breakdown, is included in this repository: [SMART PARK IoT Sensor Fusion & LoRa Data Pipeline (PDF)](./SMART%20PARK%20IoT%20Sensor%20Fusion%20&%20LoRa%20Data%20Pipeline1.pdf).

## Disclaimer

Developed for academic research. Deploying LoRa hardware requires complying with local radio frequency regulations (915MHz ISM band usage varies by region).
