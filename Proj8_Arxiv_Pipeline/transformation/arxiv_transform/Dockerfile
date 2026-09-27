FROM python:3.12-slim

WORKDIR /app

# The versions the local end-to-end run was verified with.
RUN pip install --no-cache-dir dbt-core==1.12.5 dbt-duckdb==1.11.0 duckdb==1.5.5

COPY . .

CMD ["dbt", "build", "--profiles-dir", ".", "--target", "motherduck"]
