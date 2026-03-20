{{ config(
    materialized='table',
    order_by=['published_timestamp', 'primary_category']
) }}

WITH staging_data AS (
    SELECT * FROM {{ ref('stg_arxiv_papers') }}
)

SELECT
    -- Create the unique fingerprint (Surrogate Key)
    MD5(COALESCE(paper_id, '') || COALESCE(title, '') || COALESCE(authors, '')) AS paper_key,
    paper_id,
    title,
    authors,
    published_timestamp,
    primary_category,
    abstract,
    pdf_url,
    -- Add a load timestamp so we know when this record entered our warehouse
    CURRENT_TIMESTAMP AS dbt_updated_at
FROM staging_data