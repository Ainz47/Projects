# Proj8 Architecture Diagram

This diagram reflects the current implementation in `Proj8_Arxiv_Pipeline`.

```mermaid
flowchart LR
    user[Engineer / Operator]
    browser[Browser]
    env[.env Secrets<br/>Azure connection string<br/>MotherDuck token]

    subgraph infra[Infrastructure Provisioning]
        tf[Terraform]
        rg[Azure Resource Group]
        sa[Azure Storage Account]
        blob[Blob Container<br/>raw-parquet-chunks]
        tf --> rg --> sa --> blob
    end

    subgraph orchestration[Batch Orchestration]
        kestra[Kestra<br/>Docker Compose]
        extract[Python Extractor<br/>extract.py]
        localpq[Chunked Parquet Files<br/>10,000 records per file]
        kestra --> extract --> localpq
    end

    subgraph source[Source System]
        arxiv[arXiv API]
    end

    subgraph transform[Transformation Layer]
        dbt[dbt-duckdb Container]
        stg[stg_arxiv_papers<br/>clean + cast + normalize]
        fact[fact_math_papers<br/>hashed key + ordered table]
        dbt --> stg --> fact
    end

    subgraph warehouse[Analytics Warehouse]
        md[MotherDuck / DuckDB]
    end

    subgraph bi[Serving Layer]
        metabase[Metabase<br/>Docker Compose]
        dash[Math Research Dashboard]
        metabase --> dash
    end

    user --> tf
    user --> kestra
    user --> dbt
    user --> metabase
    browser --> dash

    env -. credentials .-> extract
    env -. credentials .-> dbt
    env -. credentials .-> metabase

    arxiv --> extract
    localpq --> blob
    blob --> dbt
    fact --> md
    md --> metabase
```

## Data Flow

1. Terraform provisions the Azure resource group, storage account, and the `raw-parquet-chunks` container.
2. Kestra runs the Python extraction job against the arXiv API.
3. The extractor paginates results, writes parquet chunks locally, and uploads them into Azure Blob Storage under `raw/`.
4. dbt reads the raw parquet files directly from Azure, creates the staging model, and materializes the curated fact table in MotherDuck.
5. Metabase connects to MotherDuck and serves the dashboard to the browser.

## Main Components

- `infrastructure/`: Terraform for Azure storage resources.
- `orchestration/`: Kestra runtime launched with Docker Compose.
- `extraction/`: Python batch extractor with Azure Blob upload support.
- `transformation/`: dbt project using DuckDB + MotherDuck.
- `visualization/`: Metabase service for dashboarding.
