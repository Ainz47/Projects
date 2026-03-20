FROM python:3.11-slim

WORKDIR /app

# Pin BOTH dbt-duckdb and the underlying duckdb engine
RUN pip install --no-cache-dir dbt-duckdb==1.7.1 duckdb==1.4.4

COPY . .

CMD ["dbt", "run", "--profiles-dir", "."]