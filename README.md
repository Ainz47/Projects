# Projects

A collection of 12 production-oriented projects spanning data engineering, AI pipelines, web scraping, IoT, and automation. Built in Python with occasional cloud infrastructure (Azure, Supabase, GCP).

---

## Projects

| # | Project | Domain | Stack |
|---|---------|--------|-------|
| 1 | [SchoolJobs](#1-schooljobs) | Web Scraping | Python, Playwright, SQLite |
| 2 | [ShopeeHijacker](#2-shopeehijacker) | E-commerce Scraping | Python, Playwright CDP |
| 3 | [PDFExtractor](#3-pdfextractor) | Document Processing | Python, pdfplumber, SQLite |
| 4 | [SmartParkingIoT](#4-smartparkingiot) | IoT / Embedded | C++, ESP32, LoRa, Blynk |
| 5 | [WordPress ACF REST API](#5-wordpress-acf-rest-api) | CMS Integration | Python, WordPress REST API |
| 6 | [Cloud Report Engine](#6-cloud-report-engine) | PDF Generation | Python, FastAPI, Supabase, WeasyPrint |
| 7 | [FastAPI ETL Alerts](#7-fastapi-etl-alerts) | Real-time ETL | Python, FastAPI, Supabase, Discord |
| 8 | [Arxiv Pipeline](#8-arxiv-pipeline) | Data Engineering | Python, dbt, Kestra, Azure, MotherDuck |
| 9 | [GeoData AI Ingestion Engine](#9-geodata-ai-ingestion-engine) | AI Data Pipeline | Python, Gemini, Playwright, WordPress |
| 10 | [NYC BIS Violation Monitor](#10-nyc-bis-violation-monitor) | Public Data / ETL | Python, NYC Open Data API |
| 11 | [Rank Rent Automation](#11-rank-rent-automation) | SEO Automation | Python, Flask, Gemini, Pexels, WordPress REST API |
| 12 | [AI Lead Generator](#12-ai-lead-generator) | B2B Lead Gen | Python, Claude, Gemini, Apify |

---

## 1. SchoolJobs

WAF-bypassing scraper that pulls job listings from the SchoolSpring/PowerSchool ATS platform. Uses Playwright to harvest session cookies, then hits the internal API directly with Requests for bulk extraction.

**Stack:** Python · Playwright · Requests · Pandas · SQLite  
**Highlights:** Reverse-engineered `GetPagedJobsWithSearch` API endpoint; batch fetches 1,000+ records per call; stores to SQLite.

[→ View project](Proj1_SchoolJobs/)

---

## 2. ShopeeHijacker

Stealth e-commerce scraper that attaches to an existing Chrome window via Chrome DevTools Protocol and passively intercepts live Shopee API responses — no bot-triggering requests sent.

**Stack:** Python · Playwright CDP · Pandas  
**Highlights:** Zero suspicious request footprint; mouse.wheel() pagination to mimic human behavior; ID-based deduplication across pages.

[→ View project](Proj2_ShopeeHijacker/)

---

## 3. PDFExtractor

Automated pipeline that discovers procurement PDFs on school district websites and extracts structured fields (budget approvals, bid deadlines) using pdfplumber and regex — all in-memory, no disk writes.

**Stack:** Python · Playwright · pdfplumber · SQLite  
**Highlights:** Three-layer architecture (discovery → ingestion → extraction); fully in-memory byte-stream processing, so it is cloud-ready for AWS Lambda or a CI runner.

[→ View project](Proj3_PDFExtractor/)

---

## 4. SmartParkingIoT

Academic IoT prototype for urban parking management. Sensor nodes use AND-gate fusion of ultrasonic and magnetometer readings to detect vehicles, then relay status over LoRa to a Wi-Fi gateway that syncs to Blynk cloud.

**Stack:** C++ · Heltec ESP32 · LoRa SX1276 · Blynk IoT · Arduino IDE  
**Highlights:** <3.6 s cloud latency; Listen-After-Talk protocol for battery savings; ~$36/node (80% cheaper than industrial alternatives).

[→ View project](Proj4_SmartParkingIoT/)

---

## 5. WordPress ACF REST API

Idempotent data pipeline that syncs external JSON datasets to WordPress custom post types with ACF Pro field mapping. Includes an AI enrichment hook (Gemini) for SEO-optimized copy generation.

**Stack:** Python · WordPress REST API · ACF Pro · Gemini  
**Highlights:** MD5 hash idempotency prevents duplicate posts; pre-flight conflict resolution via REST queries; Application Password auth.

[→ View project](Proj5_WordPress_ACF_REST_API/)

---

## 6. Cloud Report Engine

Backend microservice that ingests quiz-response webhooks, runs a rules-based lead-scoring engine, persists results to Supabase, and renders a branded PDF report via WeasyPrint.

**Stack:** Python · FastAPI · Supabase (PostgreSQL) · Jinja2 · WeasyPrint  
**Highlights:** Normalized 0–100 scoring with tier assignment; Jinja2 templates keep layout decoupled from logic; modular design (engine, db_client, pdf_generator).

[→ View project](Proj6_Cloud_Report_Engine/)

---

## 7. FastAPI ETL Alerts

Real-time ETL microservice that aggregates restaurant POS data (Toast) and labor data (7shifts), calculates Cost Per Labor Hour and Labor %, persists to Supabase, and fires Discord/Slack alerts when thresholds are breached.

**Stack:** Python · FastAPI · Pydantic · Supabase (PostgreSQL) · Discord Webhooks  
**Highlights:** BackgroundTasks for non-blocking ETL; idempotent UPSERT; Swagger UI auto-generated from Pydantic models; mock data simulator included.

[→ View project](Proj7_FastAPI_ETL_Alerts/)

---

## 8. Arxiv Pipeline

Full data engineering capstone (DE Zoomcamp). Batch ETL pulls arXiv math papers via API, stages parquet chunks to Azure Data Lake, transforms with dbt in MotherDuck (DuckDB), orchestrated by Kestra, visualized in Metabase.

**Stack:** Python · Terraform · Azure Blob Storage · MotherDuck (DuckDB) · dbt · Kestra · Metabase · Docker  
**Highlights:** IaC-provisioned Azure infrastructure; MD5 surrogate keys for 100% pipeline idempotency; dbt clustering on timestamp + category; custom Metabase Dockerfile for DuckDB JDBC.

[→ View project](Proj8_Arxiv_Pipeline/)

---

## 9. GeoData AI Ingestion Engine

Three-phase AI pipeline: scrapes business data from Google Maps (Playwright), enriches it with Gemini (text descriptions + image quality validation + image generation), then publishes to WordPress via REST API.

**Stack:** Python · Playwright · Google Gemini API · WordPress REST API · Pillow · FastAPI  
**Highlights:** Gemini Vision for image relevance filtering; AI image generation for missing gallery assets; MD5 place_id idempotency; fallback chain when AI quotas are hit.

[→ View project](Proj9_GeoData_AI_Ingestion_Engine/)

---

## 10. NYC BIS Violation Monitor

Tracks building violations for NYC properties by querying the official DOB Open Data endpoint with SoQL filters. Deduplicates on BIN + violation number, outputs CSV or JSON, and is designed for Google Sheets / Airtable integration.

**Stack:** Python · NYC DOB Open Data API (SoQL) · SQLite · CSV/JSON  
**Highlights:** Official API source (more reliable than HTML scraping); address normalization; CLI flags for borough, date range, limit, and output format.

[→ View project](Proj10_NYC_BIS_Violation_Monitor/)

---

## 11. Rank Rent Automation

Local Flask app that provisions a complete rank-and-rent WordPress site from a single form. Gemini writes the copy and Pexels supplies the imagery, then the tool publishes a homepage, one page per service, blog posts with a listing page, 12 FAQs, and a contact page with a quote form and Maps embed.

**Stack:** Python · Flask · Google Gemini · Pexels API · WordPress REST API  
**Highlights:** Live progress over SSE; content cache and Retry Failed so re-runs are idempotent; AI-driven internal interlinking; deployment history and one-click site reset; 14 pages published per run.

[→ View project](Proj11_Rank_Rent_Automation/)

---

## 12. AI Lead Generator

B2B lead generation system for web design agencies. Scrapes local service businesses via Apify/Google Maps, scores their websites on modernity and SEO, uses Claude + Gemini to generate redesign concepts and personalized cold emails, exports to CSV.

**Stack:** Python · Anthropic Claude · Google Gemini · Apify · BeautifulSoup4 · Pandas · httpx  
**Highlights:** Multi-model AI with auto-detection and fallback; async concurrent processing; HTML mockup generation per lead; CLI params for service category, city, state, and result count.

[→ View project](Proj12_AI_Lead_Generator/)

---

## Tech at a Glance

**Languages:** Python (primary), C++ (IoT firmware), HCL (Terraform)  
**Data / ETL:** dbt · MotherDuck (DuckDB) · Supabase (PostgreSQL) · SQLite · Parquet  
**AI / LLMs:** Anthropic Claude · Google Gemini (text + vision + image gen)  
**Orchestration & Infra:** Kestra · Azure Blob Storage · Terraform · Docker  
**Web / APIs:** FastAPI · WordPress REST API · Playwright · BeautifulSoup4  
**Visualization:** Metabase · Jinja2 / WeasyPrint (PDF)
