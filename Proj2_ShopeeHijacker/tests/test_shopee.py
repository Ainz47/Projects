import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from shopee import SearchCollector, dedupe, parse_search_response, search_url  # noqa: E402

NESTED = {"items": [
    {"item_basic": {"itemid": 11, "shopid": 1, "name": "Zeus G-61", "price": 59800000, "historical_sold": 10000, "sold": 7000}},
    {"item_basic": {"itemid": 12, "shopid": 2, "name": "AULA F3261", "price": 91900000, "historical_sold": 20000, "sold": 171}},
]}
FLAT = {"items": [{"itemid": 13, "shopid": 3, "name": "Flat item", "price": 100000, "historical_sold": 1, "sold": 0}]}


def test_parses_nested_items_with_php_price_and_url():
    rows, bad = parse_search_response(NESTED)
    assert bad == 0
    assert rows[0] == {"itemid": 11, "shopid": 1, "title": "Zeus G-61", "price_php": 598.0,
                       "lifetime_sold": 10000, "monthly_sold": 7000, "url": "https://shopee.ph/product/1/11"}


def test_parses_flat_items_too():
    rows, _ = parse_search_response(FLAT)
    assert rows[0]["itemid"] == 13 and rows[0]["price_php"] == 1.0


def test_items_without_ids_are_counted_not_kept():
    rows, bad = parse_search_response({"items": [{"item_basic": {"name": "no ids"}}, NESTED["items"][0]]})
    assert [r["itemid"] for r in rows] == [11]
    assert bad == 1


def test_null_items_is_an_empty_page():
    assert parse_search_response({"items": None}) == ([], 0)


def test_dedupe_is_on_shop_and_item_not_title():
    same_title_other_item = {**NESTED["items"][0]["item_basic"], "itemid": 99}
    rows, _ = parse_search_response({"items": NESTED["items"] + [NESTED["items"][0], {"item_basic": same_title_other_item}]})
    kept = dedupe(rows)
    assert [(r["shopid"], r["itemid"]) for r in kept] == [(1, 11), (2, 12), (1, 99)]


def test_search_url_encodes_the_keyword():
    assert search_url("mechanical keyboard & mouse", 2) == "https://shopee.ph/search?keyword=mechanical%20keyboard%20%26%20mouse&page=2"


class FakeResponse:
    def __init__(self, url, body=None, error=None):
        self.url, self._body, self._error = url, body, error

    def json(self):
        if self._error:
            raise self._error
        return self._body


def test_collector_keeps_search_responses_and_counts_failures():
    c = SearchCollector()
    c(FakeResponse("https://shopee.ph/api/v4/search/search_items?keyword=x", NESTED))
    c(FakeResponse("https://shopee.ph/api/v4/other", {"items": [1, 2, 3]}))  # not a search call: ignored
    c(FakeResponse("https://shopee.ph/api/v4/search/search_items?page=1", error=ValueError("not json")))
    assert len(c.rows) == 2
    assert c.responses == 2 and c.failures == 1
