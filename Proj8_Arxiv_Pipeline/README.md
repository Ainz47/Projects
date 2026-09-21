# Arxiv Pipeline

A batch data engineering pipeline (built as a Data Engineering Zoomcamp capstone) that pulls Mathematics and Physics papers from the arXiv API, lands them in Azure Blob Storage as Parquet, transforms them with dbt on MotherDuck (cloud DuckDB), and serves the result to a Metabase dashboard. Infrastructure is provisioned with Terraform.

## What's actually here, verified by reading the code

- **Extraction (`extraction/extract.py`):** paginates the arXiv API (1,000 records per request, `math.*` category, a 3-second sleep between requests to respect arXiv's rate limit), buffers records in memory, and once 10,000 records accumulate, writes them to a local Parquet file and uploads it to Azure Blob Storage (`raw-parquet-chunks/raw/`). There is no checkpoint or resume logic: `start_index` lives only in a local variable, so if the script crashes or is killed partway through, the next run starts over from record 0, re-downloading and re-uploading everything already fetched. Any "resumable" claim in earlier versions of this README referred to a design intent for a future distributed backfill, not something this script does today.
- **Transformation (`transformation/arxiv_transform/models/`):** two dbt models. `stg_arxiv_papers.sql` reads the raw Parquet files directly from Azure (`azure://raw-parquet-chunks/raw/*.parquet`), strips the `http://arxiv.org/abs/` prefix off the id, and casts the published date to a timestamp. `fact_math_papers.sql` builds on that with `order_by=['published_timestamp', 'primary_category']` (DuckDB's physical sort/clustering) and an MD5 surrogate key. That key is hashed from `paper_id`, `title`, and `authors` concatenated together, not from `paper_id` alone as earlier documentation for this project said, and the column is named `paper_key`, not `paper_sk`.
- **Infrastructure (`infrastructure/main.tf`):** provisions an Azure resource group, a storage account, and one private blob container (`raw-parquet-chunks`) through Terraform. A `terraform.tfstate` file exists locally in this folder (gitignored, not committed) whose presence means `terraform apply` was actually run against a real Azure subscription at some point; that infrastructure is almost certainly not still standing, since cloud storage costs money to keep provisioned and there's no evidence here of ongoing use.
- **Orchestration (`orchestration/docker-compose.yml`):** starts a single Kestra container. There is no Kestra flow definition file (`.yml`) committed anywhere in this repository, so the "fully declarative Kestra DAG" that earlier documentation described can't be verified from what's here. Also: the compose file maps Kestra's internal port 8080 to host port 9000 (`"9000:8080"`), so the correct local URL is `localhost:9000`, not `localhost:8080` as earlier setup instructions said.
- **Visualization (`visualization/`):** a custom Metabase Docker image (Ubuntu base, to get a `glibc` environment the DuckDB JDBC driver needs) with a DuckDB driver JAR. The `sample-database.db.mv.db` file under `visualization/plugins/` is Metabase's own bundled demo database, not output from this pipeline; it's not evidence of a real arXiv run and isn't cited as such here.

## What is NOT verified

- No automated tests here (dbt has no test files in `tests/`, `analyses/`, `macros/` beyond placeholder `.gitkeep`s), and this project isn't in `.github/workflows/tests.yml` (only Proj14-19 are).
- Whether this pipeline was ever run end to end (extraction through the dashboard) isn't something this repo has an artifact for. The `terraform.tfstate` confirms the Azure resources existed at some point; nothing here confirms data actually flowed all the way through dbt to Metabase.
- The earlier claim of processing "10,000 records to validate the architecture" matches the code's chunk size exactly, which is consistent with a real run having happened, but there's no committed log, row count, or exported chunk file in this repo to confirm it independently.
- Whether the MotherDuck account and Azure subscription behind this are still active is unknown; this README does not attempt to connect to either.

## Stack

Python (extraction) · Terraform (Azure resource group, storage account, blob container) · Kestra (orchestration, container only, no committed flow) · dbt-core with dbt-duckdb · MotherDuck (cloud DuckDB) · Metabase (custom Docker image) · Docker Compose

## Running it (as designed; not re-run for this README)

```bash
cd infrastructure && terraform init && terraform apply   # provisions Azure resource group, storage account, container
cd ../orchestration && docker compose up -d               # Kestra at localhost:9000; a flow still needs to be created/imported
cd ../transformation && docker build -t arxiv-dbt . && docker run --env-file ../.env arxiv-dbt
cd ../visualization && docker compose up -d --build        # Metabase dashboard at localhost:3000
```

A `.env` in the repo root needs `AZURE_CONNECTION_STRING` and `MOTHERDUCK_TOKEN`; see `dependencies.md` for the full library/version list and system requirements.

## Known gaps and future work (carried over from the original design notes)

Full backfill beyond the 10,000-record MVP, horizontal scaling of extraction onto AKS/Azure Functions, incremental dbt loads instead of full rebuilds, dbt data-quality tests on `paper_key`, CI/CD for `dbt test` and `terraform plan`, alerting on failed extraction batches, and semantic search over abstracts via a vector database. None of these are built; they're listed here as the original scope notes, not as claims about what exists.
