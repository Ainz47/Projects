{{ config(
    materialized='incremental',
    unique_key='paper_id',
    incremental_strategy='delete+insert'
) }}

WITH staging_data AS (
    SELECT * FROM {{ ref('stg_arxiv_papers') }}
)

SELECT
    -- Hash of the arXiv id alone, so the key survives a title fix or a new version.
    md5(paper_id)                                 AS paper_key,
    paper_id,
    version,
    title,
    authors,
    author_count,
    published_timestamp,
    updated_timestamp,
    primary_category,
    primary_category NOT LIKE 'math%'             AS is_cross_list,
    categories,
    abstract,
    pdf_url,
    CURRENT_TIMESTAMP                             AS dbt_updated_at
FROM staging_data s

{% if is_incremental() %}
-- Only papers that are new, or newer than the copy already loaded. Comparing per
-- paper (not against max(updated)) stays correct if chunks land out of order.
WHERE NOT EXISTS (
    SELECT 1 FROM {{ this }} t
    WHERE t.paper_id = s.paper_id
      AND t.updated_timestamp >= s.updated_timestamp
)
{% endif %}
