{# Where the raw Parquet chunks live. Override with --vars '{raw_path: ...}'. #}
{% macro raw_path() %}
    {%- if target.name == 'local' -%}
        {{ var('raw_path', '../../data/raw/*.parquet') }}
    {%- else -%}
        {{ var('raw_path', 'azure://raw-parquet-chunks/raw/*.parquet') }}
    {%- endif -%}
{% endmacro %}
