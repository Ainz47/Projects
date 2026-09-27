# Dependencies

## Verified locally (2026-09-27)

The local run in the README used Python 3.12 with:

| Package | Version | Used by |
| :--- | :--- | :--- |
| `requests` | 2.34.2 | extraction: API calls |
| `pyarrow` | 25.0.1 | extraction: Parquet writing |
| `dbt-core` | 1.12.5 | transformation |
| `dbt-duckdb` | 1.11.0 | transformation |
| `duckdb` | 1.5.5 | transformation (local DuckDB file) |
| `pytest` | 9.1.1 | tests |

`azure-storage-blob` (12.20+) is only needed when `--dest` is an `azure://` prefix. It's in `extraction/requirements.txt` for the Docker image.

The dbt image (`transformation/arxiv_transform/Dockerfile`) pins the same dbt and DuckDB versions. MotherDuck only accepts certain DuckDB client versions, and the MotherDuck target hasn't been re-run with these, so check its supported versions before a cloud run.

## Cloud and containers (not re-run for this version)

- **Azure Blob Storage:** a storage account with a `raw-parquet-chunks` container (`infrastructure/`, Terraform 1.5+ with the azurerm provider pinned in `.terraform.lock.hcl`).
- **MotherDuck:** an account and a `MOTHERDUCK_TOKEN`.
- **Docker Engine 24+ and Compose v2:** for Kestra (`orchestration/`) and Metabase (`visualization/`).
- **Metabase:** a custom image on `eclipse-temurin:21-jre-jammy`, since the community DuckDB JDBC driver needs glibc. Allow about 8 GB of RAM for Kestra, a task container and Metabase together.

## arXiv API

Public, no key. The extractor waits 3 seconds between requests, as arXiv's terms ask.
