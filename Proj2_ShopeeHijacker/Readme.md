Shopee-CDP-Interceptor 🛒
Live Session Hijacking & Passive API Interception Pipeline
A stealth-focused data extraction tool that leverages the Chrome DevTools Protocol (CDP) to attach to authenticated browser sessions and intercept backend JSON responses in real-time.
🏗️ The Engineering Approach
Scraping modern e-commerce platforms like Shopee is often hindered by aggressive rate-limiting and complex Javascript challenges. This project bypasses those hurdles using two primary architectural patterns:

1. CDP Session Hijacking
Instead of launching a "clean" bot instance that looks suspicious, this script uses connect_over_cdp to "hijack" a pre-existing Chrome window. This allows the engineer to manually solve CAPTCHAs or log in, while the script handles the repetitive data collection.

2. Passive Network Interception
Rather than mimicking the browser's requests (which can be fingerprinted), this pipeline acts as a Network Listener. It monitors the response event for specific API endpoints (/api/v4/search/search).

The Advantage: We capture the raw, high-precision data before it is truncated or rounded by the frontend UI.Data 
Integrity: Prices are extracted as raw integers and converted ($Price = \frac{raw}{100,000}$) to maintain 100% accuracy.

🛠️ Tech Stack
Automation Engine: Playwright (Python)
Protocol: Chrome DevTools Protocol (CDP)
Data Science: Pandas (De-duplication & CSV Serialization)
Target: Shopee Philippines (v4 Search API)

🚀 Key Engineering Features
Stealth Pagination: Implements a coordinate-based scrolling mechanism (page.mouse.wheel) to mimic human browsing behavior, triggering the lazy-loading of API responses.
ID-Based De-duplication: Uses Pandas to ensure that overlapping search results across multiple pages do not result in duplicate entries.

📥 Setup & Execution
Launch Chrome in Debug Mode:
Close all Chrome windows and run this via your terminal:

chrome.exe --remote-debugging-port=9222
Clone and Install:

git clone https://github.com/JhuraldHilary/Shopee-CDP-Interceptor.git
pip install playwright pandas

Run the Interceptor:
python shopee_hijack.py

🛡️ Disclaimer
This project is for educational use and technical demonstration of CDP-based data pipelines. Always adhere to the platform's Terms of Service.
