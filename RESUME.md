# JHURALD HILARY A. LANTAPE 
### Data Engineer | Electronics Engineering (ECE) Student 
📍 Davao del Sur, Philippines | ✉️ jhuraldhilary@gmail.com   
🔗 **GitHub:** [Ainz47/Projects](https://github.com/Ainz47/Projects) | 🔗 **LinkedIn:** [jhuraldhilarylantape](https://linkedin.com/in/jhuraldhilarylantape/) 

---

## 🚀 PROFESSIONAL SUMMARY
Data Engineer Electronics Engineering (ECE) Student at the University of Southeastern Philippines (USeP). Specializing in decoupled backend architecture, event-driven ETL pipelines, and real-time operational intelligence. Expert in replacing fragmented manual workflows with secure, automated cloud systems that maintain strict data integrity.

---

## 🛠️ TECHNICAL SKILLS
* **Backend & Data:** Python (Adv), FastAPI, PostgreSQL, Supabase, ETL, Idempotent Logic, Pydantic, Pandas.
* **Cloud & Data Engineering:** Azure Blob Storage, MotherDuck (DuckDB), Kestra, dbt (Core), Terraform, Parquet.
* **Automation & Web Scraping:** Browser Automation, Anti-Bot Mitigation, API Reverse-Engineering, Playwright, Requests.
* **Engineering & Tools:** Git/GitHub, LoRa, ESP32, SQLite, Regex, Excel (Adv), Video/Audio Transcoding.

---

## 📜 CERTIFICATIONS
**Data Engineering Zoomcamp 2026 | DataTalks.Club** | *April 2026* * Intensive 9-week program covering the Modern Data Stack: Docker, Terraform, Airflow, dbt, BigQuery, and Spark. 
* Passed Final Capstone project.

---

## 💻 TECHNICAL PROJECTS

**DE Zoomcamp Capstone: Mathematics Research Data Pipeline** | `Azure` `MotherDuck` `Kestra` `dbt` `Terraform` 
* Architected an end-to-end batch pipeline ingesting 500k+ arXiv research papers (1992-Present) into Azure Data Lake using Terraform IaC. 
* Kestra DAG chunks records into 10,000-row compressed Parquet batches, eliminating OOM crashes across the full historical backfill.
* Built a dbt dimensional model with idempotent MD5 surrogate keys ensuring 100% pipeline idempotency across reruns. 
* Optimized MotherDuck (DuckDB) query performance via native clustering on published_timestamp and primary_category, reducing dashboard load times significantly.
* Deployed a Metabase dashboard (custom Ubuntu Dockerfile for DuckDB JDBC compatibility) visualizing exponential paper growth over 3 decades, top mathematical sub-disciplines, and total ingestion volume scorecard.

**Restaurant OS: Event-Driven ETL Microservice (Proj 7)** | `FastAPI` `PostgreSQL` `Webhooks` 
* Architected a high-speed FastAPI microservice ingesting async JSON payloads from Toast POS & 7shifts. 
* Used Background Tasks to compute real-time KPIs (CPLH, Contribution Margins) without blocking upstream services, reducing manual reporting time to zero.
* Engineered idempotent UPSERT logic in PostgreSQL (Supabase) guaranteeing 100% data integrity during out-of-order webhook events across concurrent SaaS data streams. 
* Defined complex schema mappings and synchronization rules to normalize fragmented POS data into a unified reporting layer.

**Intelligent Directory ETL Pipeline (Proj 9)** | `Playwright` `Gemini API` `FastAPI` 
* Architected an end-to-end AI-enriched ETL pipeline scraping business data (name, address, hi-res photos) from Google Maps via Playwright. 
* Leveraged Gemini API for LLM description generation and Vision-based image quality gates, discarding irrelevant assets before ingestion.
* Engineered idempotent WordPress REST API ingestion using MD5(name+address) as a surrogate place_id to prevent duplicate CPT records. 
* Built intelligent fallback logic routing to original scraped assets on AI quota failures, ensuring zero pipeline breakage. Validated end-to-end flow via a lightweight FastAPI mock WordPress server.

**Cloud-Native Report Engine (Proj 6) & WordPress REST API Pipeline (Proj 5)** | `Python` `Jinja2` `WeasyPrint` 
* Designed a decoupled pipeline processing raw payloads through a custom diagnostic rules engine. 
* Automated branded PDF report generation via WeasyPrint with a No-Disk ingestion layer, eliminating manual report creation entirely.
* Built a production-grade ETL pipeline bridging raw data scraping to structured CMS ingestion via REST API mapping. 
* Applied MD5 fingerprinting to ensure full idempotency during high-volume reruns.

**Enterprise Data Acquisition & IoT Suite (Proj 1-4)** | `LoRa` `ESP32` `Playwright` `Pandas` 
* **Smart Park & LoRa Gateway:** Engineered dual-sensor fusion (Magnetometer + Ultrasonic) on ESP32 for real-time vehicle occupancy detection. Built a LoRa-to-Cloud gateway streaming live data to Blynk IoT Cloud for remote monitoring.
* **API Extractors:** Developed an antibot-mitigation pipeline bypassing enterprise WAFs (Incapsula) via session bridging, and a Chrome DevTools Protocol (CDP) session interceptor for high-fidelity Shopee market intelligence.

---

## 🎓 EDUCATION
**Bachelor of Science: Electrical, Electronics and Communications Engineering** | *Expected Jun 2027* *University of Southeastern Philippines Obrero, Davao City* * **Leadership:** Technical Head, AECES (2025-2026) overseeing technical initiatives for the engineering student body.
* **Relevant Coursework:** Systems Logic, Advanced Mathematics, Technical Troubleshooting.

---

## 💼 OTHER PROFESSIONAL EXPERIENCE
**Digital Asset & Video Editor (Volunteer)** | *Global Impact, Davao City* | *Apr 2021 - Dec 2021* * Managed high-volume digital asset workloads for a global organization transcoding video/audio files, maintaining organized backups in a DAM system, and delivering production-ready media assets on tight deadlines.
