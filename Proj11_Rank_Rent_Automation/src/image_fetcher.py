"""
image_fetcher.py — Pexels search → download → WP media upload.
Returns WP-hosted URLs so pages never link to external CDNs.
"""
import os
import hashlib
import random
import logging
import requests
from src.config import DeployConfig
from src.wp_client import WPClient

logger = logging.getLogger(__name__)

PEXELS_SEARCH = "https://api.pexels.com/v1/search"

# Synonym pools rotated per query to diversify results across deployments
_ROLE_WORDS = ["professional", "specialist", "contractor", "expert", "crew", "team", "worker"]
_ACTION_WORDS = ["service", "work", "installation", "project", "repair", "construction", "job"]
_STYLE_WORDS = ["residential", "outdoor", "modern", "quality", "finished", "completed", "new"]


def _deployment_variant(cfg: DeployConfig) -> int:
    """Return a stable per-deployment integer derived from business name + city.

    Two different clients always get a different variant number, so synonym
    selection and Pexels page offsets diverge between deployments.
    """
    key = f"{cfg.business_name.lower()}|{cfg.city.lower()}"
    digest = hashlib.md5(key.encode()).hexdigest()
    return int(digest[:6], 16)  # 0–16777215


def _service_to_query(service: str, variant: int = 0) -> list[str]:
    """Generate diversified Pexels search queries for a service name.

    variant shifts which synonyms are chosen, so two deployments for the
    same service keyword end up with different query strings.
    """
    base = service.lower().strip()
    first = base.split()[0]

    def _pick(pool: list[str], offset: int) -> str:
        return pool[(variant + offset) % len(pool)]

    role   = _pick(_ROLE_WORDS, 0)
    action = _pick(_ACTION_WORDS, 1)
    style  = _pick(_STYLE_WORDS, 2)
    role2  = _pick(_ROLE_WORDS, 3)

    return [
        f"{base} {role}",
        f"{base} {action} {style}",
        f"{role2} {first} {action}",
        f"{first} work {style}",
        f"{base} site {style}",
    ]


def _home_queries(services: list[str], variant: int = 0) -> dict:
    """Generate homepage image queries dynamically from the configured services."""
    s = [svc.lower() for svc in services]
    s0 = s[0] if s else "professional service"
    s1 = s[1] if len(s) > 1 else s0
    s2 = s[2] if len(s) > 2 else s0

    def _pick(pool: list[str], offset: int) -> str:
        return pool[(variant + offset) % len(pool)]

    role   = _pick(_ROLE_WORDS, 0)
    action = _pick(_ACTION_WORDS, 1)
    style  = _pick(_STYLE_WORDS, 2)

    return {
        "hero": f"{s0} {role} {style}",
        "best": f"{s0} {action} quality {style}",
        "svc1": f"{s0} work {role}",
        "svc2": f"{s1} {action} {role}",
        "svc3": f"{s2} {role} {action}",
    }


class ImageFetcher:
    def __init__(self, cfg: DeployConfig, wp: WPClient, image_queries: dict | None = None):
        self.cfg = cfg
        self.wp = wp
        self.api_key = cfg.pexels_api_key or os.getenv("PEXELS_API_KEY", "")
        self._used_ids: set = set()
        self._queries: dict = image_queries or {}
        # Per-deployment variant: different for each business+city combo
        self._variant = _deployment_variant(cfg)
        # Page base anchored to this deployment so Pexels result windows don't overlap
        self._page_base = (self._variant % 12) + 1  # 1–12

    def _search(self, query: str, count: int = 1) -> list[dict]:
        if not self.api_key:
            return []
        # Search a deployment-specific page band, then add per-call jitter
        page = self._page_base + random.randint(0, 3)
        try:
            r = requests.get(
                PEXELS_SEARCH,
                headers={"Authorization": self.api_key},
                params={"query": query, "per_page": count + 10,
                        "orientation": "landscape", "page": page},
                timeout=10,
            )
            r.raise_for_status()
            photos = r.json().get("photos", [])
            fresh = [p for p in photos if p["id"] not in self._used_ids]
            # If fresh results are scarce on this page, fall back to page 1
            if not fresh and page > 1:
                r2 = requests.get(
                    PEXELS_SEARCH,
                    headers={"Authorization": self.api_key},
                    params={"query": query, "per_page": count + 10,
                            "orientation": "landscape", "page": 1},
                    timeout=10,
                )
                r2.raise_for_status()
                photos = r2.json().get("photos", [])
                fresh = [p for p in photos if p["id"] not in self._used_ids]
            selected = fresh[:count]
            for p in selected:
                self._used_ids.add(p["id"])
            return selected
        except Exception as e:
            logger.warning("Pexels search failed for '%s': %s", query, e)
            return []

    def _download(self, photo: dict, width: int = 1200) -> bytes | None:
        url = photo["src"].get("large2x") or photo["src"].get("large") or photo["src"]["original"]
        url = url.split("?")[0] + f"?w={width}&auto=compress&cs=tinysrgb"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            return r.content
        except Exception as e:
            logger.warning("Image download failed: %s", e)
            return None

    def fetch_and_upload(self, query: str, filename: str) -> dict | None:
        photos = self._search(query, count=1)
        if not photos:
            logger.warning("No Pexels results for: %s", query)
            return None
        data = self._download(photos[0])
        if not data:
            return None
        result = self.wp.upload_image(data, filename)
        if result:
            logger.info("Uploaded %s → WP ID %s", filename, result["id"])
        return result

    def _q(self, key: str, fallback: str) -> str:
        return self._queries.get(key) or fallback

    def fetch_service_images(self, service: str) -> dict:
        """Fetch hero + 4 section images for a service page."""
        svc_key = f"svc_{service}"
        gemini_q = self._queries.get(svc_key)
        if gemini_q:
            queries = [gemini_q] if isinstance(gemini_q, str) else gemini_q
        else:
            queries = _service_to_query(service, self._variant)

        safe = service.lower().replace(" ", "-")
        images = {}
        slots = ["hero", "section1", "section2", "section3", "section4"]
        for i, slot in enumerate(slots):
            query = queries[i % len(queries)]
            img = self.fetch_and_upload(query, f"svc-{safe}-{slot}.jpg")
            images[slot] = img
            if img:
                logger.info("  %s: %s", slot, img["url"])
        return images

    def fetch_home_images(self) -> dict:
        """Fetch homepage images using Gemini-generated queries when available."""
        home_q = _home_queries(self.cfg.services, self._variant)
        images = {}
        for slot in ("hero", "best", "svc1", "svc2", "svc3"):
            query = self._q(slot, home_q.get(slot, "professional service worker"))
            img = self.fetch_and_upload(query, f"home-{slot}.jpg")
            images[slot] = img
        return images

    def fetch_blog_images(self, count: int = 9) -> list[dict | None]:
        """Fetch one image per blog post using Gemini-generated blog queries."""
        blog_queries = self._queries.get("blog") or [
            f"{svc.lower()} service work" for svc in (self.cfg.services or ["professional service"])
        ]
        if isinstance(blog_queries, str):
            blog_queries = [blog_queries]
        images = []
        for i in range(count):
            query = blog_queries[i % len(blog_queries)]
            img = self.fetch_and_upload(query, f"blog-post-{i+1}.jpg")
            images.append(img)
        return images

    def fetch_single(self, query: str, filename: str) -> dict | None:
        return self.fetch_and_upload(query, filename)
