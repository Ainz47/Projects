# 📋Dependencies

This document provides a comprehensive map of the technical stack, library versions, and system dependencies required to maintain and reproduce the **arXiv Research Data Pipeline**.

---

## 💻 1. System Requirements
* **Operating System:** Windows 10/11 with **WSL2 (Ubuntu 22.04+)** or a native Linux environment (Debian-based preferred).
* **Memory:** Minimum **8GB RAM** is required. The simultaneous execution of Kestra, dbt, and Metabase within Docker typically consumes ~5-6GB of memory.
* **Storage:** ~2GB of local disk space for container images and temporary Parquet processing chunks.

---

## ☁️ 2. External Services & Cloud
* **Azure Blob Storage:** Requires an active Storage Account and a container named `raw-parquet-chunks`.
* **MotherDuck:** Serverless DuckDB cloud instance. Requires an **Authentication Token**.
* **arXiv API:** Public access; however, the pipeline respects the mandatory **3-second request interval** to prevent IP throttling.

---

## 🐋 3. Containerization & Orchestration
* **Docker Engine:** v24.0.0+
* **Docker Compose:** v2.20.0+
* **Kestra:** v0.17.0 (Standard Edition) for workflow orchestration and task scheduling.

---

## 🐍 4. Python Extraction Layer (Python 3.11+)
The `extract.py` script utilizes the following libraries for data retrieval and cloud streaming:

| Library | Version | Purpose |
| :--- | :--- | :--- |
| `requests` | ^2.31.0 | API communication and pagination logic. |
| `pandas` | ^2.1.0 | In-memory data structuring and cleaning. |
| `pyarrow` | ^14.0.0 | High-performance Parquet serialization. |
| `azure-storage-blob` | ^12.19.0 | Streaming data directly to Azure Data Lake. |
| `python-dotenv` | ^1.0.0 | Secure management of environment variables. |

---

## 💎 5. Transformation Layer (dbt)
The transformation environment is specifically pinned to ensure compatibility between the dbt adapter and the MotherDuck serverless protocol.

* **`dbt-core`**: 1.7.18
* **`dbt-duckdb`**: 1.7.1
* **`duckdb`**: **1.4.4** (Pinned to prevent protocol mismatches with MotherDuck's engine).

---

## 📊 6. Visualization Layer (Metabase)
To overcome shared library conflicts (`glibc` vs `musl`), the Metabase environment is built on a custom Ubuntu-based image with the following dependencies:

* **Base Runtime:** `eclipse-temurin:21-jre-jammy` (Provides the necessary `glibc` environment).
* **System Libraries:** `libstdc++6`, `g++`, `libc6-compat`.
* **BI Software:** Metabase v0.50.21.
* **Database Driver:** `duckdb.metabase-driver.jar` (Community-sourced JDBC driver).

---

## 🛠️ 7. Infrastructure as Code
* **Terraform:** v1.5.0+ 
* **Azure Provider:** Used to provision the Resource Group and Storage Account containers automatically.
