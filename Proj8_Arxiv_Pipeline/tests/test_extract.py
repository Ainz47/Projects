import json

import pyarrow.parquet as pq
import pytest
import requests

import extract
from extract import ExtractionError, LocalDestination, chunk_name, fetch_page, parse_feed, run

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:opensearch="http://a9.com/-/spec/opensearch/1.1/"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <opensearch:totalResults>{total}</opensearch:totalResults>
  {entries}
</feed>"""

ENTRY = """<entry>
  <id>http://arxiv.org/abs/0704.{n:04d}v2</id>
  <updated>2007-05-01T00:00:00Z</updated>
  <published>2007-04-02T00:00:00Z</published>
  <title>Paper   number
    {n}</title>
  <summary>  An abstract
  wrapped over lines.  </summary>
  <author><name>Ada Lovelace</name></author>
  <author><name>Emmy Noether</name></author>
  <link href="http://arxiv.org/abs/0704.{n:04d}v2" rel="alternate" type="text/html"/>
  <link title="pdf" href="http://arxiv.org/pdf/0704.{n:04d}v2" rel="related" type="application/pdf"/>
  <arxiv:primary_category term="math.CO" scheme="http://arxiv.org/schemas/atom"/>
  <category term="math.CO" scheme="http://arxiv.org/schemas/atom"/>
  <category term="cs.DM" scheme="http://arxiv.org/schemas/atom"/>
</entry>"""


def feed(total, numbers):
    return FEED.format(total=total, entries="".join(ENTRY.format(n=n) for n in numbers)).encode()


class Resp:
    def __init__(self, status=200, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}


class FakeArxiv:
    """Serves `total` papers page by page. `script` maps a call number to a
    forced response (or exception) so failures can be injected."""

    def __init__(self, total, script=None):
        self.total, self.script, self.calls = total, script or {}, []

    def get(self, url, params, timeout):
        assert url.startswith("https://") and timeout
        self.calls.append(dict(params))
        forced = self.script.get(len(self.calls))
        if isinstance(forced, Exception):
            raise forced
        if forced is not None:
            return forced
        start, size = params["start"], params["max_results"]
        return Resp(content=feed(self.total, range(start, min(start + size, self.total))))


def no_sleep(_):
    pass


def ids_in(folder):
    out = []
    for path in sorted(folder.glob("arxiv_math_*.parquet")):
        out += pq.read_table(path).column("id").to_pylist()
    return out


# --- parsing -----------------------------------------------------------------

def test_parse_feed_extracts_and_cleans_every_field():
    total, [rec] = parse_feed(feed(42, [7]))
    assert total == 42
    assert rec == {
        "id": "http://arxiv.org/abs/0704.0007v2",
        "title": "Paper number 7",
        "authors": ["Ada Lovelace", "Emmy Noether"],
        "published_date": "2007-04-02T00:00:00Z",
        "updated_date": "2007-05-01T00:00:00Z",
        "primary_category": "math.CO",
        "categories": ["math.CO", "cs.DM"],
        "abstract": "An abstract wrapped over lines.",
        "pdf_url": "http://arxiv.org/pdf/0704.0007v2",
    }


def test_parse_feed_tolerates_missing_optional_parts():
    xml = FEED.format(total=1, entries="<entry><id>x</id></entry>").encode()
    _, [rec] = parse_feed(xml)
    assert rec["id"] == "x"
    assert rec["title"] is None and rec["pdf_url"] is None and rec["primary_category"] is None
    assert rec["authors"] == [] and rec["categories"] == []


def test_chunk_name_sorts_by_offset():
    assert chunk_name(2000) == "arxiv_math_00002000.parquet"
    assert sorted([chunk_name(10000), chunk_name(2000)])[0] == chunk_name(2000)


# --- HTTP retries ------------------------------------------------------------

@pytest.mark.parametrize("failure", [
    Resp(503), Resp(429), requests.ConnectionError("reset"), requests.Timeout("slow"),
])
def test_fetch_page_retries_transient_failures(failure):
    api, waits = FakeArxiv(5, script={1: failure}), []
    total, records = fetch_page(api, 0, 5, sleep=waits.append)
    assert total == 5 and len(records) == 5
    assert len(api.calls) == 2 and len(waits) == 1


def test_fetch_page_honours_retry_after():
    api, waits = FakeArxiv(5, script={1: Resp(429, headers={"Retry-After": "17"})}), []
    fetch_page(api, 0, 5, sleep=waits.append)
    assert waits == [17.0]


def test_fetch_page_backs_off_exponentially_then_gives_up():
    api, waits = FakeArxiv(5, script={i: Resp(500) for i in range(1, 10)}), []
    with pytest.raises(ExtractionError, match="gave up"):
        fetch_page(api, 0, 5, sleep=waits.append)
    assert len(api.calls) == extract.MAX_ATTEMPTS
    assert waits == [extract.POLITE_DELAY * 2 ** i for i in range(extract.MAX_ATTEMPTS - 1)]


def test_fetch_page_does_not_retry_a_client_error():
    api = FakeArxiv(5, script={1: Resp(400)})
    with pytest.raises(ExtractionError, match="HTTP 400"):
        fetch_page(api, 0, 5, sleep=no_sleep)
    assert len(api.calls) == 1


def test_empty_page_mid_result_set_is_retried_not_taken_as_the_end():
    api = FakeArxiv(10, script={1: Resp(content=feed(10, []))})
    _, records = fetch_page(api, 0, 5, sleep=no_sleep)
    assert len(records) == 5 and len(api.calls) == 2


def test_empty_page_past_the_end_is_the_end():
    api = FakeArxiv(10)
    _, records = fetch_page(api, 10, 5, sleep=no_sleep)
    assert records == [] and len(api.calls) == 1


# --- runs and resume ---------------------------------------------------------

def test_run_writes_offset_named_chunks_and_a_checkpoint(tmp_path):
    state = run(LocalDestination(tmp_path), FakeArxiv(23), page_size=5, chunk_size=10, sleep=no_sleep)
    assert sorted(p.name for p in tmp_path.glob("*.parquet")) == [
        chunk_name(0), chunk_name(10), chunk_name(20)]
    assert len(ids_in(tmp_path)) == 23
    assert state["next_start"] == 23 and state["chunks_written"] == 3
    assert json.loads((tmp_path / "_state.json").read_text())["next_start"] == 23


def test_max_records_caps_the_total_offset_and_the_next_run_resumes(tmp_path):
    dest, api = LocalDestination(tmp_path), FakeArxiv(50)
    run(dest, api, page_size=5, chunk_size=10, max_records=12, sleep=no_sleep)
    assert api.calls[-1]["max_results"] == 2  # last page trimmed to the cap
    run(dest, api, page_size=5, chunk_size=10, max_records=30, sleep=no_sleep)
    got = ids_in(tmp_path)
    assert len(got) == len(set(got)) == 30
    assert api.calls[len(api.calls) - 4]["start"] == 12  # second run started where the first stopped


def test_a_crash_resumes_from_the_last_written_chunk(tmp_path):
    dest = LocalDestination(tmp_path)
    # Pages of 5, chunks of 10: calls 1-2 fill chunk 0, call 3 is buffered, call 4 fails for good.
    dying = FakeArxiv(40, script={i: Resp(500) for i in range(4, 20)})
    with pytest.raises(ExtractionError):
        run(dest, dying, page_size=5, chunk_size=10, sleep=no_sleep)
    assert json.loads((tmp_path / "_state.json").read_text())["next_start"] == 10

    api = FakeArxiv(40)
    state = run(dest, api, page_size=5, chunk_size=10, sleep=no_sleep)
    assert api.calls[0]["start"] == 10  # the buffered-but-unwritten page is fetched again
    got = ids_in(tmp_path)
    assert len(got) == len(set(got)) == 40 and state["next_start"] == 40


def test_reset_overwrites_the_same_files_instead_of_duplicating(tmp_path):
    dest = LocalDestination(tmp_path)
    run(dest, FakeArxiv(20), page_size=5, chunk_size=10, sleep=no_sleep)
    run(dest, FakeArxiv(20), page_size=5, chunk_size=10, reset=True, sleep=no_sleep)
    assert len(list(tmp_path.glob("*.parquet"))) == 2
    assert len(ids_in(tmp_path)) == 20


def test_a_checkpoint_for_another_query_is_refused(tmp_path):
    dest = LocalDestination(tmp_path)
    run(dest, FakeArxiv(5), page_size=5, chunk_size=10, sleep=no_sleep)
    with pytest.raises(ExtractionError, match="checkpoint for query"):
        run(dest, FakeArxiv(5), query="cat:physics.*", sleep=no_sleep)


def test_azure_destination_needs_a_connection_string(monkeypatch):
    monkeypatch.delenv("AZURE_CONNECTION_STRING", raising=False)
    with pytest.raises(ExtractionError, match="AZURE_CONNECTION_STRING"):
        extract.open_destination("azure://raw-parquet-chunks/raw")


def test_no_temp_files_are_left_behind(tmp_path):
    run(LocalDestination(tmp_path), FakeArxiv(7), page_size=5, chunk_size=10, sleep=no_sleep)
    assert not list(tmp_path.glob(".*.tmp"))
