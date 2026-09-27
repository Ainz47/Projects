import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import shopee_capture  # noqa: E402
from shopee import SearchCollector  # noqa: E402

ITEM = {"item_basic": {"itemid": 11, "shopid": 1, "name": "Zeus G-61", "price": 59800000, "historical_sold": 1, "sold": 1}}
OTHER = {"item_basic": {"itemid": 12, "shopid": 2, "name": "AULA", "price": 91900000, "historical_sold": 1, "sold": 1}}


class Resp:
    def __init__(self, body):
        self.url, self.body = "https://shopee.ph/api/v4/search/search_items?x", body

    def json(self):
        return self.body


def fake_capture(pages_bodies, pages_ok):
    def capture(keyword, pages, cdp_url):
        c = SearchCollector()
        for body in pages_bodies:
            c(Resp(body))
        return c, pages_ok
    return capture


def test_run_dedupes_across_pages_and_saves(tmp_path):
    capture = fake_capture([{"items": [ITEM, OTHER]}, {"items": [ITEM]}], pages_ok=2)
    s = shopee_capture.run("mechanical keyboard", 2, tmp_path / "m.db", tmp_path / "out.csv", capture=capture)
    assert (s["items"], s["duplicates_dropped"], s["pages_ok"]) == (2, 1, 2)
    with sqlite3.connect(tmp_path / "m.db") as conn:
        assert conn.execute("select count(*) from products where run_id = ?", (s["run_id"],)).fetchone() == (2,)
    assert len((tmp_path / "out.csv").read_text(encoding="utf-8").splitlines()) == 3


def test_nothing_captured_saves_nothing(tmp_path):
    s = shopee_capture.run("x", 1, tmp_path / "m.db", tmp_path / "out.csv", capture=fake_capture([], pages_ok=0))
    assert s["items"] == 0 and "run_id" not in s
    assert not (tmp_path / "m.db").exists() and not (tmp_path / "out.csv").exists()


def test_cli_exit_codes(tmp_path):
    args = ["kb", "--pages", "1", "--db", str(tmp_path / "m.db"), "--csv", str(tmp_path / "o.csv")]
    assert shopee_capture.main(args, capture=fake_capture([{"items": [ITEM]}], 1)) == 0
    assert shopee_capture.main(args, capture=fake_capture([], 0)) == 1


def test_pages_must_be_positive():
    with pytest.raises(SystemExit):
        shopee_capture.main(["kb", "--pages", "0"])
