"""
deployer.py — Full site deployment orchestrator.
Runs the entire pipeline: images → content → pages → posts.
"""
import sys
import time
import logging
from typing import Callable
from src.config import DeployConfig
from src.wp_client import WPClient
from src.image_fetcher import ImageFetcher
from src import content_gen, content_cache
from templates import service_page, homepage, blog, faqs, contact, services_hub

logger = logging.getLogger(__name__)


def _extract_page_hero_url(wp: WPClient, slug: str) -> str:
    """Pull the hero image URL from a stored service page's cover block."""
    import re as _re, json as _json
    try:
        r = wp._get("/pages", params={"slug": slug, "context": "edit", "per_page": 1}, timeout=10)
        if r.status_code == 200 and r.json():
            raw = r.json()[0].get("content", {}).get("raw", "")
            # Try block comment JSON first: <!-- wp:cover {"url":"https://..."} -->
            m = _re.search(r'<!--\s*wp:cover\s+(\{[^>]+?\})\s*-->', raw, _re.DOTALL)
            if m:
                try:
                    attrs = _json.loads(m.group(1))
                    if attrs.get("url"):
                        return attrs["url"]
                except Exception:
                    pass
            # Fallback: <img src="https://..."> inside wp-block-cover
            m2 = _re.search(r'class="wp-block-cover__image-background"[^>]+src="([^"]+)"', raw)
            if m2:
                return m2.group(1)
    except Exception:
        pass
    return ""


def deploy(cfg: DeployConfig, log: Callable[[str], None] = print,
           external_links: dict[str, str] | None = None) -> dict:
    """
    Full deployment. log() is called with progress strings for UI streaming.
    external_links: optional keyword→URL map for external sites (open in new tab).
    Returns a summary dict with success/fail counts.
    """
    summary = {"success": [], "failed": [], "warnings": [], "published_urls": []}

    # ------------------------------------------------------------------
    # 0. Validate config
    # ------------------------------------------------------------------
    errors = cfg.validate()
    if errors:
        for e in errors:
            log(f"❌ Config error: {e}")
        return summary

    # ------------------------------------------------------------------
    # 1. Connect to WordPress
    # ------------------------------------------------------------------
    log("🔌 Connecting to WordPress...")
    wp = WPClient(cfg)
    if not wp.test_connection():
        log("❌ WordPress connection failed. Check URL and credentials.")
        summary["failed"].append("WP connection")
        return summary
    log("✅ WordPress connected.")

    # ------------------------------------------------------------------
    # 1b. Ensure required plugins are installed and active
    # ------------------------------------------------------------------
    log("\n🎨 Checking required theme...")
    if wp.ensure_theme("astra", "Astra"):
        log("  ✅ Astra theme active.")
    else:
        log("  ⚠️  Could not auto-install Astra — install it manually in WP Admin → Appearance → Themes.")

    log("🗑️  Removing WordPress default pages (Sample Page, Privacy Policy)...")
    wp.delete_default_pages()

    log("⚙️  Updating site title...")
    primary_service = cfg.services[0] if cfg.services else "Local Service"
    tagline = f"{primary_service} serving {cfg.city}, {cfg.state}"
    if wp.update_site_settings(cfg.business_name, tagline):
        log(f"   ✅ Site title set to: {cfg.business_name}")
    else:
        log("   ⚠️  Could not update site title — update manually in Settings → General.")

    if not cfg.rich_footer:
        log("🧹 Replacing Astra footer credit with branded copyright...")
        _footer_text = f"© [current_year] {cfg.business_name}. All Rights Reserved."
        if wp.set_footer_copyright(_footer_text, bg_color=cfg.dark_color, text_color="#ffffff", align="left"):
            log(f"  ✅ Footer styled (bg {cfg.dark_color}, white text, left-aligned): {_footer_text}")
        else:
            log("  ⚠️  Could not auto-set footer — set it manually in "
                "Appearance → Customize → Footer Builder → Copyright.")

    # ------------------------------------------------------------------
    # 2. Test Gemini (skipped when cached content is available)
    # ------------------------------------------------------------------
    _has_cache = bool(content_cache.get_image_queries(cfg))
    if not _has_cache:
        log("🧠 Testing Gemini API...")
        if not content_gen.test_connection(cfg):
            log("❌ Gemini API connection failed. Check your API key.")
            summary["failed"].append("Gemini connection")
            return summary
        log("✅ Gemini API ready.")
    else:
        log("🧠 Gemini test skipped — using cached content.")

    # ------------------------------------------------------------------
    # 2b. Generate Gemini image queries (once — used throughout)
    # ------------------------------------------------------------------
    log("🖼️  Generating image search queries...")
    img_queries = content_cache.get_image_queries(cfg) or content_gen.generate_image_queries(cfg)
    content_cache.set_image_queries(cfg, img_queries)
    log(f"   ✅ Queries ready (hero: \"{img_queries.get('hero', '')}\")")

    fetcher = ImageFetcher(cfg, wp, image_queries=img_queries)

    # ------------------------------------------------------------------
    # 3. Fetch homepage images
    # ------------------------------------------------------------------
    log("🖼️  Fetching homepage images from Pexels...")
    home_images = fetcher.fetch_home_images()
    log(f"   ✅ {sum(1 for v in home_images.values() if v)} homepage images uploaded.")

    # ------------------------------------------------------------------
    # 4. Generate and deploy service pages
    # ------------------------------------------------------------------
    log(f"\n📄 Deploying {len(cfg.services)} service pages...")
    log("   📁 Setting up Services parent page...")
    services_parent_id = wp.get_or_create_services_page()
    if services_parent_id:
        log(f"   ✅ Services parent page ready (id={services_parent_id})")
    else:
        log("   ⚠️  Could not create Services parent page — pages will be at root level.")

    # Build nav upfront using predicted URLs so it's ready before any page deploys
    log("\n🔗 Building nav menu from inputs...")
    _predicted_nav = _predict_service_nav(cfg, wp, services_parent_id)
    if wp.rebuild_full_nav(_predicted_nav):
        log("  ✅ Nav menu built.")
    else:
        log("  ⚠️  Nav build failed — will retry after deploy.")

    service_results = []

    for service in cfg.services:
        log(f"\n  → {service}")
        try:
            svc_content = content_cache.get_service(cfg, service)
            if svc_content:
                log(f"    📦 Using cached content.")
            else:
                log(f"    🧠 Generating content...")
                svc_content = content_gen.generate_service_page(cfg, service)
                content_cache.set_service(cfg, service, svc_content)
            time.sleep(3)

            log(f"    🖼️  Fetching images...")
            svc_images = fetcher.fetch_service_images(service)

            log(f"    📤 Building and pushing page...")
            payload = service_page.build_service_payload(cfg, svc_content, svc_images, parent_id=services_parent_id)
            result = wp.upsert_page(payload)

            if result:
                url = result.get("link", "")
                log(f"    ✅ Published: {url}")
                summary["success"].append(service)
                summary["published_urls"].append({"label": service, "url": url, "type": "page"})
                hero_url = (svc_images.get("hero") or {}).get("url", "")
                excerpt = svc_content.get("meta_description", "") or svc_content.get("intro", "")
                service_results.append({"service": service, "id": result["id"], "link": url, "hero_url": hero_url, "excerpt": excerpt})
            else:
                log(f"    ❌ Failed to push page to WordPress.")
                summary["failed"].append({"label": service, "type": "Service Page"})

        except Exception as e:
            log(f"    ❌ Error: {e}")
            summary["failed"].append({"label": service, "type": "Service Page"})
            logger.exception("Service page error: %s", e)

    # Build services hub page with hero image + cards linking to each service page
    if service_results:
        log("\n📋 Building services hub page...")
        try:
            _primary = cfg.services[0].lower() if cfg.services else "service"
            hub_hero = fetcher.fetch_single(img_queries.get("hero", f"{_primary} contractor professional"), "services-hub-hero.jpg")
            hub_items = [{"service": r["service"], "link": r["link"], "excerpt": r.get("excerpt", ""), "hero_url": r.get("hero_url", "")} for r in service_results]
            hub_payload = services_hub.build_services_hub_payload(cfg, hub_items, hub_hero)
            hub_result = wp.upsert_page(hub_payload)
            if hub_result:
                url = hub_result.get("link", "")
                log(f"  ✅ Services hub: {url}")
                summary["success"].append("Services Hub")
                summary["published_urls"].append({"label": "Services Hub", "url": url, "type": "page"})
            else:
                log("  ⚠️  Services hub failed.")
                summary["failed"].append({"label": "Services Hub", "type": "Page"})
        except Exception as e:
            log(f"  ⚠️  Services hub error: {e}")
            summary["failed"].append({"label": "Services Hub", "type": "Page"})

    # ------------------------------------------------------------------
    # 5. Generate and deploy blog posts
    # ------------------------------------------------------------------
    topics = cfg.blog_topics
    log(f"\n📝 Deploying {len(topics)} blog posts...")
    blog_images = fetcher.fetch_blog_images(len(topics))
    post_summaries = []

    for i, topic in enumerate(topics):
        log(f"  → Post {i+1}/{len(topics)}: {topic}")
        try:
            post_content = content_cache.get_blog(cfg, topic)
            if post_content:
                log(f"    📦 Using cached content.")
            else:
                post_content = content_gen.generate_blog_post(cfg, topic)
                content_cache.set_blog(cfg, topic, post_content)
            time.sleep(2)
            featured = blog_images[i] if i < len(blog_images) else None
            payload = blog.build_post_payload(cfg, post_content, featured)
            result = wp.upsert_post(payload)
            if result:
                url = result.get("link", "")
                log(f"    ✅ {url}")
                post_summaries.append({
                    "title": post_content.get("title", topic),
                    "slug": post_content.get("slug", ""),
                    "excerpt": post_content.get("meta_description", ""),
                    "featured_image": featured,
                })
                summary["success"].append(f"Blog: {topic[:40]}")
                summary["published_urls"].append({"label": topic, "url": url, "type": "post"})
            else:
                summary["failed"].append({"label": topic, "type": "Blog Post"})
        except Exception as e:
            log(f"    ❌ Error: {e}")
            summary["failed"].append({"label": topic, "type": "Blog Post"})

    # ------------------------------------------------------------------
    # 6. Blog listing page
    # ------------------------------------------------------------------
    log("\n📰 Building blog listing page...")
    try:
        blog_hero = fetcher.fetch_single(img_queries.get("faq", f"{primary_service.lower()} professional editorial"), "blog-hero.jpg")
        blog_listing_payload = blog.build_blog_listing_payload(cfg, post_summaries, blog_hero)
        result = wp.upsert_page(blog_listing_payload)
        if result:
            url = result.get("link", "")
            log(f"  ✅ Blog listing: {url}")
            summary["success"].append("Blog listing")
            summary["published_urls"].append({"label": "Blog", "url": url, "type": "page"})
        else:
            summary["failed"].append({"label": "Blog listing", "type": "Page"})
    except Exception as e:
        log(f"  ❌ Blog listing error: {e}")
        summary["failed"].append({"label": "Blog listing", "type": "Page"})

    # ------------------------------------------------------------------
    # 7. FAQs page
    # ------------------------------------------------------------------
    log("\n❓ Building FAQs page...")
    try:
        faq_content = content_cache.get_faqs(cfg)
        if faq_content:
            log("  📦 Using cached content.")
        else:
            faq_content = content_gen.generate_faqs(cfg)
            content_cache.set_faqs(cfg, faq_content)
        faq_hero = fetcher.fetch_single(img_queries.get("faq", f"{primary_service.lower()} service professional"), "faq-hero.jpg")
        faq_payload = faqs.build_faqs_payload(cfg, faq_content, faq_hero)
        result = wp.upsert_page(faq_payload)
        if result:
            url = result.get("link", "")
            log(f"  ✅ FAQs: {url}")
            summary["success"].append("FAQs")
            summary["published_urls"].append({"label": "FAQs", "url": url, "type": "page"})
        else:
            summary["failed"].append({"label": "FAQs", "type": "Page"})
    except Exception as e:
        log(f"  ❌ FAQs error: {e}")
        summary["failed"].append({"label": "FAQs", "type": "Page"})

    # ------------------------------------------------------------------
    # 8. Contact form plugin + contact page
    # ------------------------------------------------------------------
    log("\n📬 Installing contact form handler...")
    try:
        ok = wp.install_contact_plugin(cfg.contact_email)
        if ok:
            log("  ✅ Contact plugin installed and activated")
        else:
            log("  ⚠️  Contact plugin install failed — form will not send emails")
    except Exception as e:
        log(f"  ⚠️  Contact plugin error: {e}")

    if cfg.rich_footer:
        log("🧹 Building rich footer (brand · services · contact)...")
        if wp.set_rich_footer(cfg):
            log("  ✅ Rich footer applied.")
        else:
            log("  ⚠️  Rich footer could not be applied — check plugin install.")

    if cfg.smtp_host:
        log("\n📧 Installing WP Mail SMTP...")
        try:
            ok = wp.install_smtp_plugin(cfg)
            if ok:
                log(f"  ✅ WP Mail SMTP installed — sending via {cfg.smtp_host}")
            else:
                log("  ⚠️  WP Mail SMTP install failed — emails may not deliver")
        except Exception as e:
            log(f"  ⚠️  WP Mail SMTP error: {e}")

    log("\n📞 Building contact page...")
    try:
        contact_content = content_cache.get_contact(cfg)
        if contact_content:
            log("  📦 Using cached content.")
        else:
            contact_content = content_gen.generate_contact(cfg)
            content_cache.set_contact(cfg, contact_content)
        contact_hero = fetcher.fetch_single(img_queries.get("contact", f"{primary_service.lower()} residential home"), "contact-hero.jpg")
        contact_payload = contact.build_contact_payload(cfg, contact_content, contact_hero)
        result = wp.upsert_page(contact_payload)
        if result:
            url = result.get("link", "")
            log(f"  ✅ Contact: {url}")
            summary["success"].append("Contact")
            summary["published_urls"].append({"label": "Contact Us", "url": url, "type": "page"})
        else:
            summary["failed"].append({"label": "Contact Us", "type": "Page"})
    except Exception as e:
        log(f"  ❌ Contact error: {e}")
        summary["failed"].append({"label": "Contact Us", "type": "Page"})

    # ------------------------------------------------------------------
    # 9. Homepage (last — references service pages)
    # ------------------------------------------------------------------
    log("\n🏠 Building homepage...")
    try:
        home_content = content_cache.get_homepage(cfg)
        if home_content:
            log("  📦 Using cached content.")
        else:
            home_content = content_gen.generate_homepage(cfg, cfg.services)
            content_cache.set_homepage(cfg, home_content)
        time.sleep(2)

        # v2: hero is built inside homepage.py itself as native Gutenberg blocks.
        home_payload = homepage.build_homepage_payload(cfg, home_content, home_images)

        # WordPress page ID 0 = create new; look up existing "home" page first
        result = wp.upsert_page(home_payload)
        if result:
            page_id = result["id"]
            wp.set_front_page(page_id)
            url = result.get("link", "")
            log(f"  ✅ Homepage: {url}")
            summary["success"].append("Homepage")
            summary["published_urls"].append({"label": "Homepage", "url": url, "type": "page"})
        else:
            summary["failed"].append({"label": "Homepage", "type": "Page"})
    except Exception as e:
        log(f"  ❌ Homepage error: {e}")
        summary["failed"].append({"label": "Homepage", "type": "Page"})

    # ------------------------------------------------------------------
    # 10. Auto-interlink all deployed pages/posts
    # ------------------------------------------------------------------
    _ext = {k: v for k, v in (external_links or {}).items() if k and v}
    _link_label = "internal + external" if _ext else "internal"
    log(f"\n🔗 Auto-linking {_link_label} references...")
    _SLUG_BY_LABEL = {
        "homepage": "home",
        "blog": "blog",
        "faqs": "faqs",
        "contact us": "contact-us",
        "services": "services",
        "services hub": "services",
    }
    try:
        from src.interlinker import build_internal_url_map, inject_links, fetch_page_html, fetch_post_html
        internal_map = build_internal_url_map(summary["published_urls"], cfg.services)
        all_links = {**internal_map, **_ext}
        new_tab_urls = set(_ext.values())
        if not all_links:
            log("   — No URL pairs built; skipping.")
        else:
            log(f"   Built {len(internal_map)} internal + {len(_ext)} external keyword→URL pairs")
            linked_count = 0
            for item in summary["published_urls"]:
                item_url = item.get("url", "").rstrip("/")
                item_type = item.get("type", "page")
                item_label = item.get("label", "")
                # Resolve slug: use known mappings first, then extract from URL
                slug = _SLUG_BY_LABEL.get(item_label.lower()) or item_url.split("/")[-1]
                if not slug:
                    continue
                if item_type == "post":
                    page_id, html = fetch_post_html(wp, slug)
                else:
                    page_id, html = fetch_page_html(wp, slug)
                if not page_id or not html:
                    log(f"   — Could not fetch: {item_label}")
                    continue
                # Exclude self-links (don't link a page to itself)
                filtered_map = {kw: u for kw, u in all_links.items()
                                if u.rstrip("/") != item_url}
                new_html = inject_links(html, filtered_map, new_tab_urls=new_tab_urls)
                if new_html == html:
                    log(f"   — No matches: {item_label}")
                    continue
                r = wp._post(f"/{item_type}s/{page_id}",
                             json={"content": new_html}, timeout=20)
                if r.status_code in (200, 201):
                    log(f"   ✅ Linked: {item_label}")
                    linked_count += 1
                else:
                    log(f"   ⚠️  Update failed ({r.status_code}): {item_label}")
            log(f"   🔗 Done — {linked_count}/{len(summary['published_urls'])} pages updated")
    except Exception as e:
        log(f"   ⚠️  Auto-interlinking error: {e}")
        summary["warnings"].append(f"Auto-interlinking: {e}")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    import json as _json
    log(f"\n{'='*50}")
    log(f"✅ Succeeded: {len(summary['success'])}")
    log(f"❌ Failed:    {len(summary['failed'])}")
    log(f"{'='*50}")
    # Emit structured report for the UI to render
    log(f"__REPORT__:{_json.dumps({'published': summary['published_urls'], 'failed': summary['failed']})}")

    return summary


def deploy_retry(cfg: DeployConfig, failed_items: list, log: Callable[[str], None] = print) -> dict:
    """Re-runs only the items that failed in a previous deployment."""
    summary = {"success": [], "failed": [], "published_urls": []}

    log("🔌 Connecting to WordPress...")
    wp = WPClient(cfg)
    if not wp.test_connection():
        log("❌ WordPress connection failed.")
        return summary
    log("✅ WordPress connected.")

    img_queries = content_cache.get_image_queries(cfg) or content_gen.generate_image_queries(cfg)
    fetcher = ImageFetcher(cfg, wp, image_queries=img_queries)
    services_parent_id = wp.get_or_create_services_page()

    failed_labels = {
        (item["label"] if isinstance(item, dict) else item): (item.get("type", "") if isinstance(item, dict) else "")
        for item in failed_items
    }

    blog_posts_retried = False
    blog_retry_index = [0]  # mutable counter for unique filenames across blog retries
    service_pages_retried = False

    for label, item_type in failed_labels.items():
        log(f"\n🔁 Retrying: {label} ({item_type})")
        try:
            if item_type == "Service Page":
                svc_content = content_cache.get_service(cfg, label)
                if svc_content:
                    log("  📦 Using cached content.")
                else:
                    svc_content = content_gen.generate_service_page(cfg, label)
                    content_cache.set_service(cfg, label, svc_content)
                svc_images = fetcher.fetch_service_images(label)
                payload = service_page.build_service_payload(cfg, svc_content, svc_images, parent_id=services_parent_id)
                result = wp.upsert_page(payload)
                if result:
                    url = result.get("link", "")
                    log(f"  ✅ Published: {url}")
                    summary["success"].append(label)
                    summary["published_urls"].append({"label": label, "url": url, "type": "page"})
                    service_pages_retried = True
                else:
                    log(f"  ❌ Still failed.")
                    summary["failed"].append({"label": label, "type": item_type})

            elif item_type == "Blog Post":
                post_content = content_cache.get_blog(cfg, label)
                if post_content:
                    log("  📦 Using cached content.")
                else:
                    post_content = content_gen.generate_blog_post(cfg, label)
                    content_cache.set_blog(cfg, label, post_content)
                _primary = cfg.services[0].lower() if cfg.services else "service"
                idx = blog_retry_index[0]
                blog_retry_index[0] += 1
                blog_img = fetcher.fetch_single(fetcher._q("blog", f"{_primary} professional"), f"blog-retry-{idx}.jpg")
                payload = blog.build_post_payload(cfg, post_content, blog_img)
                result = wp.upsert_post(payload)
                if result:
                    url = result.get("link", "")
                    log(f"  ✅ Published: {url}")
                    summary["success"].append(label)
                    summary["published_urls"].append({"label": label, "url": url, "type": "post"})
                    blog_posts_retried = True
                else:
                    log(f"  ❌ Still failed.")
                    summary["failed"].append({"label": label, "type": item_type})

            elif item_type in ("Page", "Blog listing"):
                _retry_page(cfg, wp, fetcher, label, summary, log)

            else:
                log(f"  ⚠️  Unknown item type '{item_type}' — cannot retry.")
                summary["failed"].append({"label": label, "type": item_type})

        except Exception as e:
            log(f"  ❌ Error: {e}")
            summary["failed"].append({"label": label, "type": item_type})

    if service_pages_retried:
        log("\n🔧 Rebuilding Services Hub with all published service pages...")
        try:
            from templates import services_hub as svc_hub_tmpl
            _primary = cfg.services[0].lower() if cfg.services else "service"
            hub_hero = fetcher.fetch_single(fetcher._q("hero", f"{_primary} contractor professional"), "services-hub-hero.jpg")
            svc_pages = wp.get_service_pages()
            hub_items = []
            for p in svc_pages:
                svc_slug = p["link"].rstrip("/").split("/")[-1]
                svc_hero_url = _extract_page_hero_url(wp, svc_slug)
                if not svc_hero_url:
                    svc_safe = p["service"].lower().replace(" ", "-")
                    svc_img = fetcher.fetch_service_images(p["service"])
                    svc_hero_url = (svc_img.get("hero") or {}).get("url", "")
                cached = content_cache.get_service(cfg, p["service"]) or {}
                excerpt = cached.get("meta_description", "") or cached.get("intro", "")
                hub_items.append({"service": p["service"], "link": p["link"], "excerpt": excerpt, "hero_url": svc_hero_url})
            hub_payload = svc_hub_tmpl.build_services_hub_payload(cfg, hub_items, hub_hero)
            result = wp.upsert_page(hub_payload)
            if result:
                url = result.get("link", "")
                log(f"  ✅ Services Hub updated: {url}")
                summary["published_urls"].append({"label": "Services Hub", "url": url, "type": "page"})
            else:
                log("  ❌ Services Hub update failed.")
        except Exception as e:
            log(f"  ❌ Services Hub rebuild error: {e}")

    if blog_posts_retried:
        log("\n📰 Rebuilding blog listing with all published posts...")
        try:
            _primary = cfg.services[0].lower() if cfg.services else "service"
            blog_hero = fetcher.fetch_single(fetcher._q("faq", f"{_primary} professional editorial"), "blog-hero.jpg")
            all_posts = wp.get_published_posts()
            blog_listing_payload = blog.build_blog_listing_payload(cfg, all_posts, blog_hero)
            result = wp.upsert_page(blog_listing_payload)
            if result:
                url = result.get("link", "")
                log(f"  ✅ Blog listing updated: {url}")
                summary["published_urls"].append({"label": "Blog", "url": url, "type": "page"})
            else:
                log("  ❌ Blog listing update failed.")
        except Exception as e:
            log(f"  ❌ Blog listing rebuild error: {e}")

    # Re-run full-site internal linking so retried pages link to original pages
    # and original pages link back to newly published retried pages.
    try:
        from src.interlinker import build_internal_url_map, inject_links, fetch_page_html, fetch_post_html

        # Discover ALL published pages/posts from WP (not just the ones retried)
        all_published: list[dict] = []
        for p in wp.get_service_pages():
            all_published.append({"label": p["service"], "url": p["link"], "type": "page"})
        for slug, label in [("home", "Homepage"), ("blog", "Blog"),
                             ("faqs", "FAQs"), ("contact-us", "Contact Us"),
                             ("services", "Services Hub")]:
            try:
                r = wp._get("/pages", params={"slug": slug, "per_page": 1}, timeout=10)
                if r.status_code == 200 and r.json():
                    all_published.append({"label": label, "url": r.json()[0]["link"], "type": "page"})
            except Exception:
                pass
        posts = wp.get_published_posts() if hasattr(wp, "get_published_posts") else []
        for p in posts:
            all_published.append({"label": p.get("title", {}).get("rendered", ""), "url": p.get("link", ""), "type": "post"})

        internal_map = build_internal_url_map(all_published, cfg.services)
        if internal_map:
            log(f"\n🔗 Re-applying internal links across full site ({len(internal_map)} pairs)...")
            linked_count = 0
            for item in all_published:
                item_url = item.get("url", "").rstrip("/")
                item_type = item.get("type", "page")
                slug = item_url.split("/")[-1]
                if not slug:
                    continue
                if item_type == "post":
                    page_id, html = fetch_post_html(wp, slug)
                else:
                    page_id, html = fetch_page_html(wp, slug)
                if not page_id or not html:
                    continue
                filtered_map = {kw: u for kw, u in internal_map.items() if u.rstrip("/") != item_url}
                new_html = inject_links(html, filtered_map)
                if new_html != html:
                    r = wp._post(f"/{item_type}s/{page_id}", json={"content": new_html}, timeout=20)
                    if r.status_code in (200, 201):
                        linked_count += 1
            log(f"   🔗 Done — {linked_count}/{len(all_published)} pages updated")
    except Exception as e:
        log(f"   ⚠️  Internal linking error: {e}")

    import json as _json
    log(f"__REPORT__:{_json.dumps({'published': summary['published_urls'], 'failed': summary['failed']})}")
    return summary


def _retry_page(cfg, wp, fetcher, label, summary, log):
    from templates import faqs, contact, blog, homepage, services_hub
    import json as _json

    if label == "Services Hub":
        _primary = cfg.services[0].lower() if cfg.services else "service"
        hub_hero = fetcher.fetch_single(fetcher._q("hero", f"{_primary} contractor professional"), "services-hub-hero.jpg")
        svc_pages = wp.get_service_pages()
        hub_items = []
        for p in svc_pages:
            svc_slug = p["link"].rstrip("/").split("/")[-1]
            svc_hero_url = _extract_page_hero_url(wp, svc_slug)
            if not svc_hero_url:
                svc_img = fetcher.fetch_service_images(p["service"])
                svc_hero_url = (svc_img.get("hero") or {}).get("url", "")
            cached = content_cache.get_service(cfg, p["service"]) or {}
            excerpt = cached.get("meta_description", "") or cached.get("intro", "")
            hub_items.append({"service": p["service"], "link": p["link"], "excerpt": excerpt, "hero_url": svc_hero_url})
        payload = services_hub.build_services_hub_payload(cfg, hub_items, hub_hero)
        result = wp.upsert_page(payload)
    elif label == "FAQs":
        faq_content = content_cache.get_faqs(cfg)
        if faq_content:
            log("  📦 Using cached content.")
        else:
            faq_content = content_gen.generate_faqs(cfg)
            content_cache.set_faqs(cfg, faq_content)
        _primary = cfg.services[0].lower() if cfg.services else "service"
        faq_hero = fetcher.fetch_single(fetcher._q("faq", f"{_primary} service professional"), "faq-hero.jpg")
        payload = faqs.build_faqs_payload(cfg, faq_content, faq_hero)
        result = wp.upsert_page(payload)
    elif label == "Contact Us":
        contact_content = content_cache.get_contact(cfg)
        if contact_content:
            log("  📦 Using cached content.")
        else:
            contact_content = content_gen.generate_contact(cfg)
            content_cache.set_contact(cfg, contact_content)
        _primary = cfg.services[0].lower() if cfg.services else "service"
        contact_hero = fetcher.fetch_single(fetcher._q("contact", f"{_primary} residential home"), "contact-hero.jpg")
        payload = contact.build_contact_payload(cfg, contact_content, contact_hero)
        result = wp.upsert_page(payload)
    elif label == "Blog listing":
        _primary = cfg.services[0].lower() if cfg.services else "service"
        blog_hero = fetcher.fetch_single(fetcher._q("faq", f"{_primary} professional editorial"), "blog-hero.jpg")
        all_posts = wp.get_published_posts()
        payload = blog.build_blog_listing_payload(cfg, all_posts, blog_hero)
        result = wp.upsert_page(payload)
    elif label == "Homepage":
        home_images = fetcher.fetch_home_images()
        home_content = content_cache.get_homepage(cfg)
        if home_content:
            log("  📦 Using cached content.")
        else:
            home_content = content_gen.generate_homepage(cfg, cfg.services)
            content_cache.set_homepage(cfg, home_content)
        payload = homepage.build_homepage_payload(cfg, home_content, home_images)
        result = wp.upsert_page(payload)
    else:
        log(f"  ⚠️  Don't know how to retry: {label}")
        return

    if result:
        url = result.get("link", "")
        log(f"  ✅ Published: {url}")
        summary["success"].append(label)
        summary["published_urls"].append({"label": label, "url": url, "type": "page"})
        if label == "Homepage":
            wp.set_front_page(result["id"])
            log("  ✅ Set as front page.")
    else:
        log(f"  ❌ Still failed.")
        summary["failed"].append({"label": label, "type": "Page"})


def _predict_service_nav(cfg: DeployConfig, wp, services_parent_id: int | None) -> list[dict]:
    """Compute predicted service page URLs from config inputs before pages are deployed."""
    import re

    def slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^\w\s-]", "", text)
        text = re.sub(r"[\s_]+", "-", text)
        return re.sub(r"-+", "-", text)

    site = cfg.wp_site_url().rstrip("/")
    services_slug = "services"
    if services_parent_id:
        slug = wp.get_services_parent_url(services_parent_id)
        if slug:
            services_slug = slug

    return [
        {
            "service": svc,
            "link": f"{site}/{services_slug}/{slugify(svc + ' ' + cfg.city)}/",
        }
        for svc in cfg.services
    ]


# Note: hero markup moved into templates/homepage.py (build_homepage) for v2 —
# it's now built as native Gutenberg blocks instead of a separate wp:html chunk.
