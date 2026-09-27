"""WordPress REST client for directory listings. Any unexpected response raises WordPressError."""
import io
import os

import requests
from dotenv import load_dotenv
from PIL import Image

MIME = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


class WordPressError(RuntimeError):
    pass


def image_mime(image_bytes: bytes) -> str:
    return MIME.get(Image.open(io.BytesIO(image_bytes)).format, "image/jpeg")


class WordPressClient:
    def __init__(self, base_url: str, auth: tuple[str, str], session=None):
        self.base = base_url.rstrip("/")
        self.auth = auth
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls) -> "WordPressClient":
        load_dotenv()
        base, user, password = (os.getenv(k) for k in ("WP_BASE_URL", "WP_USERNAME", "WP_APP_PASSWORD"))
        if not (base and user and password):
            raise WordPressError("WP_BASE_URL, WP_USERNAME and WP_APP_PASSWORD must all be set in .env")
        return cls(base, (user, password))

    def _json(self, response, expected: int, what: str):
        if response.status_code != expected:
            raise WordPressError(f"{what} failed: HTTP {response.status_code} {response.text[:300]}")
        return response.json()

    def find_listing(self, place_id: str) -> dict | None:
        """Needs the proj9-directory-listing plugin, which adds the ?place_id= filter."""
        r = self.session.get(
            f"{self.base}/wp/v2/directory_listing",
            params={"place_id": place_id, "_fields": "id,featured_media"},
            auth=self.auth,
        )
        posts = self._json(r, 200, "Listing lookup")
        return {"id": posts[0]["id"], "featured_media": posts[0].get("featured_media", 0)} if posts else None

    def upload_media(self, image_bytes: bytes, filename: str) -> int:
        r = self.session.post(
            f"{self.base}/wp/v2/media",
            data=image_bytes,
            headers={"Content-Disposition": f'attachment; filename="{filename}"', "Content-Type": image_mime(image_bytes)},
            auth=self.auth,
        )
        return self._json(r, 201, f"Media upload ({filename})")["id"]

    def save_listing(self, listing: dict, post_id: int | None = None, featured_media: int | None = None, gallery_ids=()) -> tuple[str, int]:
        """Creates the post, or updates post_id. A missing gallery leaves the stored one alone."""
        meta = {**listing["meta"], "place_id": listing["place_id"]}
        if gallery_ids:
            meta["gallery_images"] = list(gallery_ids)
        body = {"title": listing["title"], "content": listing["content"], "status": "publish", "meta": meta}
        if featured_media:
            body["featured_media"] = featured_media
        if post_id:
            r = self.session.post(f"{self.base}/wp/v2/directory_listing/{post_id}", json=body, auth=self.auth)
            return "updated", self._json(r, 200, "Listing update")["id"]
        r = self.session.post(f"{self.base}/wp/v2/directory_listing", json=body, auth=self.auth)
        return "created", self._json(r, 201, "Listing create")["id"]
