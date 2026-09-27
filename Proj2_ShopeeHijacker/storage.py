"""SQLite history of capture runs (every run appended, never replaced) and a CSV export."""
import csv
import sqlite3
from pathlib import Path

COLUMNS = ["itemid", "shopid", "title", "price_php", "lifetime_sold", "monthly_sold", "url"]

SCHEMA = """
create table if not exists capture_runs (
    id              integer primary key,
    keyword         text not null,
    pages_requested integer not null,
    pages_ok        integer not null,
    items           integer not null,
    parse_failures  integer not null,
    started_at      text not null,
    finished_at     text not null
);
create table if not exists products (
    run_id        integer not null references capture_runs(id),
    itemid        integer not null,
    shopid        integer not null,
    title         text not null,
    price_php     real not null,
    lifetime_sold integer not null,
    monthly_sold  integer not null,
    url           text not null,
    primary key (run_id, shopid, itemid)
);
"""


def save_run(db_path, run: dict, rows: list[dict]) -> int:
    """Writes the run and its products in one transaction and returns the run id."""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        with conn:  # commits on success, rolls back the whole run on any error
            cur = conn.execute(
                "insert into capture_runs (keyword, pages_requested, pages_ok, items, parse_failures, started_at, finished_at) "
                "values (?, ?, ?, ?, ?, ?, ?)",
                (run["keyword"], run["pages_requested"], run["pages_ok"], len(rows), run["parse_failures"],
                 run["started_at"], run["finished_at"]))
            run_id = cur.lastrowid
            conn.executemany(
                f"insert into products (run_id, {', '.join(COLUMNS)}) values (?, {', '.join('?' * len(COLUMNS))})",
                [(run_id, *(r[c] for c in COLUMNS)) for r in rows])
        return run_id
    finally:
        conn.close()


def write_csv(path, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
