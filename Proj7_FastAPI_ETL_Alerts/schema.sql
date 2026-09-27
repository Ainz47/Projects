-- One row per store per day. Run once in the Supabase SQL editor.
create table if not exists public.daily_metrics (
    id            bigint generated always as identity primary key,
    store_id      text not null,
    date          date not null,
    gross_sales   numeric(12, 2) check (gross_sales >= 0),
    labor_cost    numeric(12, 2) check (labor_cost >= 0),
    labor_hours   numeric(8, 2)  check (labor_hours >= 0),
    cplh          numeric(10, 2),
    labor_pct     numeric(7, 2),
    alert_sent_at timestamptz,
    created_at    timestamptz not null default now(),
    -- The upsert target: sales and labor webhooks for the same store-day land on one row.
    unique (store_id, date)
);

-- Only the service-role key (server side) can read or write; the public anon key gets nothing.
alter table public.daily_metrics enable row level security;
