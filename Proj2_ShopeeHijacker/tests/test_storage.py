import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from storage import save_run, write_csv  # noqa: E402

ROW = {"itemid": 11, "shopid": 1, "title": "Zeus G-61", "price_php": 598.0, "lifetime_sold": 10000,
       "monthly_sold": 7000, "url": "https://shopee.ph/product/1/11"}
RUN = {"keyword": "mechanical keyboard", "pages_requested": 3, "pages_ok": 3, "parse_failures": 0,
       "started_at": "2026-09-27T10:00:00+00:00", "finished_at": "2026-09-27T10:01:00+00:00"}


def test_each_run_is_appended_so_prices_have_history(tmp_path):
    db = tmp_path / "m.db"
    first = save_run(db, RUN, [ROW])
    second = save_run(db, {**RUN, "started_at": "2026-09-28T10:00:00+00:00"}, [{**ROW, "price_php": 549.0}])
    assert second == first + 1
    with sqlite3.connect(db) as conn:
        prices = conn.execute("select r.started_at, p.price_php from products p join capture_runs r on r.id = p.run_id "
                              "where p.itemid = 11 order by r.started_at").fetchall()
    assert prices == [("2026-09-27T10:00:00+00:00", 598.0), ("2026-09-28T10:00:00+00:00", 549.0)]


def test_run_row_records_what_happened(tmp_path):
    db = tmp_path / "m.db"
    run_id = save_run(db, {**RUN, "pages_ok": 2, "parse_failures": 1}, [ROW])
    with sqlite3.connect(db) as conn:
        assert conn.execute("select keyword, pages_requested, pages_ok, items, parse_failures from capture_runs "
                            "where id = ?", (run_id,)).fetchone() == ("mechanical keyboard", 3, 2, 1, 1)


def test_the_same_item_twice_in_one_run_is_rejected(tmp_path):
    import pytest
    with pytest.raises(sqlite3.IntegrityError):
        save_run(tmp_path / "m.db", RUN, [ROW, ROW])


def test_a_failed_save_leaves_no_half_run(tmp_path):
    db = tmp_path / "m.db"
    try:
        save_run(db, RUN, [ROW, ROW])
    except sqlite3.IntegrityError:
        pass
    with sqlite3.connect(db) as conn:
        assert conn.execute("select count(*) from capture_runs").fetchone() == (0,)


def test_csv_has_a_header_and_every_row(tmp_path):
    out = tmp_path / "out.csv"
    write_csv(out, [ROW, {**ROW, "itemid": 12, "title": 'Quote "and", comma'}])
    lines = out.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "itemid,shopid,title,price_php,lifetime_sold,monthly_sold,url"
    assert len(lines) == 3 and '"Quote ""and"", comma"' in lines[2]
