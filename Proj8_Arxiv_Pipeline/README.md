# arXiv Pipeline (API -> Parquet -> dbt on DuckDB)

A batch data pipeline, first built as a Data Engineering Zoomcamp capstone. It pulls math papers from the arXiv API into Parquet chunks, transforms them with dbt on DuckDB (a local file, or MotherDuck in the cloud), and serves the result to Metabase. In the cloud setup the chunks land in Azure Blob Storage, provisioned with Terraform, and Kestra runs the whole thing daily.

Architecture diagram: [docs/architecture-diagram.md](./docs/architecture-diagram.md) | [docs/architecture-diagram.svg](./docs/architecture-diagram.svg) | [docs/architecture-diagram.png](./docs/architecture-diagram.png)

## What it does

**Extraction** ([extraction/extract.py](./extraction/extract.py)) pages through the `cat:math.*` query oldest first and writes Parquet chunks, either to a local folder or to an Azure blob prefix.

- **Resumable.** A checkpoint (`_state.json`) sits next to the chunks and is rewritten after every chunk. A run that dies part way picks up at the last written chunk. Because it lives with the data rather than on the machine, a fresh container pointed at Azure resumes too, and a daily run picks up where yesterday's stopped.
- **Re-runs don't duplicate.** Each chunk is named by the offset of its first record (`arxiv_math_00001000.parquet`), so fetching a range again overwrites the same file. Local writes go to a temp file first and are renamed, so a crash never leaves half a chunk behind.
- **Polite and patient with the API.** 3 seconds between requests (arXiv's rule), a timeout on every call, and retries with exponential backoff on network errors, 429 and 5xx, honouring `Retry-After`. arXiv sometimes answers with an empty page in the middle of a result set; that's retried too, and only an empty page past `totalResults` counts as the end.
- **Refuses to mix datasets.** A checkpoint written for a different query stops the run instead of appending to it.

**Transformation** ([transformation/arxiv_transform/](./transformation/arxiv_transform/)) is two dbt models:

- `stg_arxiv_papers` (view) splits the arXiv id into `paper_id` and `version` (old-style ids like `math/9201239` included) and keeps one row per paper, the highest version, since overlapping chunks and revised papers both produce repeats.
- `fact_math_papers` (incremental) is keyed on `paper_key = md5(paper_id)`, so the key survives a new version or a corrected title. Each run only inserts papers that are new or newer than the loaded copy, compared paper by paper, so chunks arriving out of order (a backfill) aren't skipped. `is_cross_list` flags papers the math query matched through a secondary category.
- **Tests:** unique and not-null on `paper_key` and `paper_id`, not-null category and publish date, and a check that nothing is published or updated in the future or updated before it was published.

**Orchestration** ([orchestration/flows/arxiv_pipeline.yml](./orchestration/flows/arxiv_pipeline.yml)) is a Kestra flow: extract (retried up to 3 times), then `dbt build` on MotherDuck, daily at 06:00, with secrets from Kestra's secret store.

## Local run

Run on 2026-09-27 against the real arXiv API, into a local folder and a local DuckDB file, in two parts to show the resume and the incremental load.

Part 1, capped at 1,000 records ([runs/extract_run1.log](./runs/extract_run1.log)), then `dbt build` ([runs/dbt_build_run1.log](./runs/dbt_build_run1.log)):

```
INFO resuming at offset 0 into data\raw
INFO wrote arxiv_math_00000000.parquet (500 records), checkpoint at 500
INFO wrote arxiv_math_00000500.parquet (500 records), checkpoint at 1000
```

Part 2, the same command with the cap raised to 2,000 ([runs/extract_run2.log](./runs/extract_run2.log)), then `dbt build` again ([runs/dbt_build_run2.log](./runs/dbt_build_run2.log)):

```
INFO resuming at offset 1000 into data\raw
INFO wrote arxiv_math_00001000.parquet (500 records), checkpoint at 1500
INFO wrote arxiv_math_00001500.parquet (500 records), checkpoint at 2000
```

Both builds passed all 11 models and tests. The fact table afterwards ([runs/fact_summary.txt](./runs/fact_summary.txt)) holds 2,000 papers from 1989 to 1995 in two load batches of 1,000, so the second build inserted only the new papers rather than rebuilding. 630 of them have a non-math primary category (mostly `hep-th`), which is what `is_cross_list` is for.

The dedupe isn't exercised by that run, since its chunks don't overlap. The CI fixture ([tests/make_fixture.py](./tests/make_fixture.py)) is built so it is: two chunks share one paper, as v1 and then v2, and the fact table ends up with 5 papers and the v2 copy.

**Not re-run this time:** the Azure destination, the MotherDuck target, the Kestra flow and the Metabase image. They need Docker and cloud accounts, and Docker isn't running on the machine this was verified on. The Azure path runs the same code as the local one apart from the upload call, and its missing-credentials case is tested. The `terraform.tfstate` kept locally (gitignored) shows the Azure resources were provisioned for the original capstone run.

## Running it

**Locally** (Python 3.12, the version the run above used):

```bash
pip install -r extraction/requirements.txt dbt-core dbt-duckdb
python extraction/extract.py --max-records 2000          # writes data/raw/, resumes if run again
cd transformation/arxiv_transform
dbt build --profiles-dir .                               # local target: arxiv_local.duckdb, reads ../../data/raw
```

`extract.py` options: `--dest` (folder or `azure://<container>/<prefix>`), `--max-records` (caps the total offset, so 1000 then 2000 fetches 1,000 more), `--page-size`, `--chunk-size`, `--query`, `--reset`. dbt reads somewhere else with `--vars '{raw_path: "path/*.parquet"}'`.

**In the cloud:**

```bash
cd infrastructure && terraform init && terraform apply     # resource group, storage account, raw-parquet-chunks container
docker build -t arxiv-extract extraction
docker build -t arxiv-dbt transformation/arxiv_transform
cd orchestration && docker compose up -d                   # Kestra at localhost:9000
```

Then add `AZURE_CONNECTION_STRING` and `MOTHERDUCK_TOKEN` to Kestra's secrets, and paste `orchestration/flows/arxiv_pipeline.yml` into a new flow in the Kestra UI. Metabase: `cd visualization && docker compose up -d --build` (localhost:3000).

**Tests** (no network; they run in CI along with `dbt build` on the fixture, twice, to go through both the full and the incremental path):

```bash
python -m pytest tests -q
```

They cover parsing, every retry case, the empty-page rule, chunk naming, the offset cap, resuming after a crash, re-runs overwriting instead of duplicating, and the query check.

## Project structure

```text
extraction/extract.py          arXiv API -> Parquet chunks, with the checkpoint, retries and destinations
transformation/arxiv_transform dbt project: staging dedupe, incremental fact, tests, local + MotherDuck profiles
orchestration/flows/           The Kestra flow (extract, then dbt build, daily)
orchestration/docker-compose   Kestra server
infrastructure/                Terraform for the Azure storage
visualization/                 Metabase image with the DuckDB driver
tests/                         Extractor tests and the CI fixture generator
runs/                          Logs and the fact table summary from the local run
```

Stack: Python, pyarrow, dbt-core, dbt-duckdb, DuckDB / MotherDuck, Azure Blob Storage, Terraform, Kestra, Metabase, Docker. Versions in [dependencies.md](./dependencies.md).
