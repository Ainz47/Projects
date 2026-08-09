"""
wp_client.py — WordPress REST API wrapper.
Handles auth, page upsert, media upload, and nav menu.
"""
import re
import io
import json
import logging
import requests
from datetime import datetime
from src.config import DeployConfig

logger = logging.getLogger(__name__)


class WPClient:
    def __init__(self, cfg: DeployConfig):
        self.cfg = cfg
        self.base = cfg.wp_api_base()
        self.site = cfg.wp_site_url()
        self.auth = (cfg.wp_username, cfg.wp_password)
        self._session: requests.Session | None = None
        self._nonce: str | None = None

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _get_session(self) -> tuple[requests.Session, str]:
        if self._session and self._nonce:
            return self._session, self._nonce

        s = requests.Session()
        s.cookies.set("wordpress_test_cookie", "WP Cookie check",
                      domain=self.site.split("//")[-1].split("/")[0])
        resp = s.post(f"{self.site}/wp-login.php", data={
            "log": self.cfg.wp_username,
            "pwd": self.cfg.wp_password,
            "wp-submit": "Log In",
            "redirect_to": f"{self.site}/wp-admin/",
            "testcookie": "1",
        }, allow_redirects=True, timeout=20)

        if "/wp-admin" not in resp.url and "Dashboard" not in resp.text:
            raise RuntimeError("WP login failed — check username and password")

        admin = s.get(f"{self.site}/wp-admin/", timeout=15)
        m = re.search(r'wpApiSettings\s*=\s*\{[^}]*?"nonce"\s*:\s*"([^"]+)"', admin.text, re.DOTALL)
        if not m:
            raise RuntimeError("Could not extract WP REST nonce after login")

        self._session, self._nonce = s, m.group(1)
        return self._session, self._nonce

    def _get(self, path: str, **kwargs) -> requests.Response:
        s, nonce = self._get_session()
        return s.get(f"{self.base}{path}", headers={"X-WP-Nonce": nonce}, **kwargs)

    def _post(self, path: str, retries: int = 3, **kwargs) -> requests.Response:
        import time
        s, nonce = self._get_session()
        for attempt in range(retries):
            r = s.post(f"{self.base}{path}", headers={"X-WP-Nonce": nonce}, **kwargs)
            if r.status_code < 500:
                return r
            logger.warning("WP %s returned %s, retrying (%d/%d)...", path, r.status_code, attempt + 1, retries)
            if attempt < retries - 1:
                time.sleep(6 * (attempt + 1))
        return r

    # ------------------------------------------------------------------
    # Connection test
    # ------------------------------------------------------------------

    def test_connection(self) -> bool:
        try:
            r = self._get("/users/me", timeout=10)
            if r.status_code == 200:
                name = r.json().get("name", "Unknown")
                logger.info("WP connected as: %s", name)
                return True
            logger.error("WP auth failed: %s", r.status_code)
            return False
        except Exception as e:
            logger.error("WP connection error: %s", e)
            return False

    def ensure_theme(self, slug: str, display_name: str) -> bool:
        """Install and activate a theme via WP admin AJAX (works on any host)."""
        try:
            s, _ = self._get_session()

            # Check if already active via REST
            r = self._get("/themes?status=active", timeout=15)
            if r.status_code == 200:
                for t in r.json():
                    if t.get("stylesheet") == slug:
                        logger.info("%s already active", display_name)
                        return True

            # Check if installed but not active
            r2 = self._get("/themes", timeout=15)
            installed = False
            if r2.status_code == 200:
                for t in r2.json():
                    if t.get("stylesheet") == slug:
                        installed = True
                        break

            activate_url = None

            if not installed:
                # Nonce lives in _wpUpdatesSettings.ajax_nonce on any WP admin page
                page = s.get(f"{self.site}/wp-admin/theme-install.php", timeout=20)
                m = re.search(r'_wpUpdatesSettings\s*=\s*\{[^}]*?"ajax_nonce"\s*:\s*"([^"]+)"', page.text, re.DOTALL)
                if not m:
                    m = re.search(r'"ajax_nonce"\s*:\s*"([^"]+)"', page.text)
                nonce = m.group(1) if m else ""
                logger.info("Theme install nonce acquired: %s", bool(nonce))

                install_r = s.post(f"{self.site}/wp-admin/admin-ajax.php", data={
                    "action": "install-theme",
                    "slug": slug,
                    "_ajax_nonce": nonce,
                }, timeout=60)
                logger.info("Theme install response (%s): %s", install_r.status_code, install_r.text[:300])

                if install_r.status_code not in (200, 302):
                    logger.error("Theme install via admin-ajax failed: %s", install_r.status_code)
                    return False

                try:
                    resp = install_r.json()
                    if resp.get("success"):
                        # Response includes activateUrl with nonce already embedded
                        activate_url = resp.get("data", {}).get("activateUrl")
                        logger.info("%s installed — activateUrl: %s", display_name, activate_url)
                    else:
                        logger.warning("Theme install JSON: %s", resp)
                except Exception:
                    pass

            # Activate — prefer activateUrl from install response, fallback to themes.php scrape
            if not activate_url:
                themes_page = s.get(f"{self.site}/wp-admin/themes.php", timeout=15)
                # WP activation URL: ?action=activate&_wpnonce=XYZ&stylesheet=slug  (nonce before stylesheet)
                m = re.search(
                    rf'action=activate[^"\']*_wpnonce=([a-zA-Z0-9]+)[^"\']*stylesheet={re.escape(slug)}',
                    themes_page.text,
                )
                if not m:
                    m = re.search(
                        rf'action=activate[^"\']*stylesheet={re.escape(slug)}[^"\']*_wpnonce=([a-zA-Z0-9]+)',
                        themes_page.text,
                    )
                if m:
                    activate_url = (
                        f"{self.site}/wp-admin/themes.php"
                        f"?action=activate&_wpnonce={m.group(1)}&stylesheet={slug}"
                    )

            if activate_url:
                act_r = s.get(activate_url, timeout=15, allow_redirects=True)
                logger.info("%s activate response: %s", display_name, act_r.status_code)
                return True

            logger.error("Could not find activation URL for %s", slug)
        except Exception as e:
            logger.error("ensure_theme error for %s: %s", slug, e)
        return False

    def ensure_plugin(self, slug: str, display_name: str) -> bool:
        """Install and activate a plugin if not already active."""
        try:
            r = self._get("/plugins", timeout=15)
            if r.status_code == 200:
                for plugin in r.json():
                    if plugin.get("plugin", "").startswith(slug + "/"):
                        if plugin.get("status") == "active":
                            logger.info("%s already active", display_name)
                            return True
                        r2 = self._post(f"/plugins/{plugin['plugin']}", json={"status": "active"}, timeout=30)
                        if r2.status_code == 200:
                            logger.info("%s activated", display_name)
                            return True

            r3 = self._post("/plugins", json={"slug": slug, "status": "active"}, timeout=60)
            if r3.status_code == 201:
                logger.info("%s installed and activated", display_name)
                return True
            logger.error("Plugin install failed (%s): %s", r3.status_code, r3.text[:200])
        except Exception as e:
            logger.error("ensure_plugin error for %s: %s", slug, e)
        return False

    # ------------------------------------------------------------------
    # Pages
    # ------------------------------------------------------------------

    def _find_page(self, slug: str) -> int | None:
        try:
            r = self._get("/pages", params={"slug": slug, "status": "any"}, timeout=10)
            pages = r.json()
            if isinstance(pages, list) and pages:
                return pages[0]["id"]
        except Exception:
            pass
        return None

    def get_or_create_services_page(self) -> int | None:
        """Return the ID of the Services parent page, creating it if needed."""
        existing = self._find_services_parent()
        if existing:
            logger.info("Services parent page already exists: id=%s", existing)
            return existing
        try:
            r = self._post("/pages", json={
                "title": "Services",
                "slug": "services",
                "content": "<!-- wp:html --><p>Explore our services below.</p><!-- /wp:html -->",
                "status": "publish",
                "meta": {"_astra-site-sidebar-layout": "no-sidebar"},
            }, timeout=20)
            if r.status_code == 201:
                page_id = r.json()["id"]
                logger.info("Created Services parent page: id=%s", page_id)
                return page_id
            logger.error("Failed to create Services page: %s", r.status_code)
        except Exception as e:
            logger.error("Services page creation error: %s", e)
        return None

    def _archive_page(self, page_id: int, original_slug: str) -> bool:
        """Copy an existing page to a draft archive before overwriting it."""
        try:
            r = self._get(f"/pages/{page_id}", params={"context": "edit"}, timeout=10)
            if r.status_code != 200:
                return False
            page = r.json()
            date_tag = datetime.now().strftime("%Y%m%d")
            archive_payload = {
                "title":   f"[BAK {date_tag}] {page.get('title', {}).get('raw', original_slug)}",
                "slug":    f"{original_slug}-bak-{date_tag}",
                "content": page.get("content", {}).get("raw", ""),
                "status":  "draft",
            }
            ar = self._post("/pages", json=archive_payload, timeout=30)
            if ar.status_code == 201:
                logger.info("Archived page '%s' as draft id=%s", original_slug, ar.json()["id"])
                return True
            logger.warning("Archive draft failed (%s)", ar.status_code)
        except Exception as e:
            logger.warning("Archive page error: %s", e)
        return False

    def upsert_page(self, payload: dict) -> dict | None:
        slug = payload.get("slug", "")
        existing = self._find_page(slug)
        try:
            if existing:
                self._archive_page(existing, slug)
                r = self._post(f"/pages/{existing}", json=payload, timeout=30)
            else:
                r = self._post("/pages", json=payload, timeout=30)
            if r.status_code in (200, 201):
                return r.json()
            logger.error("Page upsert failed (%s): %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.error("Page upsert exception: %s", e)
        return None

    def _find_post(self, slug: str) -> int | None:
        try:
            r = self._get("/posts", params={"slug": slug, "status": "any"}, timeout=10)
            posts = r.json()
            if isinstance(posts, list) and posts:
                return posts[0]["id"]
        except Exception:
            pass
        return None

    def _archive_post(self, post_id: int, original_slug: str) -> bool:
        """Copy an existing post to a draft archive before overwriting it."""
        try:
            r = self._get(f"/posts/{post_id}", params={"context": "edit"}, timeout=10)
            if r.status_code != 200:
                return False
            post = r.json()
            date_tag = datetime.now().strftime("%Y%m%d")
            archive_payload = {
                "title":   f"[BAK {date_tag}] {post.get('title', {}).get('raw', original_slug)}",
                "slug":    f"{original_slug}-bak-{date_tag}",
                "content": post.get("content", {}).get("raw", ""),
                "status":  "draft",
            }
            ar = self._post("/posts", json=archive_payload, timeout=30)
            if ar.status_code == 201:
                logger.info("Archived post '%s' as draft id=%s", original_slug, ar.json()["id"])
                return True
            logger.warning("Archive post draft failed (%s)", ar.status_code)
        except Exception as e:
            logger.warning("Archive post error: %s", e)
        return False

    def upsert_post(self, payload: dict) -> dict | None:
        slug = payload.get("slug", "")
        existing = self._find_post(slug)
        try:
            if existing:
                self._archive_post(existing, slug)
                r = self._post(f"/posts/{existing}", json=payload, timeout=30)
            else:
                r = self._post("/posts", json=payload, timeout=30)
            if r.status_code in (200, 201):
                return r.json()
            logger.error("Post upsert failed (%s): %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.error("Post upsert exception: %s", e)
        return None

    def get_published_posts(self) -> list[dict]:
        """Returns post summaries for all published posts, for rebuilding the blog listing."""
        try:
            r = self._get("/posts", params={"status": "publish", "per_page": 100}, timeout=15)
            if r.status_code == 200:
                posts = r.json()
                summaries = []
                for p in posts:
                    featured_url = ""
                    if p.get("featured_media"):
                        try:
                            mr = self._get(f"/media/{p['featured_media']}", timeout=10)
                            if mr.status_code == 200:
                                featured_url = mr.json().get("source_url", "")
                        except Exception:
                            pass
                    summaries.append({
                        "title": p.get("title", {}).get("rendered", ""),
                        "slug": p.get("slug", ""),
                        "excerpt": p.get("excerpt", {}).get("rendered", "").replace("<p>", "").replace("</p>", "").strip(),
                        "featured_image": {"url": featured_url} if featured_url else None,
                    })
                return summaries
        except Exception as e:
            logger.warning("get_published_posts error: %s", e)
        return []

    # ------------------------------------------------------------------
    # Media upload
    # ------------------------------------------------------------------

    def upload_image(self, image_bytes: bytes, filename: str, mime: str = "image/jpeg") -> dict | None:
        import time
        s, nonce = self._get_session()
        for attempt in range(3):
            try:
                r = s.post(
                    f"{self.base}/media",
                    headers={
                        "X-WP-Nonce": nonce,
                        "Content-Disposition": f'attachment; filename="{filename}"',
                        "Content-Type": mime,
                    },
                    data=image_bytes,
                    timeout=60,
                )
                if r.status_code == 201:
                    data = r.json()
                    return {"id": data["id"], "url": data["source_url"]}
                if r.status_code < 500:
                    logger.error("Media upload failed (%s): %s", r.status_code, r.text[:200])
                    return None
                logger.warning("Media upload %s error, retrying (%d/3)...", r.status_code, attempt + 1)
                time.sleep(6 * (attempt + 1))
            except Exception as e:
                logger.error("Media upload exception: %s", e)
                return None
        return None

    # ------------------------------------------------------------------
    # Page meta (sidebar, etc.)
    # ------------------------------------------------------------------

    def set_page_meta(self, page_id: int, meta: dict) -> bool:
        try:
            r = self._post(f"/pages/{page_id}", json={"meta": meta}, timeout=15)
            return r.status_code in (200, 201)
        except Exception:
            return False

    # ------------------------------------------------------------------
    # Site settings
    # ------------------------------------------------------------------

    def update_site_settings(self, title: str, tagline: str) -> bool:
        try:
            r = self._post("/settings", json={"title": title, "description": tagline}, timeout=15)
            if r.status_code == 200:
                logger.info("Site title updated to: %s", title)
                return True
            logger.error("Site settings update failed (%s): %s", r.status_code, r.text[:200])
        except Exception as e:
            logger.error("Site settings error: %s", e)
        return False

    def set_front_page(self, page_id: int) -> bool:
        """Set a page as the WordPress static front page (shows at root URL)."""
        # Try REST API first
        try:
            r = self._post("/settings", json={
                "show_on_front": "page",
                "page_on_front": page_id,
            }, timeout=15)
            if r.status_code == 200:
                logger.info("Front page set via REST to page id=%s", page_id)
                return True
            logger.warning("set_front_page REST failed (%s), trying admin form...", r.status_code)
        except Exception as e:
            logger.warning("set_front_page REST error: %s, trying admin form...", e)

        # Fallback: POST directly to wp-admin/options.php (always works for admin sessions)
        try:
            s, _ = self._get_session()
            opts_page = s.get(f"{self.site}/wp-admin/options-reading.php", timeout=15)
            m = re.search(r'name="_wpnonce"\s+value="([^"]+)"', opts_page.text)
            if not m:
                logger.error("set_front_page: could not extract nonce from options-reading.php")
                return False
            nonce = m.group(1)
            r2 = s.post(f"{self.site}/wp-admin/options.php", data={
                "_wpnonce": nonce,
                "_wp_http_referer": "/wp-admin/options-reading.php",
                "option_page": "reading",
                "action": "update",
                "show_on_front": "page",
                "page_on_front": str(page_id),
                "page_for_posts": "0",
                "posts_per_page": "10",
                "posts_per_rss": "10",
                "rss_use_excerpt": "0",
                "blog_public": "1",
            }, timeout=15, allow_redirects=True)
            if r2.status_code == 200:
                logger.info("Front page set via admin form to page id=%s", page_id)
                return True
            logger.error("set_front_page admin form failed (%s)", r2.status_code)
        except Exception as e:
            logger.error("set_front_page admin form error: %s", e)
        return False

    # ------------------------------------------------------------------
    # Sidebar layout
    # ------------------------------------------------------------------

    def set_no_sidebar(self, page_id: int):
        self.set_page_meta(page_id, {"_astra-site-sidebar-layout": "no-sidebar"})

    # ------------------------------------------------------------------
    # Nav menu
    # ------------------------------------------------------------------

    def _delete(self, path: str, **kwargs) -> requests.Response:
        s, nonce = self._get_session()
        return s.delete(f"{self.base}{path}", headers={"X-WP-Nonce": nonce}, **kwargs)

    def get_menus(self) -> list:
        try:
            r = self._get("/menus", timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        return []

    def _find_services_parent(self) -> int | None:
        """Find the Services parent page — tries services, services-2 … services-5,
        returning the one that has the most published children."""
        best_id, best_count = None, -1
        for slug in ["services", "services-2", "services-3", "services-4", "services-5"]:
            pid = self._find_page(slug)
            if not pid:
                continue
            try:
                r = self._get("/pages", params={"parent": pid, "status": "publish", "per_page": 100}, timeout=10)
                count = len(r.json()) if r.status_code == 200 else 0
            except Exception:
                count = 0
            logger.info("Slug '%s' → id=%s, children=%s", slug, pid, count)
            if count > best_count:
                best_id, best_count = pid, count
        return best_id

    def get_services_parent_url(self, parent_id: int) -> str:
        """Return the slug of the services parent page (works even when draft)."""
        try:
            r = self._get(f"/pages/{parent_id}", timeout=10)
            if r.status_code == 200:
                return r.json().get("slug", "")
        except Exception:
            pass
        return ""

    def get_service_pages(self) -> list[dict]:
        """Fetch all published child pages under the Services parent page."""
        services_id = self._find_services_parent()
        if not services_id:
            logger.warning("No Services parent page found")
            return []
        try:
            r = self._get("/pages", params={"parent": services_id, "status": "publish", "per_page": 100}, timeout=15)
            if r.status_code == 200:
                pages = r.json()
                logger.info("Found %s service pages under parent id=%s", len(pages), services_id)
                return [{"service": p["title"]["rendered"], "link": p["link"]} for p in pages]
            logger.error("get_service_pages failed: %s", r.status_code)
        except Exception as e:
            logger.error("get_service_pages error: %s", e)
        return []

    def rebuild_full_nav(self, service_results: list[dict]) -> bool:
        """
        Wipes all existing nav items and rebuilds the full nav from scratch:
        Home | Services (dropdown) | Blog | FAQs | Contact Us | Phone
        """
        import re
        try:
            menus = self.get_menus()
            if not menus:
                logger.info("No menu found — creating one...")
                r = self._post("/menus", json={
                    "name": "Primary Menu",
                    "slug": "primary-menu",
                    "locations": ["primary"],
                }, timeout=15)
                if r.status_code == 201:
                    menu_id = r.json()["id"]
                    logger.info("Created menu id=%s", menu_id)
                else:
                    logger.error("Failed to create menu: %s", r.status_code)
                    return False
            else:
                menu_id = menus[0]["id"]

            # Always ensure the menu is assigned to the primary theme location
            self._post(f"/menus/{menu_id}", json={"locations": ["primary"]}, timeout=10)

            # Delete all existing menu items
            r = self._get("/menu-items", params={"menus": menu_id, "per_page": 100}, timeout=15)
            if r.status_code == 200:
                for item in r.json():
                    self._delete(f"/menu-items/{item['id']}", params={"force": True}, timeout=10)

            site = self.site.rstrip("/")
            pd = re.sub(r"\D", "", self.cfg.phone)

            def add(title, url, parent=0, order=1):
                payload = {"title": title, "url": url, "menus": menu_id,
                           "parent": parent, "menu_order": order, "status": "publish"}
                cr = self._post("/menu-items", json=payload, timeout=15)
                if cr.status_code == 201:
                    return cr.json()["id"]
                logger.warning("Nav item failed (%s): %s → %s", cr.status_code, title, url)
                return None

            # Top-level items
            services_page_url = f"{site}/services/"
            if service_results:
                # Use actual deployed services parent URL if available
                first_link = service_results[0].get("link", "")
                # e.g. https://site.com/services-2/concrete-driveways/ → take up to second segment
                parts = first_link.rstrip("/").split("/")
                if len(parts) >= 4:
                    services_page_url = "/".join(parts[:-1]) + "/"

            home_id    = add("Home",       f"{site}/",           order=1)
            svc_id     = add("Services",   services_page_url,    order=2)
            _          = add("Blog",       f"{site}/blog/",      order=3)
            _          = add("FAQs",       f"{site}/faqs/",      order=4)
            _          = add("Contact Us", f"{site}/contact-us/",order=5)
            _          = add(self.cfg.phone, f"tel:{pd}",        order=6)

            # Service page dropdown under Services
            if svc_id:
                for i, svc in enumerate(service_results):
                    add(svc.get("service", ""), svc.get("link", ""), parent=svc_id, order=i + 1)

            logger.info("Nav rebuilt with %d service items", len(service_results))
            return True
        except Exception as e:
            logger.error("Nav rebuild error: %s", e)
            return False

    def update_services_nav(self, service_results: list[dict]) -> bool:
        """
        Rebuilds the Services dropdown in the primary nav menu to match deployed pages.
        service_results: list of {"service": str, "link": str, "id": int}
        """
        try:
            menus = self.get_menus()
            if not menus:
                logger.warning("No menus found — skipping nav update")
                return False

            menu_id = menus[0]["id"]

            r = self._get("/menu-items", params={"menus": menu_id, "per_page": 100}, timeout=15)
            if r.status_code != 200:
                logger.error("Could not fetch menu items: %s", r.status_code)
                return False
            items = r.json()

            # Find the "Services" parent menu item
            services_item_id = None
            for item in items:
                title = (item.get("title") or {}).get("rendered", "").strip().lower()
                url = item.get("url", "").lower()
                if title == "services" or "/services" in url:
                    services_item_id = item["id"]
                    break

            if not services_item_id:
                logger.warning("No 'Services' menu item found — skipping nav update")
                return False

            # Collect direct children of Services and their children (grandchildren)
            child_ids = {item["id"] for item in items if item.get("parent") == services_item_id}
            grandchild_ids = {item["id"] for item in items if item.get("parent") in child_ids}
            to_delete = child_ids | grandchild_ids
            for item in items:
                if item["id"] in to_delete:
                    self._delete(f"/menu-items/{item['id']}", params={"force": True}, timeout=10)
                    logger.info("Removed nav item: %s", (item.get("title") or {}).get("rendered", "?"))

            # Add new children
            for i, svc in enumerate(service_results):
                new_item = {
                    "title": svc.get("service", ""),
                    "url": svc.get("link", ""),
                    "menus": menu_id,
                    "parent": services_item_id,
                    "menu_order": i + 1,
                    "status": "publish",
                }
                cr = self._post("/menu-items", json=new_item, timeout=15)
                if cr.status_code == 201:
                    logger.info("Added nav item: %s → %s", svc.get("service"), svc.get("link"))
                else:
                    logger.warning("Nav item creation failed (%s): %s", cr.status_code, cr.text[:100])

            return True
        except Exception as e:
            logger.error("Nav menu update error: %s", e)
            return False

    def install_contact_plugin(self, contact_email: str = "") -> bool:
        """
        Packages rr-contact-handler.php as a ZIP and installs it.
        Primary path: WP REST /plugins (WP 5.5+, PUT to activate).
        Fallback: admin form upload via update.php (works on all hosts).
        """
        import zipfile, io, os, re as _re

        plugin_src = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "plugins", "rr-contact-handler.php"
        )
        with open(plugin_src, "rb") as f:
            php_bytes = f.read()

        def _make_zip() -> io.BytesIO:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr("rr-contact-handler/rr-contact-handler.php", php_bytes)
            buf.seek(0)
            return buf

        try:
            s, nonce = self._get_session()

            # ── Path 1: REST API ──────────────────────────────────────────
            rest_ok = False
            rest_r = self._get("/plugins", timeout=15)
            if rest_r.status_code == 200:
                # Remove old version
                for p in rest_r.json():
                    if p.get("plugin", "").startswith("rr-contact-handler"):
                        self._delete(
                            "/plugins/rr-contact-handler/rr-contact-handler",
                            params={"force": True}, timeout=15
                        )
                        break

                upload = s.post(
                    f"{self.base}/plugins",
                    headers={"X-WP-Nonce": nonce},
                    files={"pluginzip": ("rr-contact-handler.zip", _make_zip(), "application/zip")},
                    timeout=30,
                )
                if upload.status_code in (200, 201):
                    plugin_slug = upload.json().get("plugin", "rr-contact-handler/rr-contact-handler")
                    # PUT (not POST) to change status
                    act = s.put(
                        f"{self.base}/plugins/{plugin_slug}",
                        headers={"X-WP-Nonce": nonce, "Content-Type": "application/json"},
                        json={"status": "active"},
                        timeout=15,
                    )
                    rest_ok = act.status_code in (200, 201)
                    if not rest_ok:
                        logger.warning("REST activation failed (%s), trying admin fallback", act.status_code)
                else:
                    logger.warning("REST upload failed (%s): %s — trying admin fallback",
                                   upload.status_code, upload.text[:120])
            else:
                logger.warning("REST /plugins not available (%s) — using admin fallback", rest_r.status_code)

            # ── Path 2: Admin form upload (universal fallback) ────────────
            if not rest_ok:
                upload_page = s.get(
                    f"{self.site}/wp-admin/plugin-install.php",
                    params={"tab": "upload"}, timeout=15
                )
                m = _re.search(r'name="_wpnonce"\s+value="([^"]+)"', upload_page.text)
                if not m:
                    logger.error("Could not find nonce on plugin upload page")
                    return False
                upload_nonce = m.group(1)

                resp = s.post(
                    f"{self.site}/wp-admin/update.php",
                    params={"action": "upload-plugin"},
                    data={"_wpnonce": upload_nonce, "_wp_http_referer": "/wp-admin/plugin-install.php?tab=upload"},
                    files={"pluginzip": ("rr-contact-handler.zip", _make_zip(), "application/zip")},
                    timeout=30,
                )
                if resp.status_code != 200 or "Plugin installed successfully" not in resp.text and "activate-now" not in resp.text:
                    logger.error("Admin plugin upload failed (%s): %s", resp.status_code, resp.text[:200])
                    return False

                # Extract activate URL from response
                act_m = _re.search(r'href="([^"]*action=activate[^"]*)"', resp.text)
                if act_m:
                    act_url = act_m.group(1).replace("&amp;", "&")
                    s.get(f"{self.site}/wp-admin/{act_url}" if not act_url.startswith("http") else act_url,
                          timeout=15)
                else:
                    # Activate by constructing the URL directly
                    activate_nonce_page = s.get(f"{self.site}/wp-admin/plugins.php", timeout=15)
                    an = _re.search(
                        r'action=activate[^"]*plugin=rr-contact-handler[^"]*&[^"]*_wpnonce=([^"&]+)',
                        activate_nonce_page.text
                    )
                    if an:
                        s.get(
                            f"{self.site}/wp-admin/plugins.php",
                            params={"action": "activate",
                                    "plugin": "rr-contact-handler/rr-contact-handler.php",
                                    "_wpnonce": an.group(1)},
                            timeout=15
                        )

            # Store contact email
            if contact_email:
                self._post("/settings", json={"rr_contact_email": contact_email}, timeout=10)

            logger.info("rr-contact-handler installed and activated")
            return True

        except Exception as e:
            logger.error("install_contact_plugin error: %s", e)
            return False

    def install_smtp_plugin(self, cfg) -> bool:
        """
        Downloads WP Mail SMTP from wp.org, installs + activates it via admin form,
        then writes the SMTP settings via the rr_set_option ajax endpoint.
        """
        import io, re as _re, json as _json
        try:
            import requests as _req
            logger.info("Downloading WP Mail SMTP...")
            dl = _req.get(
                "https://downloads.wordpress.org/plugin/wp-mail-smtp.latest-stable.zip",
                timeout=60, stream=True
            )
            if dl.status_code != 200:
                logger.error("WP Mail SMTP download failed (%s)", dl.status_code)
                return False
            zip_bytes = dl.content

            s, nonce = self._get_session()

            # Remove old version if present
            existing = self._get("/plugins", timeout=15)
            if existing.status_code == 200:
                for p in existing.json():
                    if p.get("plugin", "").startswith("wp-mail-smtp"):
                        self._delete(
                            f"/plugins/{p['plugin'].replace('/', '%2F')}",
                            params={"force": True}, timeout=15
                        )
                        break

            # Try REST upload first
            rest_ok = False
            upload = s.post(
                f"{self.base}/plugins",
                headers={"X-WP-Nonce": nonce},
                files={"pluginzip": ("wp-mail-smtp.zip", io.BytesIO(zip_bytes), "application/zip")},
                timeout=60,
            )
            if upload.status_code in (200, 201):
                slug = upload.json().get("plugin", "wp-mail-smtp/wp_mail_smtp")
                act = s.put(
                    f"{self.base}/plugins/{slug}",
                    headers={"X-WP-Nonce": nonce, "Content-Type": "application/json"},
                    json={"status": "active"}, timeout=15,
                )
                rest_ok = act.status_code in (200, 201)

            # Admin form fallback
            if not rest_ok:
                up_page = s.get(f"{self.site}/wp-admin/plugin-install.php",
                                params={"tab": "upload"}, timeout=15)
                m = _re.search(r'name="_wpnonce"\s+value="([^"]+)"', up_page.text)
                if not m:
                    logger.error("Could not get upload nonce for WP Mail SMTP")
                    return False
                resp = s.post(
                    f"{self.site}/wp-admin/update.php",
                    params={"action": "upload-plugin"},
                    data={"_wpnonce": m.group(1),
                          "_wp_http_referer": "/wp-admin/plugin-install.php?tab=upload"},
                    files={"pluginzip": ("wp-mail-smtp.zip", io.BytesIO(zip_bytes), "application/zip")},
                    timeout=60,
                )
                if resp.status_code != 200:
                    logger.error("WP Mail SMTP admin upload failed (%s)", resp.status_code)
                    return False
                act_m = _re.search(r'href="([^"]*action=activate[^"]*wp-mail-smtp[^"]*)"', resp.text)
                if act_m:
                    act_url = act_m.group(1).replace("&amp;", "&")
                    s.get(act_url if act_url.startswith("http") else f"{self.site}/wp-admin/{act_url}",
                          timeout=15)
                else:
                    plugins_page = s.get(f"{self.site}/wp-admin/plugins.php", timeout=15)
                    an = _re.search(
                        r'action=activate[^"]*plugin=wp-mail-smtp[^"]*_wpnonce=([^"&]+)',
                        plugins_page.text
                    )
                    if an:
                        s.get(f"{self.site}/wp-admin/plugins.php",
                              params={"action": "activate",
                                      "plugin": "wp-mail-smtp/wp_mail_smtp.php",
                                      "_wpnonce": an.group(1)},
                              timeout=15)

            # Write SMTP settings via WP Mail SMTP's own admin form so the
            # password gets encrypted by the plugin (rr_set_option writes
            # plaintext which the plugin then fails to decrypt).
            # Small pause to let the plugin finish initialising after activation.
            import time as _time
            _time.sleep(10)

            from_email = cfg.smtp_from_email or cfg.contact_email
            from_name  = cfg.smtp_from_name  or cfg.business_name

            # Use a fresh session for the SMTP form POST — the long-lived deploy
            # session can accumulate stale state that causes the password save to
            # silently fail even when the response says "successfully saved".
            import requests as _requests
            smtp_s = _requests.Session()
            smtp_s.get(f"{self.site}/wp-login.php", timeout=15)
            smtp_s.post(f"{self.site}/wp-login.php", data={
                "log":         self.cfg.wp_username,
                "pwd":         self.cfg.wp_password,
                "wp-submit":   "Log In",
                "redirect_to": f"{self.site}/wp-admin/",
                "testcookie":  "1",
            }, allow_redirects=True, timeout=20)

            settings_page = smtp_s.get(
                f"{self.site}/wp-admin/admin.php",
                params={"page": "wp-mail-smtp"},
                timeout=15,
            )
            form_nonce_m = _re.search(
                r'name="_wpnonce"\s+value="([^"]+)"', settings_page.text
            )
            if not form_nonce_m:
                logger.warning("Could not get WP Mail SMTP form nonce; SMTP password may not save correctly")
            else:
                form_data = {
                    "_wpnonce":                             form_nonce_m.group(1),
                    "_wp_http_referer":                     "/wp-admin/admin.php?page=wp-mail-smtp",
                    "wp-mail-smtp-post":                    "1",
                    "wp-mail-smtp[mail][from_email]":       from_email,
                    "wp-mail-smtp[mail][from_name]":        from_name,
                    "wp-mail-smtp[mail][from_email_force]": "1",
                    "wp-mail-smtp[mail][from_name_force]":  "1",
                    "wp-mail-smtp[mail][return_path]":      "0",
                    "wp-mail-smtp[mail][mailer]":           "smtp",
                    "wp-mail-smtp[smtp][host]":             cfg.smtp_host,
                    "wp-mail-smtp[smtp][encryption]":       cfg.smtp_encryption,
                    "wp-mail-smtp[smtp][port]":             str(cfg.smtp_port),
                    "wp-mail-smtp[smtp][auth]":             "1",
                    "wp-mail-smtp[smtp][user]":             cfg.smtp_username,
                    "wp-mail-smtp[smtp][pass]":             cfg.smtp_password.replace(" ", ""),
                    "submit":                               "Save Settings",
                }
                r = smtp_s.post(
                    f"{self.site}/wp-admin/admin.php",
                    params={"page": "wp-mail-smtp"},
                    data=form_data,
                    timeout=15,
                )
                if r.status_code not in (200, 302):
                    logger.warning("WP Mail SMTP form save returned %s", r.status_code)
                elif "successfully saved" in r.text.lower():
                    logger.info("WP Mail SMTP settings saved and password encrypted OK")
                else:
                    logger.warning("WP Mail SMTP form posted but 'successfully saved' not in response — password may not have saved")

            logger.info("WP Mail SMTP installed and configured (host=%s)", cfg.smtp_host)
            return True

        except Exception as e:
            logger.error("install_smtp_plugin error: %s", e)
            return False

    def reset_site(self, log=None) -> dict:
        """
        Nuclear reset: deletes all pages, posts, and media attachments,
        clears additional CSS, and removes the RR contact plugin.
        Returns counts of deleted items.
        """
        def _log(msg):
            if log:
                log(msg)

        counts = {"pages": 0, "posts": 0, "media": 0, "errors": 0}

        # Delete all pages
        _log("🗑️  Deleting pages...")
        try:
            r = self._get("/pages", params={"per_page": 100, "status": "any"}, timeout=20)
            if r.status_code == 200:
                for page in r.json():
                    dr = self._delete(f"/pages/{page['id']}", params={"force": True}, timeout=15)
                    if dr.status_code == 200:
                        counts["pages"] += 1
                    else:
                        counts["errors"] += 1
                _log(f"  ✅ Deleted {counts['pages']} pages")
        except Exception as e:
            _log(f"  ❌ Pages error: {e}")
            counts["errors"] += 1

        # Delete all posts
        _log("🗑️  Deleting posts...")
        try:
            r = self._get("/posts", params={"per_page": 100, "status": "any"}, timeout=20)
            if r.status_code == 200:
                for post in r.json():
                    dr = self._delete(f"/posts/{post['id']}", params={"force": True}, timeout=15)
                    if dr.status_code == 200:
                        counts["posts"] += 1
                    else:
                        counts["errors"] += 1
                _log(f"  ✅ Deleted {counts['posts']} posts")
        except Exception as e:
            _log(f"  ❌ Posts error: {e}")
            counts["errors"] += 1

        # Delete all media
        _log("🗑️  Deleting media...")
        try:
            r = self._get("/media", params={"per_page": 100}, timeout=20)
            if r.status_code == 200:
                for item in r.json():
                    dr = self._delete(f"/media/{item['id']}", params={"force": True}, timeout=15)
                    if dr.status_code == 200:
                        counts["media"] += 1
                    else:
                        counts["errors"] += 1
                _log(f"  ✅ Deleted {counts['media']} media items")
        except Exception as e:
            _log(f"  ❌ Media error: {e}")
            counts["errors"] += 1

        # Clear additional CSS
        _log("🧹 Clearing additional CSS...")
        try:
            s, _ = self._get_session()
            theme_slug = "astra"
            r = self._get("/themes?status=active", timeout=10)
            if r.status_code == 200 and r.json():
                theme_slug = r.json()[0].get("stylesheet", "astra")

            cp = s.get(f"{self.site}/wp-admin/customize.php", timeout=20)
            m = re.search(r'"save"\s*:\s*"([a-f0-9]+)"', cp.text)
            if m:
                s.post(f"{self.site}/wp-admin/admin-ajax.php", data={
                    "action": "customize_save",
                    "nonce": m.group(1),
                    "wp_customize": "on",
                    "theme": theme_slug,
                    "customized": json.dumps({f"custom_css[{theme_slug}]": ""}),
                }, timeout=20)
                _log("  ✅ CSS cleared")
        except Exception as e:
            _log(f"  ⚠️  CSS clear error: {e}")

        # Remove RR contact plugin
        _log("🔌 Removing contact plugin...")
        try:
            r = self._get("/plugins", timeout=15)
            if r.status_code == 200:
                for p in r.json():
                    if p.get("plugin", "").startswith("rr-contact-handler"):
                        slug = p["plugin"]
                        # Deactivate first
                        self._post(f"/plugins/{slug}", json={"status": "inactive"}, timeout=15)
                        self._delete(f"/plugins/{slug}", params={"force": True}, timeout=15)
                        _log("  ✅ Contact plugin removed")
                        break
        except Exception as e:
            _log(f"  ⚠️  Plugin removal error: {e}")

        # Clear nav menu items
        _log("🗑️  Clearing nav menu...")
        try:
            r = self._get("/menu-items", params={"per_page": 100}, timeout=15)
            if r.status_code == 200:
                removed = 0
                for item in r.json():
                    self._delete(f"/menu-items/{item['id']}", params={"force": True}, timeout=10)
                    removed += 1
                if removed:
                    _log(f"  ✅ Cleared {removed} nav items")
        except Exception as e:
            _log(f"  ⚠️  Nav clear error: {e}")

        return counts

    def delete_default_pages(self) -> None:
        """Permanently delete WordPress default pages that ship with every install."""
        for slug in ("sample-page", "privacy-policy"):
            pid = self._find_page(slug)
            if pid:
                r = self._delete(f"/pages/{pid}", params={"force": True}, timeout=15)
                if r.status_code == 200:
                    logger.info("Deleted default page: %s", slug)
                else:
                    logger.warning("Could not delete %s (%s)", slug, r.status_code)

    def set_additional_css(self, css: str) -> bool:
        """
        Injects CSS into WordPress's Additional CSS (Customizer) via admin-ajax.
        Appends to any existing custom CSS so prior rules are preserved.
        """
        import uuid as _uuid

        try:
            s, _ = self._get_session()

            # Determine active theme slug
            theme_slug = "astra"
            r = self._get("/themes?status=active", timeout=10)
            if r.status_code == 200 and r.json():
                theme_slug = r.json()[0].get("stylesheet", "astra")

            # Get the Customizer save nonce from the customize page
            cp = s.get(f"{self.site}/wp-admin/customize.php", timeout=20)
            nonce = ""
            m = re.search(r'"save"\s*:\s*"([a-f0-9]+)"', cp.text)
            if m:
                nonce = m.group(1)
            else:
                m = re.search(r'wp_create_nonce\(["\']save-customize_[^"\']+["\']\)[^;]*=\s*["\']([a-f0-9]+)["\']', cp.text)
                if m:
                    nonce = m.group(1)

            if not nonce:
                logger.warning("set_additional_css: could not extract customizer nonce")
                return False

            existing_uuid = ""
            m = re.search(r'"changeset"\s*:\s*\{\s*"uuid"\s*:\s*"([0-9a-f-]+)"', cp.text)
            if m:
                existing_uuid = m.group(1)
            changeset_uuid = existing_uuid or str(_uuid.uuid4())

            # Fetch any existing custom CSS so we append rather than overwrite
            existing = ""
            css_r = s.get(
                f"{self.site}/wp-json/wp/v2/custom_css",
                params={"slug": theme_slug},
                headers={"X-WP-Nonce": self._nonce},
                timeout=10,
            )
            if css_r.status_code == 200 and css_r.json():
                existing = css_r.json()[0].get("content", {})
                if isinstance(existing, dict):
                    existing = existing.get("raw", "")

            combined = (existing.strip() + "\n\n" + css).strip() if existing.strip() else css

            payload = {
                "action": "customize_save",
                "nonce": nonce,
                "wp_customize": "on",
                "theme": theme_slug,
                "customize_changeset_uuid": changeset_uuid,
                "customize_changeset_status": "publish",
                "customized": json.dumps({f"custom_css[{theme_slug}]": combined}),
            }
            save_r = s.post(f"{self.site}/wp-admin/admin-ajax.php", data=payload, timeout=20)
            if save_r.status_code == 200:
                try:
                    body = save_r.json()
                    if body.get("success"):
                        logger.info("Additional CSS saved via Customizer")
                        return True
                    logger.warning("Customizer save response: %s", body)
                except Exception:
                    pass
            logger.error("set_additional_css: save returned %s", save_r.status_code)
            return False

        except Exception as e:
            logger.error("set_additional_css error: %s", e)
            return False

    def set_rich_footer(self, cfg) -> bool:
        import re as _re, json as _json
        def _slugify(t):
            t = t.lower().strip()
            t = _re.sub(r"[^\w\s-]", "", t)
            t = _re.sub(r"[\s_]+", "-", t)
            return _re.sub(r"-+", "-", t)

        city_slug = _slugify(cfg.city)
        services = [
            {"name": svc, "slug": f"{_slugify(svc)}-{city_slug}"}
            for svc in cfg.services
        ]
        footer_cfg = {
            "enabled":       True,
            "business_name": cfg.business_name,
            "city":          cfg.city,
            "state":         cfg.state,
            "phone":         cfg.phone,
            "primary_color": cfg.primary_color,
            "dark_color":    cfg.dark_color,
            "services":      services,
        }
        try:
            s, nonce = self._get_session()
            r = s.post(
                f"{self.site}/wp-admin/admin-ajax.php",
                data={
                    "action":       "rr_set_option",
                    "option_key":   "rr_footer_config",
                    "option_value": _json.dumps(footer_cfg),
                    "_wpnonce":     nonce,
                },
                timeout=15,
            )
            return r.status_code == 200 and r.json().get("success")
        except Exception as e:
            logger.error("set_rich_footer: %s", e)
            return False

    def set_footer_copyright(
        self,
        text: str,
        bg_color: str | None = None,
        text_color: str | None = None,
        align: str = "left",
    ) -> bool:
        """
        Sets Astra's footer copyright text, background color, text color, and
        alignment via the Customizer — all in one changeset. Astra supports
        dynamic tags like [current_year] inside the text. Replacing the whole
        text field with custom text — rather than appending to the default —
        also removes the "Powered by Astra" credit, since that credit only
        appears via the [theme_author] tag in Astra's *default* copyright text.

        bg_color/text_color are typically cfg.dark_color / "#ffffff" so the
        footer bar blends with the site's brand instead of sitting on a bare
        white strip with default dark-gray text.

        Things that aren't obvious and will silently no-op if missed:
        1. The actual customizer setting IDs are nested inside one combined
           `astra-settings` option, not standalone theme_mods — e.g. the text
           field's real ID is `astra-settings[footer-copyright-editor]`, the
           background is `astra-settings[footer-bg-obj-responsive]` (a full
           responsive background object: desktop/tablet/mobile, each with
           background-color/image/repeat/position/size/attachment/overlay-*
           keys — sending a bare hex string for this one is rejected).
        2. customize_save without a changeset UUID + status=publish only saves
           an auto-draft revision — it never reaches the live site.
        """
        import uuid as _uuid

        try:
            s, _ = self._get_session()

            theme_slug = "astra"
            r = self._get("/themes?status=active", timeout=10)
            if r.status_code == 200 and r.json():
                theme_slug = r.json()[0].get("stylesheet", "astra")

            cp = s.get(f"{self.site}/wp-admin/customize.php", timeout=20)
            nonce = ""
            m = re.search(r'"save"\s*:\s*"([a-f0-9]+)"', cp.text)
            if m:
                nonce = m.group(1)
            else:
                m = re.search(r'wp_create_nonce\(["\']save-customize_[^"\']+["\']\)[^;]*=\s*["\']([a-f0-9]+)["\']', cp.text)
                if m:
                    nonce = m.group(1)

            if not nonce:
                logger.warning("set_footer_copyright: could not extract customizer nonce")
                return False

            existing_uuid = ""
            m = re.search(r'"changeset"\s*:\s*\{\s*"uuid"\s*:\s*"([0-9a-f-]+)"', cp.text)
            if m:
                existing_uuid = m.group(1)
            changeset_uuid = existing_uuid or str(_uuid.uuid4())

            customized = {"astra-settings[footer-copyright-editor]": text}
            if align:
                customized["astra-settings[footer-copyright-alignment]"] = align
            if text_color:
                customized["astra-settings[footer-copyright-color]"] = text_color
            if bg_color:
                empty_bp = {
                    "background-color": "", "background-image": "", "background-repeat": "repeat",
                    "background-position": "center center", "background-size": "auto",
                    "background-attachment": "scroll", "overlay-type": "", "overlay-color": "",
                    "overlay-opacity": "", "overlay-gradient": "",
                }
                desktop_bp = dict(empty_bp, **{"background-color": bg_color})
                # NOT "footer-bg-obj-responsive" — that setting exists but doesn't
                # target the row the copyright text actually lives in
                # (.site-below-footer-wrap). The real key is the "hbb-" (below-
                # footer-builder) prefixed one. Confirmed by inspecting which DOM
                # element's background actually changed after each candidate.
                customized["astra-settings[hbb-footer-bg-obj-responsive]"] = {
                    "desktop": desktop_bp, "tablet": dict(empty_bp), "mobile": dict(empty_bp),
                }

            payload = {
                "action": "customize_save",
                "nonce": nonce,
                "wp_customize": "on",
                "theme": theme_slug,
                "customize_changeset_uuid": changeset_uuid,
                "customize_changeset_status": "publish",
                "customized": json.dumps(customized),
            }
            save_r = s.post(f"{self.site}/wp-admin/admin-ajax.php", data=payload, timeout=20)
            if save_r.status_code == 200:
                try:
                    body = save_r.json()
                    if body.get("success"):
                        logger.info("Footer copyright text/style saved via Customizer")
                        return True
                    logger.warning("Customizer save response: %s", body)
                except Exception:
                    pass
            logger.error("set_footer_copyright: save returned %s", save_r.status_code)
            return False

        except Exception as e:
            logger.error("set_footer_copyright error: %s", e)
            return False
