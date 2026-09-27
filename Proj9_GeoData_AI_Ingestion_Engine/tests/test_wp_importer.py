import pytest
from fastapi.testclient import TestClient

from conftest import MockSession, make_jpeg
from wp_importer import WordPressClient, WordPressError, image_mime

LISTING = {"place_id": "abc", "title": "Allegory", "content": "story", "meta": {"business_address": "22 W Jefferson Ave", "business_category": "Restaurant", "business_city": "Naperville, IL"}}


def test_first_save_creates_second_updates_the_same_post(wp, mock_app):
    action1, id1 = wp.save_listing(LISTING)
    found = wp.find_listing("abc")
    action2, id2 = wp.save_listing({**LISTING, "content": "new story"}, post_id=found["id"])
    assert (action1, action2) == ("created", "updated")
    assert id1 == id2
    posts = mock_app.state.wp["posts"]
    assert len(posts) == 1
    assert posts[id1]["content"] == "new story"
    assert posts[id1]["meta"]["place_id"] == "abc"


def test_find_listing_returns_none_when_missing(wp):
    assert wp.find_listing("nope") is None


def test_media_upload_and_featured_image(wp, mock_app):
    media_id = wp.upload_media(make_jpeg(1600, 900), "allegory.jpg")
    _, post_id = wp.save_listing(LISTING, featured_media=media_id)
    assert wp.find_listing("abc") == {"id": post_id, "featured_media": media_id}


def test_update_without_gallery_keeps_the_existing_gallery(wp, mock_app):
    _, post_id = wp.save_listing(LISTING, gallery_ids=[7, 8])
    wp.save_listing(LISTING, post_id=post_id)
    assert mock_app.state.wp["posts"][post_id]["meta"]["gallery_images"] == [7, 8]


def test_image_mime_follows_the_real_format():
    assert image_mime(make_jpeg(4, 4, "PNG")) == "image/png"
    assert image_mime(make_jpeg(4, 4)) == "image/jpeg"


def test_wrong_credentials_raise(mock_app):
    bad = WordPressClient("http://testserver", ("x", "y"), session=MockSession(TestClient(mock_app)))
    with pytest.raises(WordPressError, match="HTTP 401"):
        bad.find_listing("abc")


def test_every_request_has_a_timeout(mock_app):
    """A slow site must fail the one business, not hang the whole batch."""
    seen = []

    class Recording(MockSession):
        def get(self, url, **kw):
            seen.append(kw.get("timeout"))
            return super().get(url, **kw)

        def post(self, url, **kw):
            seen.append(kw.get("timeout"))
            return super().post(url, **kw)

    client = WordPressClient("http://testserver", ("mock_admin", "mock_password"), session=Recording(TestClient(mock_app)), timeout=7)
    client.save_listing(LISTING, featured_media=client.upload_media(make_jpeg(4, 4), "a.jpg"))
    assert seen and all(t == 7 for t in seen)


def test_from_env_needs_all_three_settings(monkeypatch):
    import wp_importer

    monkeypatch.setattr(wp_importer, "load_dotenv", lambda: None)
    for key in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(WordPressError, match="WP_BASE_URL"):
        WordPressClient.from_env()
