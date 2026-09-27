import hashlib

from conftest import FakeGemini
from pipeline_processor import build_listing, clean_text, generate_unique_story, make_place_id

RAW = {"name": "Allegory", "address": " 22 W Jefferson Ave,\nNaperville, IL", "category": "Restaurant", "city": "Naperville, IL"}


def test_clean_text_drops_private_use_glyphs_and_tidies_whitespace():
    assert clean_text(RAW["address"]) == "22 W Jefferson Ave, Naperville, IL"


def test_place_id_matches_the_original_formula():
    assert make_place_id("Allegory", "22 W Jefferson Ave") == hashlib.md5(b"Allegory_22 W Jefferson Ave").hexdigest()


def test_place_id_ignores_glyph_noise():
    noisy = build_listing(RAW, "story")
    clean = build_listing({**RAW, "address": "22 W Jefferson Ave, Naperville, IL"}, "story")
    assert noisy["place_id"] == clean["place_id"]


def test_listing_has_only_scraped_fields():
    listing = build_listing(RAW, "story")
    assert listing["title"] == "Allegory"
    assert listing["content"] == "story"
    assert listing["meta"] == {"business_address": "22 W Jefferson Ave, Naperville, IL", "business_category": "Restaurant", "business_city": "Naperville, IL"}


def test_story_comes_from_gemini():
    story, used_ai = generate_unique_story("Allegory", "Restaurant", "Naperville, IL", client=FakeGemini("  Two paragraphs.  "))
    assert (story, used_ai) == ("Two paragraphs.", True)


def test_story_falls_back_when_gemini_fails():
    story, used_ai = generate_unique_story("Allegory", "Restaurant", "Naperville, IL", client=FakeGemini(error=RuntimeError("quota")))
    assert used_ai is False
    assert "Naperville, IL" in story


def test_story_falls_back_on_empty_text():
    assert generate_unique_story("A", "Cafe", "X", client=FakeGemini(""))[1] is False
