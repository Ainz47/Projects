"""Write a small raw dataset for `dbt build` in CI.

Two chunks that overlap the way a resumed extraction does: paper 0704.0003
is in both, as v1 and then as a revised v2, so the staging dedupe and the
unique tests on paper_id have something to catch.

    py tests/make_fixture.py <folder>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "extraction"))
from extract import LocalDestination, chunk_name, to_parquet  # noqa: E402


def paper(n, version=1, updated="2007-04-10T00:00:00Z", primary="math.CO"):
    return {
        "id": f"http://arxiv.org/abs/0704.{n:04d}v{version}",
        "title": f"Fixture paper {n} (v{version})",
        "authors": ["Ada Lovelace", "Emmy Noether"],
        "published_date": "2007-04-02T00:00:00Z",
        "updated_date": updated,
        "primary_category": primary,
        "categories": [primary],
        "abstract": "A fixture abstract.",
        "pdf_url": f"http://arxiv.org/pdf/0704.{n:04d}v{version}",
    }


CHUNKS = {
    0: [paper(1), paper(2), paper(3)],
    3: [paper(3, version=2, updated="2007-06-01T00:00:00Z"), paper(4), paper(5, primary="cs.DM")],
}

if __name__ == "__main__":
    dest = LocalDestination(sys.argv[1] if len(sys.argv) > 1 else "data/raw")
    for start, records in CHUNKS.items():
        dest.write(chunk_name(start), to_parquet(records))
    print(f"wrote {len(CHUNKS)} chunks ({sum(map(len, CHUNKS.values()))} rows, 5 papers) to {dest}")
