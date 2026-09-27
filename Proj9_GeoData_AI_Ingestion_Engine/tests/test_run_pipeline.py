import json

import pytest

from conftest import make_jpeg
from run_pipeline import Steps, load_businesses, run
from scraper import high_res_url

BIZ = [{"name": "Allegory", "location": "Naperville, IL", "category": "Restaurant"},
       {"name": "Quigley's", "location": "Naperville, IL", "category": "Pub"}]


def fake_steps(**overrides):
    calls = {"fetch": 0, "gallery": 0}

    def scrape(name, location, category):
        return {"name": name, "address": f"1 Main St, {location}", "category": category, "city": location, "image_url": f"https://img/{name}"}

    def fetch(url):
        calls["fetch"] += 1
        return make_jpeg(1600, 900)

    def gallery(name, shot, location):
        calls["gallery"] += 1
        return make_jpeg(1600, 900)

    steps = Steps(scrape=scrape, story=lambda n, c, l: (f"Story of {n}", True), fetch=fetch,
                  gate=lambda b, c, n: b, gallery=gallery)
    for k, v in overrides.items():
        setattr(steps, k, v)
    return steps, calls


def test_each_business_is_created_once_with_a_featured_image(wp, mock_app, tmp_path):
    steps, _ = fake_steps()
    report = tmp_path / "run.jsonl"
    results = run(BIZ, wp, steps, report_path=report)
    assert [r["status"] for r in results] == ["created", "created"]
    posts = mock_app.state.wp["posts"].values()
    assert all(p["featured_media"] for p in posts)
    assert [json.loads(line)["business"] for line in report.read_text().splitlines()] == ["Allegory", "Quigley's"]


def test_second_run_updates_and_reuses_the_photo(wp, mock_app):
    steps, calls = fake_steps()
    run(BIZ, wp, steps)
    results = run(BIZ, wp, steps)
    assert [r["status"] for r in results] == ["updated", "updated"]
    assert all(r["image"] == "reused" for r in results)
    assert calls["fetch"] == 2
    assert len(mock_app.state.wp["posts"]) == 2
    assert len(mock_app.state.wp["media"]) == 2


def test_one_failure_does_not_stop_the_batch(wp):
    def scrape(name, location, category):
        if name == "Allegory":
            raise RuntimeError("selector changed")
        return {"name": name, "address": "1 Main St", "category": category, "city": location, "image_url": "u"}

    steps, _ = fake_steps(scrape=scrape)
    results = run(BIZ, wp, steps)
    assert results[0]["status"] == "error" and "selector changed" in results[0]["error"]
    assert results[1]["status"] == "created"


def test_not_found_is_reported(wp):
    steps, _ = fake_steps(scrape=lambda *a: None)
    assert run(BIZ[:1], wp, steps)[0]["status"] == "not_found"


def test_rejected_photo_still_publishes_without_one(wp, mock_app):
    steps, _ = fake_steps(gate=lambda *a: None)
    result = run(BIZ[:1], wp, steps)[0]
    assert (result["status"], result["image"]) == ("created", "none")


def test_gallery_only_when_asked_and_only_on_create(wp, mock_app):
    steps, calls = fake_steps()
    run(BIZ[:1], wp, steps, gallery=True)
    run(BIZ[:1], wp, steps, gallery=True)
    post = next(iter(mock_app.state.wp["posts"].values()))
    assert len(post["meta"]["gallery_images"]) == 2
    assert calls["gallery"] == 2


def test_load_businesses_rejects_missing_fields(tmp_path):
    path = tmp_path / "b.json"
    path.write_text(json.dumps([{"name": "A", "location": "X"}]))
    with pytest.raises(ValueError, match="category"):
        load_businesses(path)


def test_high_res_url_asks_for_a_width_that_passes_the_gate():
    url = high_res_url("https://lh5.googleusercontent.com/p/AF1Qip=w256-h256-k-no")
    assert url == "https://lh5.googleusercontent.com/p/AF1Qip=w1600-h1067-k-no"
