"""
content_cache.py — File-based cache for Gemini-generated content.
Scoped per deployment target (wp_url + city + business_name).
Used by deploy_retry to skip Gemini calls for content already generated.
"""
import json
import os
import re

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "cache")


def _slug(s: str) -> str:
    return re.sub(r"[^\w]", "_", s.lower().strip())[:40]


def _cache_path(cfg) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = f"{_slug(cfg.wp_url)}_{_slug(cfg.city)}_{_slug(cfg.business_name)}"
    return os.path.join(CACHE_DIR, f"{key}.json")


def _load(cfg) -> dict:
    path = _cache_path(cfg)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _save(cfg, data: dict):
    try:
        with open(_cache_path(cfg), "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


# ------------------------------------------------------------------
# Service pages
# ------------------------------------------------------------------

def get_service(cfg, service: str) -> dict | None:
    return _load(cfg).get("service_pages", {}).get(service)


def set_service(cfg, service: str, content: dict):
    data = _load(cfg)
    data.setdefault("service_pages", {})[service] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# Blog posts
# ------------------------------------------------------------------

def get_blog(cfg, topic: str) -> dict | None:
    return _load(cfg).get("blog_posts", {}).get(topic)


def set_blog(cfg, topic: str, content: dict):
    data = _load(cfg)
    data.setdefault("blog_posts", {})[topic] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# FAQs
# ------------------------------------------------------------------

def get_faqs(cfg) -> dict | None:
    return _load(cfg).get("faqs")


def set_faqs(cfg, content: dict):
    data = _load(cfg)
    data["faqs"] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# Homepage
# ------------------------------------------------------------------

def get_homepage(cfg) -> dict | None:
    return _load(cfg).get("homepage")


def set_homepage(cfg, content: dict):
    data = _load(cfg)
    data["homepage"] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# Contact page
# ------------------------------------------------------------------

def get_contact(cfg) -> dict | None:
    return _load(cfg).get("contact")


def set_contact(cfg, content: dict):
    data = _load(cfg)
    data["contact"] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# Image queries (Gemini-generated)
# ------------------------------------------------------------------

def get_image_queries(cfg) -> dict | None:
    return _load(cfg).get("image_queries")


def set_image_queries(cfg, content: dict):
    data = _load(cfg)
    data["image_queries"] = content
    _save(cfg, data)


# ------------------------------------------------------------------
# Cache management
# ------------------------------------------------------------------

def clear(cfg) -> bool:
    path = _cache_path(cfg)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def list_caches() -> list[dict]:
    if not os.path.exists(CACHE_DIR):
        return []
    result = []
    for fname in os.listdir(CACHE_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(CACHE_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            counts = {
                "service_pages": len(data.get("service_pages", {})),
                "blog_posts": len(data.get("blog_posts", {})),
                "faqs": 1 if data.get("faqs") else 0,
                "homepage": 1 if data.get("homepage") else 0,
            }
            result.append({"file": fname, "counts": counts})
        except Exception:
            pass
    return result
