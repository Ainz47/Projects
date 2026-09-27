-- A paper can't be published or updated in the future, or updated before it was published.
SELECT paper_id, published_timestamp, updated_timestamp
FROM {{ ref('fact_math_papers') }}
WHERE published_timestamp > CURRENT_TIMESTAMP
   OR updated_timestamp > CURRENT_TIMESTAMP
   OR updated_timestamp < published_timestamp
