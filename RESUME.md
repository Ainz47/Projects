# JHURALD HILARY A. LANTAPE (Larz)
### Full-Stack Data Engineer | Systems Architect (ECE)
📍 Santa Cruz, Davao del Sur, Philippines | ✉️ jhuraldhilary@gmail.com  
🔗 **GitHub:** [Ainz47/Projects](https://github.com/Ainz47/Projects) | 🔗 **LinkedIn:** [jhuraldhilarylantape](https://linkedin.com/in/jhuraldhilarylantape/)

---

## 🚀 PROFESSIONAL SUMMARY
Third-year Electronics Engineering (ECE) student and aspiring Data Engineer with a focus on **Infrastructure as Code (IaC)**, **cloud-native data warehousing**, and **decoupled systems architecture**. Proven ability to build resilient, end-to-end data pipelines and resolve complex system dependency conflicts in containerized environments. Dedicated to engineering high-availability solutions for remote-first international teams.

---

## 🛠️ TECHNICAL SKILLS
* **Cloud & Data Warehousing:** Azure (Blob Storage), MotherDuck (Cloud DuckDB), Terraform (IaC).
* **Data Engineering:** dbt-core (Modeling/Testing), Kestra (Orchestration), Python (Advanced), PostgreSQL, Idempotent Logic, MD5 Surrogate Keys.
* **Systems & Linux:** Docker/Docker Compose, Linux Internals (glibc/musl troubleshooting), Obsidian for knowledge management.
* **Extraction:** API Reverse-Engineering, Playwright, Requests, JSON Payload processing.
* **Hardware & Electronics:** ESP32 microcontrollers, circuit design, digital logic, and electronics repair.

---

## 💻 TECHNICAL PROJECTS

**End-to-End Research Data Warehouse (arXiv)** | `Terraform` `Azure` `Kestra` `dbt` `MotherDuck`
* Architected a scalable batch-processing pipeline to extract and warehouse ~500,000 academic papers (validated on 10k+ records).
* Developed an **OOM-resilient ingestion layer** using Python-based streaming and compressed Parquet chunking to minimize memory overhead.
* Engineered a dimensional model in **dbt** utilizing **MD5 hashing** for surrogate keys to ensure 100% pipeline idempotency and deduplication.
* Optimized warehouse performance in **MotherDuck** by implementing physical clustering (`order_by`) on temporal and categorical columns, reducing BI query latency.
* **System Integration Win:** Authored a custom Ubuntu-based Dockerfile to resolve native C++ library conflicts (`glibc`) for the DuckDB JDBC driver, enabling stable Metabase visualization.

**Restaurant OS: Event-Driven ETL Microservice** | `FastAPI` `PostgreSQL` `Webhooks`
* Architected a high-speed FastAPI microservice to ingest asynchronous JSON payloads from fragmented SaaS silos (Toast POS & 7shifts).
* Implemented **FastAPI BackgroundTasks** to compute real-time KPIs (CPLH, Contribution Margins) without blocking upstream API services.
* Engineered **idempotent UPSERT logic** in a PostgreSQL environment to ensure data integrity during out-of-order data events.

**Smart Park: IoT Sensor Fusion** | `ESP32` `Hardware Logic`
* Engineered a dual-sensor fusion system using Magnetometers and Ultrasonic sensors on ESP32 nodes to detect vehicle occupancy using hardware-level "AND" logic.

---

## 🎓 EDUCATION
**Bachelor of Science: Electronics Engineering (ECE)** | 2023 – Present (Expected 2028)
*Davao del Sur State College (DSSC)*
* Currently in **3rd Year** of a 5-year program.
* Focus on digital logic, signals and systems, and assembly language programming for DOSBox.

---

## 💼 LEADERSHIP & OTHER EXPERIENCE
**Family Church Preacher & Devotional Lead** | 2025 – Present
* Assigned monthly preaching and devotional duties, developing strong public speaking and communication skills.

**Digital Asset & Video Editor** | 2018 – 2021
* Managed heavy digital asset workloads and backups in professional video editing environments.

---

## 🔧 TOOLS & INTERESTS
* **Note-taking:** Obsidian.
* **Calculator:** Canon F-789SGA (Complex number calculations).
* **Interests:** Sourdough baking, beekeeping (native *Apis cerana*), and troubleshooting consumer electronics.
