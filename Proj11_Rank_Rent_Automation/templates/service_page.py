"""
service_page.py — Builds native Gutenberg block markup for service pages (v2).
Same signature as v1, but emits real wp:cover / wp:media-text / wp:group blocks
instead of a single wp:html blob, so clients can edit content directly in the
WordPress block editor. A small technical CSS reset (page-title hiding, Astra
max-width override, mobile hero stacking) still ships as one wp:html snippet —
it's invisible plumbing, not content a client would ever touch.
"""
import re
from src.config import DeployConfig


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text)


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def build_service_page(cfg: DeployConfig, content: dict, images: dict) -> str:
    """
    Assembles native Gutenberg block markup for a service page.

    content keys: h1, intro, sections (list of {h2, body}), cta_text, service
    images keys: hero, section1, section2, section3, section4  (each: {id, url} or None)
    """
    pc = cfg.primary_color
    dc = cfg.dark_color
    phone = cfg.phone
    phone_digits = _phone_digits(phone)

    _FALLBACKS = [
        "https://images.pexels.com/photos/1078884/pexels-photo-1078884.jpeg",
        "https://images.pexels.com/photos/159306/construction-site-build-construction-work-159306.jpeg",
        "https://images.pexels.com/photos/585419/pexels-photo-585419.jpeg",
        "https://images.pexels.com/photos/209251/pexels-photo-209251.jpeg",
        "https://images.pexels.com/photos/1216589/pexels-photo-1216589.jpeg",
        "https://images.pexels.com/photos/1109541/pexels-photo-1109541.jpeg",
    ]
    import hashlib as _hl
    _svc_name = content.get("service", "") or ""
    _fb_idx = int(_hl.md5(_svc_name.encode()).hexdigest()[:4], 16) % len(_FALLBACKS)
    fallback = _FALLBACKS[_fb_idx]
    hero_data = images.get("hero", {}) or {}
    hero_img = hero_data.get("url", "") or fallback

    def img_url(slot: str) -> str:
        d = images.get(slot) or {}
        return d.get("url", fallback)

    # Technical reset — page-title hiding, Astra full-width fix, mobile hero stacking.
    # Not client-editable content; kept as a single inline snippet on purpose.
    reset_css = f"""<!-- wp:html -->
<style>
.entry-title,.entry-header,.ast-page-title-area{{display:none!important;margin:0!important;padding:0!important}}
body{{overflow-x:hidden}}
.entry-content,.ast-article-single,.ast-article-post{{padding:0!important;margin-top:0!important}}
.ast-container,.content-area,.site-main,.ast-article-single,.wp-block-html{{overflow:visible!important}}
.entry-content[data-ast-blocks-layout]>*{{max-width:none!important}}
.wp-block-html:first-child{{margin-top:0!important;margin-bottom:0!important}}
.rr-hero-form input::placeholder{{color:rgba(255,255,255,.55)}}
@media(max-width:768px){{
  .rr-hero-cols{{flex-direction:column !important}}
  .rr-hero-form{{display:none !important}}
}}
</style>
<!-- /wp:html -->"""

    # Hero: full-width cover with heading + call button on the left,
    # a lead-capture form (kept as raw HTML — no native form block exists) on the right.
    hero = f"""<!-- wp:cover {{"url":"{hero_img}","dimRatio":60,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-60 has-background-dim"></span><img class="wp-block-cover__image-background" src="{hero_img}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:columns {{"className":"rr-hero-cols","style":{{"spacing":{{"padding":{{"top":"80px","bottom":"80px","left":"40px","right":"40px"}},"blockGap":{{"left":"40px"}}}}}}}} -->
<div class="wp-block-columns rr-hero-cols" style="padding-top:80px;padding-right:40px;padding-bottom:80px;padding-left:40px"><!-- wp:column -->
<div class="wp-block-column"><!-- wp:heading {{"level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"40px","lineHeight":"1.2","textTransform":"uppercase"}}}}}} -->
<h1 class="wp-block-heading has-text-color" style="color:#ffffff;font-size:40px;line-height:1.2;text-transform:uppercase">{content.get('h1', '')}</h1>
<!-- /wp:heading -->

<!-- wp:buttons -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}"}},"typography":{{"textTransform":"uppercase"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-background wp-element-button" style="background-color:{pc};text-transform:uppercase" href="tel:{phone_digits}">Call Us Now</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:column -->

<!-- wp:column {{"className":"rr-hero-form"}} -->
<div class="wp-block-column rr-hero-form"><!-- wp:heading {{"level":3,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"20px","textTransform":"uppercase"}}}}}} -->
<h3 class="wp-block-heading has-text-color" style="color:#ffffff;font-size:20px;text-transform:uppercase">Get Free Quote</h3>
<!-- /wp:heading -->

<!-- wp:html -->
<form class="rr-ajax-form" style="margin:0">
  <input type="text" name="rr_name" placeholder="Full Name" required style="display:block;width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.4);color:#fff;padding:11px 14px;font-size:14px;margin-bottom:10px;box-sizing:border-box;outline:none">
  <input type="email" name="rr_email" placeholder="Email Address" required style="display:block;width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.4);color:#fff;padding:11px 14px;font-size:14px;margin-bottom:10px;box-sizing:border-box;outline:none">
  <input type="tel" name="rr_phone" placeholder="Phone Number" style="display:block;width:100%;background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.4);color:#fff;padding:11px 14px;font-size:14px;margin-bottom:14px;box-sizing:border-box;outline:none">
  <button type="submit" style="width:100%;background:{pc};color:#fff;padding:13px;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:1px;border:none;cursor:pointer">Get Free Quote</button>
  <div class="rr-form-msg" style="display:none;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center"></div>
</form>
<script>
(function(){{
  var form = document.currentScript.previousElementSibling;
  if(!form) return;
  form.addEventListener('submit', function(e){{
    e.preventDefault();
    var btn = form.querySelector('button[type=submit]');
    var msg = form.querySelector('.rr-form-msg');
    var fd = new FormData(form);
    fd.append('action','rr_contact');
    fd.append('source', window.location.pathname);
    btn.disabled = true; btn.textContent = 'Sending…';
    fetch('/wp-admin/admin-ajax.php',{{method:'POST',body:fd}})
      .then(function(r){{return r.json();}})
      .then(function(res){{
        if(res.success){{
          msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(0,200,100,.2);color:#fff';
          msg.textContent = res.data || "Thank you! We'll be in touch soon.";
          form.reset();
        }} else {{
          msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(255,80,80,.2);color:#fff';
          msg.textContent = res.data || 'Something went wrong. Please try again.';
        }}
      }})
      .catch(function(){{
        msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(255,80,80,.2);color:#fff';
        msg.textContent = 'Network error. Please try again.';
      }})
      .finally(function(){{ btn.disabled=false; btn.textContent='Get Free Quote'; }});
  }});
}})();
</script>
<!-- /wp:html --></div>
<!-- /wp:column --></div>
<!-- /wp:columns --></div></div>
<!-- /wp:cover -->"""

    intro = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"50px","bottom":"20px"}}}}}},"layout":{{"type":"constrained","contentSize":"1200px"}}}} -->
<div class="wp-block-group" style="padding-top:50px;padding-bottom:20px"><!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"16px","lineHeight":"1.8"}},"color":{{"text":"#555555"}}}}}} -->
<p class="has-text-color" style="color:#555555;font-size:16px;line-height:1.8">{content.get('intro', '')}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->"""

    # Alternating media+text sections, dark theme on odd index — mirrors v1's pattern.
    sections_html = []
    section_slots = ["section1", "section2", "section3", "section4"]
    content_sections = content.get("sections", [])

    for i, sec in enumerate(content_sections[:4]):
        slot = section_slots[i]
        is_dark = (i % 2 == 1)
        media_position = "left" if is_dark else "right"
        img = img_url(slot)

        text_color = "#ffffff" if is_dark else "#1a1a1a"
        body_color = "#cccccc" if is_dark else "#555555"

        h2_style = f'style="color:{text_color};text-transform:uppercase;font-size:26px"'
        h2_class = 'class="wp-block-heading has-text-color"'
        p_style = f'style="color:{body_color};font-size:15px;line-height:1.8"'
        p_class = 'class="has-text-color"'

        media_text_attrs = f'"mediaPosition":"{media_position}","mediaType":"image","mediaUrl":"{img}","mediaLink":""'
        position_class = "has-media-on-the-right" if media_position == "right" else ""
        classes = " ".join(c for c in ["wp-block-media-text", "alignwide", "is-stacked-on-mobile", position_class] if c)

        figure = f'<figure class="wp-block-media-text__media"><img src="{img}" alt=""/></figure>'
        content_div = f"""<div class="wp-block-media-text__content"><!-- wp:heading {{"level":2,"style":{{"typography":{{"textTransform":"uppercase","fontSize":"26px"}},"color":{{"text":"{text_color}"}}}}}} -->
<h2 {h2_class} {h2_style}>{sec.get('h2', '')}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"15px","lineHeight":"1.8"}},"color":{{"text":"{body_color}"}}}}}} -->
<p {p_class} {p_style}>{sec.get('body', '')}</p>
<!-- /wp:paragraph --></div>"""

        # Gutenberg's Media & Text save() always emits <figure> before the content
        # div in the DOM, regardless of mediaPosition — the visual side is purely
        # a CSS concern (has-media-on-the-right flips it with flexbox order).
        inner = figure + content_div

        media_text_block = f"""<!-- wp:media-text {{{media_text_attrs}}} -->
<div class="{classes}">{inner}</div>
<!-- /wp:media-text -->"""

        if is_dark:
            # Media & Text's own background-color support doesn't round-trip cleanly
            # through validation — wrap in a Group instead, using the same
            # background pattern already proven valid on the bottom CTA block.
            sections_html.append(f"""<!-- wp:group {{"style":{{"color":{{"background":"{dc}"}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group has-background" style="background-color:{dc}">
{media_text_block}
</div>
<!-- /wp:group -->""")
        else:
            sections_html.append(media_text_block)

    cta = f"""<!-- wp:group {{"align":"full","style":{{"color":{{"background":"{pc}"}},"spacing":{{"padding":{{"top":"60px","bottom":"60px","left":"24px","right":"24px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group alignfull has-background" style="background-color:{pc};padding-top:60px;padding-right:24px;padding-bottom:60px;padding-left:24px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"textTransform":"uppercase"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;text-transform:uppercase">Get A Free {content.get('service', 'Service')} Quote in {cfg.city}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff">Our local specialists in {cfg.city} are standing by. Call now for a free estimate.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"#ffffff","text":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-text-color has-background wp-element-button" style="color:{pc};background-color:#ffffff" href="tel:{phone_digits}">Call {phone}</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:group -->"""

    return "\n\n".join([reset_css, hero, intro] + sections_html + [cta])


def build_service_payload(cfg: DeployConfig, content: dict, images: dict, parent_id: int | None = None) -> dict:
    service = content.get("service", "Service")
    slug = _slugify(f"{service} {cfg.city}")
    block_content = build_service_page(cfg, content, images)

    payload = {
        "title": content.get("h1", f"{service} {cfg.city} {cfg.state}"),
        "slug": slug,
        "content": block_content,
        "status": "publish",
        "meta": {
            "_astra-site-sidebar-layout": "no-sidebar",
            "site-post-title": "disabled",
            "rank_math_title": content.get("meta_title", ""),
            "rank_math_description": content.get("meta_description", ""),
        },
        "excerpt": content.get("meta_description", ""),
    }
    if parent_id:
        payload["parent"] = parent_id
    return payload
