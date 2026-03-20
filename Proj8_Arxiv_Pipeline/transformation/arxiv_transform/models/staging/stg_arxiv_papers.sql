{{ config(materialized='view') }}

WITH source AS (
    SELECT * FROM 'azure://raw-parquet-chunks/raw/*.parquet'
)

SELECT
    REPLACE(id, 'http://arxiv.org/abs/', '') AS paper_id,
    title,
    authors,
    CAST(published_date AS TIMESTAMP) AS published_timestamp,
    primary_category,
    abstract,
    pdf_url
FROM source
