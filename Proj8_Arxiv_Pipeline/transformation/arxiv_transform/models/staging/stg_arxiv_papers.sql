{{ config(materialized='view') }}

-- One row per paper. Chunks can overlap (a resumed or re-run extraction, or a
-- paper revised between runs), so keep the highest version of each paper.

WITH source AS (
    SELECT * FROM read_parquet('{{ raw_path() }}')
),

parsed AS (
    SELECT
        regexp_extract(id, 'arxiv\.org/abs/(.+?)(v[0-9]+)?$', 1)               AS paper_id,
        TRY_CAST(regexp_extract(id, 'v([0-9]+)$', 1) AS INTEGER)               AS version,
        title,
        array_to_string(authors, ', ')                                          AS authors,
        len(authors)                                                            AS author_count,
        CAST(published_date AS TIMESTAMP)                                       AS published_timestamp,
        CAST(updated_date AS TIMESTAMP)                                         AS updated_timestamp,
        primary_category,
        categories,
        abstract,
        pdf_url
    FROM source
)

SELECT *
FROM parsed
QUALIFY row_number() OVER (
    PARTITION BY paper_id
    ORDER BY version DESC NULLS LAST, updated_timestamp DESC
) = 1
