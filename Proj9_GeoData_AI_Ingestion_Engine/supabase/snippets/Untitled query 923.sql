CREATE TABLE IF NOT EXISTS daily_metrics (
    id SERIAL PRIMARY KEY,
    store_id TEXT NOT NULL,
    date DATE NOT NULL,
    gross_sales NUMERIC,
    labor_hours NUMERIC,
    labor_cost NUMERIC,
    cplh NUMERIC,
    labor_pct NUMERIC
);