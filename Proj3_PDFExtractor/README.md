# Automated-PDF-Intelligence-Pipeline 📄🔍

### **End-to-End PDF Discovery, Stream-Extraction, and SQL Persistence**

A robust Python-based Data Engineering pipeline designed to automate the lifecycle of unstructured document processing. This system discovers PDF links on dynamic web pages, processes them in-memory as byte streams to optimize performance, and extracts high-priority data points into a structured SQLite database.

---

## 🏗️ Architecture Overview

Handling thousands of PDFs manually is a bottleneck. This pipeline implements a three-layer architecture:

1.  **Discovery Layer (Playwright):** Orchestrates a headless browser to navigate dynamic, JavaScript-heavy portals (like school district procurement pages) and identifies document URLs.
2.  **Ingestion Layer (Requests + IO):** Downloads documents as `BytesIO` streams. This "No-Disk" approach allows the pipeline to run in memory, making it highly compatible with cloud environments like GitHub Actions or AWS Lambda.
3.  **Extraction Layer (pdfplumber + Regex):** Performs granular text extraction from the byte stream. It utilizes Regular Expressions (Regex) to clean and normalize data such as "Approved Budget for the Contract" (ABC) and "Bid Deadlines".



---

## 🛠️ Tech Stack
* **Automation:** Playwright (Headless Chromium)
* **Document Processing:** `pdfplumber`, `io`
* **Data Persistence:** SQLite3 (SQL-based relational storage)
* **Data Cleaning:** Regex (Regular Expressions) & Pandas
* **Execution:** Standalone CLI script (no local storage required, so it schedules cleanly under cron or a CI runner)

---

## 🚀 Key Engineering Features
* **Memory Efficiency:** Processes PDF files directly from the network stream, bypassing the need for local storage and reducing I/O overhead.
* **Automated Discovery:** Automatically identifies `.pdf` links even when nested inside dynamic UI elements or accordions.
* **Relational Storage:** Moves beyond flat CSVs by utilizing a structured SQL schema for better data integrity, indexing, and future dashboard integration.
* **Repeatable Runs:** Writes into a persistent SQL schema rather than a fresh flat file each time, so the script can be re-run on a schedule to keep the database topped up with the latest leads.

---

## 📥 Setup & Usage

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Ainz47/Projects.git
   cd Proj3_PDFExtractor
   ```
   
2. **Install dependencies:**
   ```bash
   pip install playwright requests pdfplumber pandas
   playwright install chromium
   ```

3. **Initialize the Database & Run:**
   ```bash
   python PDFExtractor.py
   ```

## 📊 SQL Schema Example

The pipeline populates a `school_data.db` with the following structure:

* `id` — Primary Key (auto-increment)
* `district_name` — Extracted source identifier
* `doc_type` — Classification (e.g. "Invitation to Bid")
* `meeting_date` — Extracted and normalized date
* `extracted_text` — Raw text snippet for verification
* `source_url` — Traceability back to the original document

---

## 🛡️ Disclaimer
This project was developed for educational and professional demonstration purposes. It demonstrates advanced technical troubleshooting and systems logic applied to data extraction.


