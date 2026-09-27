"""Pull arXiv math papers into Parquet chunks, resumably.

Each chunk is named by the offset of its first record, and a checkpoint
(`_state.json`) sits next to the chunks and is rewritten after every chunk.
A run that dies part way resumes from the last written chunk, and a re-run
over the same range overwrites the same files instead of duplicating them.

Destination is a local folder, or an Azure blob prefix written as
`azure://<container>/<prefix>` (needs AZURE_CONNECTION_STRING).
"""
from __future__ import annotations

import argparse
import io
import json
import logging
import os
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import requests

log = logging.getLogger("extract")

API_URL = "https://export.arxiv.org/api/query"
SEARCH_QUERY = "cat:math.*"
PAGE_SIZE = 1000
CHUNK_SIZE = 10000
POLITE_DELAY = 3.0  # arXiv asks for 3 seconds between requests
TIMEOUT = 60
MAX_ATTEMPTS = 5
STATE_NAME = "_state.json"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}

SCHEMA = pa.schema([
    ("id", pa.string()),
    ("title", pa.string()),
    ("authors", pa.list_(pa.string())),
    ("published_date", pa.string()),
    ("updated_date", pa.string()),
    ("primary_category", pa.string()),
    ("categories", pa.list_(pa.string())),
    ("abstract", pa.string()),
    ("pdf_url", pa.string()),
])


class ExtractionError(RuntimeError):
    pass


# --- parsing -----------------------------------------------------------------

def _clean(text: str | None) -> str | None:
    # Titles and abstracts arrive hard-wrapped; collapse all whitespace runs.
    return " ".join(text.split()) if text else None


def parse_feed(xml: bytes) -> tuple[int, list[dict]]:
    """Return (totalResults, records) for one page of the arXiv Atom feed."""
    root = ET.fromstring(xml)
    total_el = root.find("opensearch:totalResults", NS)
    total = int(total_el.text) if total_el is not None and total_el.text else 0

    records = []
    for entry in root.findall("atom:entry", NS):
        primary = entry.find("arxiv:primary_category", NS)
        pdf_url = next(
            (l.get("href") for l in entry.findall("atom:link", NS) if l.get("title") == "pdf"),
            None,
        )
        records.append({
            "id": entry.findtext("atom:id", namespaces=NS),
            "title": _clean(entry.findtext("atom:title", namespaces=NS)),
            "authors": [
                _clean(a.findtext("atom:name", namespaces=NS))
                for a in entry.findall("atom:author", NS)
            ],
            "published_date": entry.findtext("atom:published", namespaces=NS),
            "updated_date": entry.findtext("atom:updated", namespaces=NS),
            "primary_category": primary.get("term") if primary is not None else None,
            "categories": [c.get("term") for c in entry.findall("atom:category", NS)],
            "abstract": _clean(entry.findtext("atom:summary", namespaces=NS)),
            "pdf_url": pdf_url,
        })
    return total, records


def to_parquet(records: list[dict]) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.Table.from_pylist(records, schema=SCHEMA), buf)
    return buf.getvalue()


def chunk_name(start: int) -> str:
    return f"arxiv_math_{start:08d}.parquet"


# --- HTTP --------------------------------------------------------------------

def _retry_wait(attempt: int, response: requests.Response | None) -> float:
    retry_after = response.headers.get("Retry-After") if response is not None else None
    if retry_after and retry_after.isdigit():
        return float(retry_after)
    return POLITE_DELAY * 2 ** attempt


def fetch_page(session, start: int, size: int, query: str = SEARCH_QUERY,
               sleep=time.sleep) -> tuple[int, list[dict]]:
    """One page, retried on network errors, 429 and 5xx.

    arXiv sometimes answers 200 with zero entries in the middle of a result
    set. That is treated as transient too: an empty page is only accepted as
    the end when `start` is at or past totalResults.
    """
    params = {
        "search_query": query,
        "start": start,
        "max_results": size,
        "sortBy": "submittedDate",
        "sortOrder": "ascending",
    }
    last = "no attempt made"
    for attempt in range(MAX_ATTEMPTS):
        response = None
        try:
            response = session.get(API_URL, params=params, timeout=TIMEOUT)
        except requests.RequestException as exc:
            last = f"{type(exc).__name__}: {exc}"
        else:
            if response.status_code == 200:
                total, records = parse_feed(response.content)
                if records or start >= total:
                    return total, records
                last = f"empty page at start={start} of totalResults={total}"
            elif response.status_code == 429 or response.status_code >= 500:
                last = f"HTTP {response.status_code}"
            else:
                raise ExtractionError(f"HTTP {response.status_code} at start={start}")
        if attempt < MAX_ATTEMPTS - 1:
            wait = _retry_wait(attempt, response)
            log.warning("start=%d: %s, retrying in %.0fs", start, last, wait)
            sleep(wait)
    raise ExtractionError(f"gave up at start={start} after {MAX_ATTEMPTS} attempts ({last})")


# --- destinations ------------------------------------------------------------

class LocalDestination:
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)

    def write(self, name: str, data: bytes) -> None:
        # Write then rename, so a crash never leaves a half-written file under the real name.
        tmp = self.folder / f".{name}.tmp"
        tmp.write_bytes(data)
        tmp.replace(self.folder / name)

    def read(self, name: str) -> bytes | None:
        path = self.folder / name
        return path.read_bytes() if path.exists() else None

    def __str__(self) -> str:
        return str(self.folder)


class AzureDestination:
    def __init__(self, uri: str, conn_str: str):
        from azure.storage.blob import BlobServiceClient  # only needed for Azure runs

        container, _, prefix = uri.removeprefix("azure://").partition("/")
        self.uri = uri
        self.prefix = prefix.strip("/")
        self.container = BlobServiceClient.from_connection_string(conn_str).get_container_client(container)

    def _blob(self, name: str):
        return self.container.get_blob_client(f"{self.prefix}/{name}" if self.prefix else name)

    def write(self, name: str, data: bytes) -> None:
        self._blob(name).upload_blob(data, overwrite=True)

    def read(self, name: str) -> bytes | None:
        from azure.core.exceptions import ResourceNotFoundError

        try:
            return self._blob(name).download_blob().readall()
        except ResourceNotFoundError:
            return None

    def __str__(self) -> str:
        return self.uri


def open_destination(dest: str):
    if not dest.startswith("azure://"):
        return LocalDestination(dest)
    conn_str = os.environ.get("AZURE_CONNECTION_STRING")
    if not conn_str:
        raise ExtractionError(f"{dest} needs AZURE_CONNECTION_STRING in the environment")
    return AzureDestination(dest, conn_str)


# --- checkpoint --------------------------------------------------------------

def load_state(dest, query: str) -> dict:
    raw = dest.read(STATE_NAME)
    if raw is None:
        return {"query": query, "next_start": 0, "chunks_written": 0, "records_written": 0}
    state = json.loads(raw)
    if state.get("query") != query:
        raise ExtractionError(
            f"{dest} holds a checkpoint for query {state.get('query')!r}, not {query!r}; "
            "use another destination or --reset"
        )
    return state


def save_state(dest, state: dict) -> None:
    state["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    dest.write(STATE_NAME, json.dumps(state, indent=2).encode())


# --- run ---------------------------------------------------------------------

def run(dest, session, *, query: str = SEARCH_QUERY, page_size: int = PAGE_SIZE,
        chunk_size: int = CHUNK_SIZE, max_records: int | None = None,
        reset: bool = False, sleep=time.sleep) -> dict:
    """Extract from the checkpoint onwards. Returns the final state.

    `max_records` caps the total offset, not this run's count, so
    `--max-records 1000` followed by `--max-records 2000` fetches 1000 more.
    """
    state = ({"query": query, "next_start": 0, "chunks_written": 0, "records_written": 0}
             if reset else load_state(dest, query))
    start = state["next_start"]
    chunk_start, buffer = start, []
    log.info("resuming at offset %d into %s", start, dest)

    def flush():
        nonlocal chunk_start, buffer
        if not buffer:
            return
        name = chunk_name(chunk_start)
        dest.write(name, to_parquet(buffer))
        chunk_start += len(buffer)
        state.update(next_start=chunk_start,
                     chunks_written=state["chunks_written"] + 1,
                     records_written=state["records_written"] + len(buffer))
        save_state(dest, state)
        log.info("wrote %s (%d records), checkpoint at %d", name, len(buffer), chunk_start)
        buffer = []

    first = True
    while max_records is None or start < max_records:
        size = page_size if max_records is None else min(page_size, max_records - start)
        if not first:
            sleep(POLITE_DELAY)
        first = False
        total, records = fetch_page(session, start, size, query, sleep=sleep)
        if not records:
            log.info("reached the end of the result set (totalResults=%d)", total)
            break
        buffer.extend(records)
        start += len(records)
        if len(buffer) >= chunk_size:
            flush()
    flush()
    return state


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dest", default=os.environ.get("ARXIV_DEST", "data/raw"),
                        help="local folder or azure://<container>/<prefix> (default: data/raw)")
    parser.add_argument("--query", default=SEARCH_QUERY)
    parser.add_argument("--page-size", type=int, default=PAGE_SIZE)
    parser.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    parser.add_argument("--max-records", type=int, help="stop at this total offset (for demos)")
    parser.add_argument("--reset", action="store_true", help="ignore the checkpoint and start at 0")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        dest = open_destination(args.dest)
        with requests.Session() as session:
            session.headers["User-Agent"] = "arxiv-pipeline/2.0 (portfolio project)"
            state = run(dest, session, query=args.query, page_size=args.page_size,
                        chunk_size=args.chunk_size, max_records=args.max_records,
                        reset=args.reset)
    except ExtractionError as exc:
        log.error("%s (checkpoint left at the last written chunk)", exc)
        return 1
    log.info("done: %d records in %d chunks, next offset %d",
             state["records_written"], state["chunks_written"], state["next_start"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
