# SchoolSpring-Hybrid-Extractor ⚡
### Session Bridging: Playwright + Requests API Scraper

A high-performance Data Engineering pipeline designed to bypass enterprise-grade Web Application Firewalls (WAF) by bridging browser-based session authentication with low-overhead HTTP requests.

---

## 🏗️ Architecture Overview
Most modern Applicant Tracking Systems (ATS) like SchoolSpring/PowerSchool utilize security layers (e.g., Incapsula/Imperva) that block standard headless scrapers. This project implements a **Hybrid Extraction Strategy**:

1. **Session Initiation (The Handshake):** Uses Playwright to launch a headless Chromium instance, navigating the front-end to solve the WAF challenge and generate valid security cookies.
2. **State Transfer (The Bridge):** Programmatically extracts the `raw_cookies` from the Playwright browser context and maps them into a Python dictionary.
3. **High-Speed Ingestion (The Extraction):** Injects the "stolen" cookies into a Requests session to hit the backend API directly. 

> **The Result:** Near-instantaneous data retrieval of 1,000+ records in a single network call, bypassing DOM rendering entirely.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Automation** | Playwright (Chromium) | Initial WAF bypass & Cookie generation |
| **Networking** | Requests | High-speed API communication |
| **Data Processing** | Pandas | JSON flattening & CSV export |
| **Target** | SchoolSpring/PowerSchool | `GetPagedJobsWithSearch` API Endpoint |

---

## 🚀 Key Engineering Features

* **WAF Persistence:** Successfully navigates the Incapsula firewall that typically triggers `403 Forbidden` errors for standard bots.
* **API Reverse-Engineering:** Targets the JSON backend via the `size=1000` parameter hack, drastically reducing bandwidth and execution time.
* **Headless-First:** Optimized to run in Linux/CI environments (GitHub Actions ready).
* **Data Normalization:** Automatically converts nested JSON API responses into a flattened CSV for immediate analysis.

---

## 📥 Installation & Usage

### 1. Clone the Repository

```bash
git clone [https://github.com/JhuraldHilary/School-ATS-API-Scraper.git](https://github.com/JhuraldHilary/School-ATS-API-Scraper.git)
cd School-ATS-API-Scraper
```

2. Install Dependencies

```bash
pip install playwright pandas requests
playwright install chromium

3. Run the Pipeline
Bash

python hybrid_scraper.py
📊 Output
The script generates ultimate_hybrid_jobs.csv, containing structured data including:

Identifiers: JobId, Title, Organization

Details: Location, SalaryRange

Metadata: PostDate, Category

🛡️ Disclaimer
This project was developed for educational purposes and to demonstrate advanced data extraction techniques. Always ensure compliance with the target website's robots.txt and Terms of Service.
