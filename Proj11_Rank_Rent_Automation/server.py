"""
server.py — Local Flask server for the Rank & Rent Deployer UI.

Usage:
    pip install -r requirements.txt
    python server.py
    Open http://localhost:5000 in your browser.
"""
import os
import sys
import json
import queue
import threading
import logging
from flask import Flask, request, Response, send_file, jsonify
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), override=True)

# Allow imports from package root
sys.path.insert(0, os.path.dirname(__file__))

from src.config import DeployConfig, DEFAULT_SERVICES, DEFAULT_BLOG_TOPICS
from src.deployer import deploy
from src import history as hist

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

app = Flask(__name__)
PORT = int(os.getenv("FLASK_PORT", 5000))

# Global cancel flag — set via POST /cancel to stop any running operation
_cancel_event = threading.Event()


@app.route("/cancel", methods=["POST"])
def cancel_operation():
    _cancel_event.set()
    return jsonify({"ok": True, "message": "Cancel signal sent."})


def _make_log(log_queue: queue.Queue):
    """Returns a log() function that checks the cancel flag on every call."""
    def log(msg: str):
        if _cancel_event.is_set():
            raise InterruptedError("Operation cancelled by user.")
        log_queue.put(msg)
    return log


@app.route("/")
def index():
    return send_file("index.html")


@app.route("/services")
def services():
    return jsonify(DEFAULT_SERVICES)


@app.route("/deploy", methods=["POST"])
def run_deploy():
    data = request.get_json(force=True)

    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", "").strip(),
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        phone=data.get("phone", "").strip(),
        primary_color=data.get("primary_color", "#ff5e14").strip(),
        dark_color=data.get("dark_color", "#1a1a1a").strip(),
        services=data.get("services", DEFAULT_SERVICES),
        blog_topics=data.get("blog_topics", DEFAULT_BLOG_TOPICS),
        gemini_api_key=data.get("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", ""),
        pexels_api_key=data.get("pexels_api_key", "").strip() or os.getenv("PEXELS_API_KEY", ""),
        maps_embed_url=data.get("maps_embed_url", "").strip(),
        contact_email=data.get("contact_email", "").strip(),
        smtp_host=data.get("smtp_host", "").strip(),
        smtp_port=int(data.get("smtp_port") or 587),
        smtp_encryption=data.get("smtp_encryption", "tls").strip(),
        smtp_username=data.get("smtp_username", "").strip(),
        smtp_password=data.get("smtp_password", "").strip(),
        smtp_from_name=data.get("smtp_from_name", "").strip(),
        smtp_from_email=data.get("smtp_from_email", "").strip(),
        rich_footer=bool(data.get("rich_footer", False)),
    )

    errors = cfg.validate()
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    log_queue: queue.Queue = queue.Queue()

    def streamer():
        for line in iter(log_queue.get, None):
            yield f"data: {json.dumps(line)}\n\n"

    cfg_dict = data  # keep raw dict for history

    def runner():
        _cancel_event.clear()
        log = _make_log(log_queue)
        try:
            summary = deploy(cfg, log=log)
            record_id = hist.save_deployment(cfg_dict, summary["published_urls"], summary["failed"])
            log(f"\n🎉 Deployment complete! {len(summary['success'])} succeeded, {len(summary['failed'])} failed.")
            log(f"__RECORD_ID__:{record_id}")
        except InterruptedError:
            log_queue.put("⛔ Deployment cancelled.")
        except Exception as e:
            log_queue.put(f"\n💥 Fatal error: {e}")
        finally:
            log_queue.put(None)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    return Response(streamer(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/reset", methods=["POST"])
def reset_site():
    data = request.get_json(force=True)
    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", ""),
        city=data.get("city", ""),
        state=data.get("state", ""),
        phone=data.get("phone", ""),
        primary_color=data.get("primary_color", "#ff5e14"),
    )
    errors = cfg.validate()
    if errors:
        return jsonify({"ok": False, "errors": errors}), 400

    log_queue: queue.Queue = queue.Queue()

    def streamer():
        for line in iter(log_queue.get, None):
            yield f"data: {json.dumps(line)}\n\n"

    def runner():
        _cancel_event.clear()
        log = _make_log(log_queue)
        try:
            from src.wp_client import WPClient
            wp = WPClient(cfg)
            if not wp.test_connection():
                log("❌ Could not connect to WordPress — check credentials.")
                return
            log("🚨 Starting site reset...")
            counts = wp.reset_site(log=log)
            log(f"\n✅ Reset complete — {counts['pages']} pages, {counts['posts']} posts, {counts['media']} media deleted.")
            if counts["errors"]:
                log(f"⚠️  {counts['errors']} item(s) could not be deleted.")
        except InterruptedError:
            log_queue.put("⛔ Reset cancelled.")
        except Exception as e:
            log_queue.put(f"\n💥 Reset error: {e}")
        finally:
            log_queue.put(None)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return Response(streamer(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/interlink/suggest", methods=["POST"])
def interlink_suggest():
    """
    Accepts published_urls + WP credentials, fetches homepage + service page snippets,
    asks Gemini for 5 external keyword suggestions, returns them as a JSON list.
    """
    data = request.get_json(force=True)
    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", "").strip(),
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        phone=data.get("phone", "").strip(),
        primary_color=data.get("primary_color", "#ff5e14"),
        services=data.get("services", DEFAULT_SERVICES),
        gemini_api_key=data.get("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", ""),
    )
    published_urls = data.get("published_urls", [])
    suggest_count = max(1, min(20, int(data.get("count", 5))))

    try:
        from src.wp_client import WPClient
        from src.interlinker import fetch_page_rendered, suggest_external_keywords, build_internal_url_map
        wp = WPClient(cfg)

        snippets = []
        # Use rendered HTML (not raw block markup) — rendered is compact paragraph text
        home_html = fetch_page_rendered(wp, "home")
        if home_html:
            snippets.append(home_html)

        # Use published_urls if provided, otherwise discover service pages from WP
        svc_items = [i for i in published_urls if i.get("type") == "page"
                     and i.get("label") not in ("Home", "Services Hub", "Blog", "FAQs", "Contact Us", "Services")]
        if not svc_items:
            svc_pages = wp.get_service_pages()
            svc_items = [{"url": p["link"], "label": p["service"], "type": "page"} for p in svc_pages]

        for item in svc_items:
            slug = item["url"].rstrip("/").split("/")[-1]
            svc_html = fetch_page_rendered(wp, slug)
            if svc_html:
                snippets.append(svc_html)
            if len(snippets) >= 4:
                break

        # Build internal keyword list so Gemini doesn't suggest the same terms
        internal_map = build_internal_url_map(published_urls, cfg.services)
        exclude = list(internal_map.keys())

        keywords = suggest_external_keywords(cfg, snippets, count=suggest_count, exclude_keywords=exclude)
        return jsonify({"ok": True, "keywords": keywords})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/interlink/apply", methods=["POST"])
def interlink_apply():
    """
    Applies internal (auto) and external (user-provided) links to homepage
    and all service child pages.

    Body:
    {
      wp_url, wp_username, wp_password, business_name, city, state, phone,
      primary_color, services,
      published_urls: [...],           # from deploy summary
      external_links: {keyword: url}  # user-provided, may be empty
    }
    """
    data = request.get_json(force=True)
    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", "").strip(),
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        phone=data.get("phone", "").strip(),
        primary_color=data.get("primary_color", "#ff5e14"),
        services=data.get("services", DEFAULT_SERVICES),
        gemini_api_key=data.get("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", ""),
    )
    published_urls = data.get("published_urls", [])
    external_links: dict = data.get("external_links", {})

    log_queue: queue.Queue = queue.Queue()

    def streamer():
        for line in iter(log_queue.get, None):
            yield f"data: {json.dumps(line)}\n\n"

    def runner():
        _cancel_event.clear()
        log = _make_log(log_queue)
        try:
            from src.wp_client import WPClient
            from src.interlinker import inject_links, fetch_page_html, fetch_post_html
            wp = WPClient(cfg)

            # External links only — internal links are handled automatically during deployment
            all_links = {k: v for k, v in external_links.items() if v}
            new_tab_urls = set(all_links.values())
            if not all_links:
                log("⚠️  No external links provided. Add keyword → URL pairs and try again.")
                return
            log(f"🔗 Applying {len(all_links)} external links...")

            # Apply to all published pages and posts
            target_slugs = []
            post_slugs = []
            if published_urls:
                for item in published_urls:
                    slug = item["url"].rstrip("/").split("/")[-1]
                    if not slug:
                        continue
                    if item.get("type") == "post":
                        post_slugs.append(slug)
                    else:
                        target_slugs.append(slug)
            else:
                # Fallback: discover from WP
                target_slugs.append("home")
                for p in wp.get_service_pages():
                    target_slugs.append(p["link"].rstrip("/").split("/")[-1])

            updated = 0
            for slug in target_slugs:
                page_id, html = fetch_page_html(wp, slug)
                if not page_id or not html:
                    log(f"  ⚠️  Could not fetch: {slug}")
                    continue
                new_html = inject_links(html, all_links, new_tab_urls=new_tab_urls)
                if new_html == html:
                    log(f"  — No matches: {slug}")
                    continue
                r = wp._post(f"/pages/{page_id}", json={"content": new_html}, timeout=20)
                if r.status_code in (200, 201):
                    log(f"  ✅ Linked: {slug}")
                    updated += 1
                else:
                    log(f"  ❌ Update failed ({r.status_code}): {slug}")

            for slug in post_slugs:
                post_id, html = fetch_post_html(wp, slug)
                if not post_id or not html:
                    log(f"  ⚠️  Could not fetch post: {slug}")
                    continue
                new_html = inject_links(html, all_links, new_tab_urls=new_tab_urls)
                if new_html == html:
                    log(f"  — No matches: {slug}")
                    continue
                r = wp._post(f"/posts/{post_id}", json={"content": new_html}, timeout=20)
                if r.status_code in (200, 201):
                    log(f"  ✅ Linked post: {slug}")
                    updated += 1
                else:
                    log(f"  ❌ Update failed ({r.status_code}): {slug}")

            log(f"\n🔗 Interlinking complete — {updated}/{len(target_slugs)} pages updated.")
        except InterruptedError:
            log_queue.put("⛔ Interlinking cancelled.")
        except Exception as e:
            log_queue.put(f"\n💥 Interlink error: {e}")
        finally:
            log_queue.put(None)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return Response(streamer(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.route("/update-nav", methods=["POST"])
def update_nav():
    data = request.get_json(force=True)
    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", ""),
        city=data.get("city", ""),
        state=data.get("state", ""),
        phone=data.get("phone", ""),
        primary_color=data.get("primary_color", "#ff5e14"),
    )
    from src.wp_client import WPClient
    wp = WPClient(cfg)
    if not wp.test_connection():
        return jsonify({"ok": False, "error": "WP connection failed — check credentials"}), 400
    pages = wp.get_service_pages()
    if not pages:
        return jsonify({"ok": False, "error": "No service pages found — deploy service pages first"}), 400
    success = wp.rebuild_full_nav(pages)
    return jsonify({"ok": success, "updated": len(pages), "pages": [p["service"] for p in pages]})


@app.route("/history", methods=["GET"])
def get_history():
    return jsonify(hist.list_deployments())


@app.route("/history/<record_id>", methods=["GET"])
def get_record(record_id):
    record = hist.get_deployment(record_id)
    if not record:
        return jsonify({"error": "Not found"}), 404
    return jsonify(record)


@app.route("/history/<record_id>", methods=["DELETE"])
def delete_record(record_id):
    hist.delete_deployment(record_id)
    return jsonify({"ok": True})


@app.route("/cache/clear", methods=["POST"])
def clear_cache():
    data = request.get_json(force=True)
    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", "").strip(),
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        phone=data.get("phone", "").strip(),
        primary_color=data.get("primary_color", "#ff5e14").strip(),
    )
    from src.content_cache import clear
    cleared = clear(cfg)
    return jsonify({"ok": True, "cleared": cleared})


@app.route("/retry", methods=["POST"])
def retry_failed():
    data = request.get_json(force=True)

    cfg = DeployConfig(
        wp_url=data.get("wp_url", "").strip().rstrip("/"),
        wp_username=data.get("wp_username", "").strip(),
        wp_password=data.get("wp_password", "").strip(),
        business_name=data.get("business_name", "").strip(),
        city=data.get("city", "").strip(),
        state=data.get("state", "").strip(),
        phone=data.get("phone", "").strip(),
        primary_color=data.get("primary_color", "#ff5e14").strip(),
        dark_color=data.get("dark_color", "#1a1a1a").strip(),
        services=data.get("services", DEFAULT_SERVICES),
        blog_topics=data.get("blog_topics", DEFAULT_BLOG_TOPICS),
        gemini_api_key=data.get("gemini_api_key", "").strip() or os.getenv("GEMINI_API_KEY", ""),
        pexels_api_key=data.get("pexels_api_key", "").strip() or os.getenv("PEXELS_API_KEY", ""),
        maps_embed_url=data.get("maps_embed_url", "").strip(),
        contact_email=data.get("contact_email", "").strip(),
        smtp_host=data.get("smtp_host", "").strip(),
        smtp_port=int(data.get("smtp_port") or 587),
        smtp_encryption=data.get("smtp_encryption", "tls").strip(),
        smtp_username=data.get("smtp_username", "").strip(),
        smtp_password=data.get("smtp_password", "").strip(),
        smtp_from_name=data.get("smtp_from_name", "").strip(),
        smtp_from_email=data.get("smtp_from_email", "").strip(),
        rich_footer=bool(data.get("rich_footer", False)),
    )

    failed_items = data.get("failed_items", [])  # list of {label, type}

    log_queue: queue.Queue = queue.Queue()

    def streamer():
        for line in iter(log_queue.get, None):
            yield f"data: {json.dumps(line)}\n\n"

    record_id = data.get("record_id")

    def runner():
        def log(msg: str):
            log_queue.put(msg)
        try:
            from src.deployer import deploy_retry
            summary = deploy_retry(cfg, failed_items, log=log)
            retried_labels = {
                (item["label"] if isinstance(item, dict) else item)
                for item in failed_items
            }
            if record_id:
                hist.update_deployment(record_id, summary["published_urls"], summary["failed"], retried_labels)
            log(f"\n🔁 Retry complete! {len(summary['success'])} succeeded, {len(summary['failed'])} still failed.")
            if record_id:
                log(f"__RECORD_ID__:{record_id}")
        except Exception as e:
            log(f"\n💥 Fatal error: {e}")
        finally:
            log_queue.put(None)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()

    return Response(streamer(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


if __name__ == "__main__":
    print(f"\n{'='*50}")
    print("  Rank & Rent Deployer")
    print(f"  Open: http://localhost:{PORT}")
    print(f"{'='*50}\n")
    # Debug enables the Werkzeug console (arbitrary code execution), so it is
    # opt-in. Bound to loopback so a deploy in progress is never network-reachable.
    app.run(host="127.0.0.1", port=PORT,
            debug=os.getenv("FLASK_DEBUG", "0") == "1", threaded=True)
