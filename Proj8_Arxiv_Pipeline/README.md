# 🚀 End-to-End Mathematics Research Data Pipeline (DE Zoomcamp Capstone)

## 📖 1. Problem Description
**The Problem:** The arXiv repository contains millions of academic papers, but tracking the explosive growth of specific mathematical sub-disciplines over the last 30 years is difficult. 
**The Solution:** This project builds a batch-processed, end-to-end Data Engineering pipeline that extracts historical Mathematics and Physics research papers (1992–Present) from the arXiv API, loads them into an Azure Data Lake, transforms them into a dimensional model, and serves them to an interactive dashboard for trend analysis.

## ☁️ 2. Cloud & Infrastructure as Code (IaC)
* **Cloud Providers:** Azure (Blob Storage) & MotherDuck (Serverless Cloud Data Warehouse).
* **IaC:** Terraform is used to provision the Azure Resource Group and the `raw-parquet-chunks` Data Lake container.

## 🔄 3. Data Ingestion (Batch Orchestration)
* **Orchestrator:** Kestra (Containerized via Docker).
* **Workflow:** A fully declarative Kestra DAG triggers a custom Python extraction script. To prevent Out-Of-Memory (OOM) crashes, the script paginates the arXiv API, chunks records into batches of 10,000, and streams them as compressed `.parquet` files directly into the Azure Data Lake.

## 🗄️ 4. Data Warehouse (Clustering & Partitioning)
* **Warehouse:** MotherDuck (DuckDB).
* **Optimization Strategy:** The `fact_math_papers` table is optimized using DuckDB's native clustering equivalent (`order_by`). The table is physically sorted on disk by `published_timestamp` and `primary_category`. 
* **Explanation:** This optimization specifically serves the upstream Metabase dashboard. Because the primary dashboard tiles aggregate paper volume over time and filter by category, sorting by these specific columns minimizes IO operations and drastically speeds up query execution.

## 🛠️ 5. Transformations (dbt)
* **Tool:** `dbt-core` with the `dbt-duckdb` adapter.
* **Lineage:** * `stg_arxiv_papers`: Cleans raw parquet data, casts data types (e.g., string dates to `TIMESTAMP`), and strips URL prefixes.
  * `fact_math_papers`: Applies MD5 hashing to the `paper_id` to generate a deterministic Surrogate Key (`paper_sk`). This ensures 100% pipeline idempotency and deduplication if the DAG is re-run.

## 📊 6. Dashboard
* **Tool:** Metabase (Deployed via custom Ubuntu Dockerfile to satisfy `glibc` dependencies for the C++ DuckDB JDBC driver).
* **Tiles:**
  1. **Temporal:** Line chart showing the exponential growth of published math papers over the decades.
  2. **Categorical:** Bar chart detailing the most popular mathematical sub-categories (e.g., High Energy Physics, Combinatorics).
  3. **Scorecard:** Total volume of papers successfully processed.

*<img width="1879" height="926" alt="image" src="https://github.com/user-attachments/assets/0ba8ca8e-e837-4cd8-bd92-2b9c899f9b8c" />
*

---

## 💻 7. Reproducibility (How to Run)

### Prerequisites
* Docker & Docker Compose
* Terraform
* An Azure account & a free MotherDuck account.

### Step 1: Infrastructure
```bash
cd infrastructure
terraform init
terraform apply
```
### Step 2: Set up Secrets
Create a .env file in the root directory and add your credentials:

```bash
AZURE_CONNECTION_STRING="your_azure_string"
MOTHERDUCK_TOKEN="your_md_token"
```

### Step 3: Orchestration

```bash
cd orchestration
docker compose up -d
```
Navigate to localhost:8080, enable the Kestra flow, and trigger the execution.

### Step 4: Transformation
```bash
cd transformation
docker build -t arxiv-dbt .
docker run --env-file ../.env arxiv-dbt
```

### Step 5: Visualization
```bash
cd visualization
docker compose up -d --build
```
Navigate to localhost:3000 to view the dashboard.

## 📈 8. Scalability & Future Work
While the current MVP successfully processes 10,000 records to validate the architecture, the system is designed to scale to the full 2M+ arXiv archive.

🚀 Scaling the Pipeline
Full Backfill Strategy: The extraction script is built with pagination. To ingest the entire historical dataset, the Kestra trigger can be updated to run a distributed loop. Given the arXiv API's 3-second rate limit, a full backfill of 500k math papers would take ~42 hours; the pipeline is designed to be resumable to handle potential network interruptions during this window.

Horizontal Scaling: By moving the Python extraction runtime from a local Docker container to Azure Kubernetes Service (AKS) or Azure Functions, the ingestion layer can scale horizontally to handle multiple categories (Physics, CS, Bio) in parallel.

Incremental Loads: The next phase involves implementing "Incremental" logic in dbt. Instead of rebuilding the fact_math_papers table daily, dbt would only process new papers published in the last 24 hours, drastically reducing compute costs in MotherDuck.

🛠️ Future Improvements
Automated Data Quality (dbt tests): Implementing generic and singular tests (e.g., not_null, unique) on the paper_sk to ensure 100% data integrity as the volume grows.

CI/CD Integration: Adding GitHub Actions to automatically run dbt test and terraform plan whenever code is pushed to the main branch.

Enhanced Monitoring: Integrating Kestra with an alerting system (like Slack or Discord) to notify the engineer immediately if an extraction batch fails.

Semantic Search: Implementing a Vector Database (like LanceDB or Pinecone) to allow for AI-powered semantic search over paper abstracts, moving beyond simple categorical filtering.
