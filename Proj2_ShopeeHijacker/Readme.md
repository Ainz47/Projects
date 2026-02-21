### Live Session Hijacking & Passive API Interception Pipeline

A stealth-focused data extraction tool that leverages the **Chrome DevTools Protocol (CDP)** to attach to authenticated browser sessions and intercept backend JSON responses in real-time.

---

## 🏗️ The Engineering Approach

Scraping modern e-commerce platforms like Shopee is often hindered by aggressive rate-limiting, TLS fingerprinting, and complex JavaScript challenges. This project bypasses those hurdles using two primary architectural patterns:

### 1. CDP Session Hijacking
Instead of launching a "clean" bot instance—which is easily flagged by anti-bot services—this script uses `connect_over_cdp` to "hijack" a pre-existing Chrome window. This allows the engineer to manually solve CAPTCHAs or log in, while the script handles the repetitive data collection.

### 2. Passive Network Interception
Rather than mimicking the browser's requests (which can be fingerprinted via headers and cookies), this pipeline acts as a **Network Listener**. It monitors the response event for specific API endpoints (e.g., `/api/v4/search/search`).

* **The Advantage:** We capture raw, high-precision data before it is truncated or rounded by the frontend UI.
* **Data Integrity:** Prices are extracted as raw integers and converted ($Price = \frac{raw}{100,000}$) to maintain 100% accuracy.

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
| :--- | :--- | :--- |
| **Automation Engine** | Playwright (Python) | Browser control and event listening |
| **Protocol** | Chrome DevTools Protocol (CDP) | Low-level browser communication |
| **Data Science** | Pandas | De-duplication & CSV Serialization |
| **Target** | Shopee Philippines | v4 Search API |

---

## 🚀 Key Engineering Features

* **Stealth Pagination:** Implements a coordinate-based scrolling mechanism (`page.mouse.wheel`) to mimic human browsing behavior, triggering the lazy-loading of API responses.
* **ID-Based De-duplication:** Uses Pandas to ensure that overlapping search results across multiple pages do not result in duplicate entries.
* **Zero-Request Footprint:** Because it intercepts existing traffic, the script does not trigger the platform's "suspicious request volume" flags.

---

## 📥 Setup & Execution

### 1. Launch Chrome in Debug Mode
Close all existing Chrome windows and run the following via your terminal to open a listener port:

```bash
# Windows
chrome.exe --remote-debugging-port=9222

# macOS
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome --remote-debugging-port=9222
```

2. Clone and Install

```bash
git clone https://github.com/Ainz47/Projects.git
cd Proj2_ShopeeHijacker
pip install playwright pandas
```

3. Run the Interceptor
Ensure you are logged into Shopee in the debug window, then execute:

```bash
shopee_hijacker.py
```
🛡️ Disclaimer
This project is for educational use and technical demonstration of CDP-based data pipelines. Always adhere to the platform's Terms of Service and Robot.txt guidelines. The authors are not responsible for any misuse of this tool.

