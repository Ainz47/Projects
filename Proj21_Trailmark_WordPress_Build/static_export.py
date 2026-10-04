"""Static snapshot of the Trailmark demo for GitHub Pages (ainz47.github.io/Projects/trailmark/).

  py static_export.py <out_dir>        e.g. ../../git/Projects/docs/trailmark

Fetches every public page, then every same-site asset those pages and their CSS reference
(stylesheets, scripts, fonts, images, video), and rewrites the site URL to BASE_PATH so the copy
works from a GitHub Pages subfolder. Cart, checkout and my-account are left out: they need the
server. Forms get a small script that says so instead of posting to a static host.
The live WordPress site stays the source of truth; re-run this after changing it.
"""
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests

SITE = "https://framelake.s6-tastewp.com"
HOST = urlsplit(SITE).netloc
BASE_PATH = "/Projects/trailmark"
PAGES = ["/", "/product/", "/for-cs-teams/", "/for-implementation/", "/for-revops/", "/about/",
         "/onboarding-checklist/", "/book-a-demo/", "/contact/", "/notes/", "/resources/", "/shop/",
         "/product/onboarding-checklist-template/", "/milestone-time-limits/", "/milestones-or-health-score/"]
TEXT_EXT = {".css", ".js", ".html", ".svg", ".json"}

# Same-site asset URLs, plain or JSON-escaped (Elementor puts background images in data-settings).
ASSET_RE = re.compile(r"(?:https?:)?(?:\\?/){2}" + re.escape(HOST) + r"((?:\\?/)wp-(?:content|includes)(?:\\?/)[^\"'\s)<>&]+)")  # stop at & too: data-settings JSON is entity-encoded (&quot;)
CSS_URL_RE = re.compile(r"url\(\s*['\"]?([^'\")]+)['\"]?\s*\)")

FORM_NOTE = """<script>
document.addEventListener('submit', function (e) {
  var f = e.target;
  if (!f.closest('.wpcf7, .woocommerce, form.cart')) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (f.querySelector('.tm-static-note')) return;
  var p = document.createElement('p'); p.className = 'tm-static-note';
  p.style.cssText = 'margin-top:12px;padding:10px 12px;border:2px solid #14171B;background:#F2C200;color:#14171B;font:600 15px/1.4 Archivo,sans-serif';
  p.innerHTML = 'This is a static copy, so forms and checkout are off here. They work on the <a href="https://framelake.s6-tastewp.com/" style="color:inherit">live WordPress demo</a>.';
  f.appendChild(p);
}, true);
</script>"""


def rewrite(text):
    text = text.replace(SITE.replace("/", "\\/"), BASE_PATH.replace("/", "\\/"))
    text = text.replace(SITE, BASE_PATH).replace("http://" + HOST, BASE_PATH).replace("//" + HOST, BASE_PATH)
    return text


def local_path(out, url_path):
    p = url_path.split("?")[0].split("#")[0].replace("\\/", "/")
    if p.endswith("/"):
        p += "index.html"
    return out / p.lstrip("/")


def main():
    out = Path(sys.argv[1]).resolve()
    s = requests.Session()
    s.headers["User-Agent"] = "Mozilla/5.0 (static export of own demo site)"
    queue, seen = [], set()

    def want(path):
        path = path.replace("\\/", "/").split("#")[0]
        key = path.split("?")[0]
        if key not in seen:
            seen.add(key)
            queue.append(path)

    for page in PAGES:
        r = s.get(SITE + page, timeout=60)
        r.raise_for_status()
        html = r.text
        for m in ASSET_RE.finditer(html):
            want(m.group(1))
        html = rewrite(html)
        # drop server-only discovery links
        html = re.sub(r"<link[^>]+(?:wp-json|xmlrpc|oembed|EditURI|wlwmanifest)[^>]*>\s*", "", html)
        html = html.replace("</body>", FORM_NOTE + "\n</body>")
        dst = local_path(out, page)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(html, encoding="utf-8")
        print("page", page, len(html))

    while queue:
        path = queue.pop(0)
        r = s.get(SITE + path, timeout=120)
        if r.status_code != 200:
            print("MISS", r.status_code, path)
            continue
        dst = local_path(out, path)
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.suffix.lower() in TEXT_EXT:
            text = r.content.decode("utf-8", errors="replace")  # no charset header on CSS: r.text guesses Latin-1 and mangles icon glyphs
            if dst.suffix.lower() == ".css":
                base = SITE + path.split("?")[0]
                for u in CSS_URL_RE.findall(text):
                    if u.startswith("data:"):
                        continue
                    absu = urljoin(base, u)
                    if urlsplit(absu).netloc == HOST:
                        want(urlsplit(absu).path)
            for m in ASSET_RE.finditer(text):
                want(m.group(1))
            dst.write_text(rewrite(text), encoding="utf-8")
        else:
            dst.write_bytes(r.content)
    print("assets", len(seen), "->", out)
    fill_missing(out, s)


def fill_missing(out, s, rounds=3):
    """Elementor loads JS chunks and lightbox CSS at run time from a base URL in its config, so no page
    references them. Open the copy in a browser, collect wp-content/wp-includes 404s, fetch them, repeat."""
    import functools
    import threading
    from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

    from playwright.sync_api import sync_playwright

    class Handler(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            return super().translate_path(path[len(BASE_PATH):] if path.startswith(BASE_PATH) else path)

        def log_message(self, *a):
            pass

    srv = ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(out)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    root = f"http://127.0.0.1:{srv.server_port}{BASE_PATH}"
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            for n in range(rounds):
                missing = set()
                for vp in ({"width": 1280, "height": 900}, {"width": 390, "height": 844}):
                    page = browser.new_page(viewport=vp)
                    page.on("response", lambda r: missing.add(r.url.split("?")[0][len(root):])
                            if r.status == 404 and r.url.startswith(root + "/wp-") else None)
                    for path in PAGES:
                        page.goto(root + path, wait_until="networkidle")
                        page.mouse.wheel(0, 4000)  # scroll-triggered widgets (counters) load their chunks
                        page.wait_for_timeout(600)
                    page.close()
                if not missing:
                    print("fill round", n + 1, ": nothing missing")
                    break
                for path in sorted(missing):
                    r = s.get(SITE + path, timeout=120)
                    if r.status_code != 200:
                        print("  still missing on live:", r.status_code, path)
                        continue
                    dst = local_path(out, path)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.suffix.lower() in TEXT_EXT:
                        dst.write_text(rewrite(r.content.decode("utf-8", errors="replace")), encoding="utf-8")
                    else:
                        dst.write_bytes(r.content)
                print("fill round", n + 1, ": fetched", len(missing))
            browser.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    main()
