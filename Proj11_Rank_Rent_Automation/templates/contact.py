"""
contact.py — Contact page builder (native Gutenberg blocks, v2).
Hero (cover) + a two-column layout: the working contact form (kept as
wp:html — it's a functional JS form posting to the rr/v1/contact REST
endpoint, no native block equivalent) alongside native heading/paragraph
blocks for the contact info sidebar.
"""
import re
from src.config import DeployConfig


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def build_contact_page(cfg: DeployConfig, content: dict, hero_img: dict | None = None) -> str:
    pc = cfg.primary_color
    pd = _phone_digits(cfg.phone)
    fallback = "https://images.pexels.com/photos/1108101/pexels-photo-1108101.jpeg"
    img_url = (hero_img or {}).get("url", "") or fallback

    reset_css = f"""<!-- wp:html -->
<style>
.entry-title,.entry-header,.ast-page-title-area{{display:none!important;margin:0!important;padding:0!important}}
body{{overflow-x:hidden}}
.entry-content,.ast-article-single,.ast-article-post{{padding:0!important;margin-top:0!important}}
.ast-container,.content-area,.site-main,.ast-article-single,.wp-block-html{{overflow:visible!important}}
.entry-content[data-ast-blocks-layout]>*{{max-width:none!important}}
.wp-block-html:first-child{{margin-top:0!important;margin-bottom:0!important}}
.rr-ct-field{{display:block;width:100%;padding:12px 16px;border:1px solid #ddd;font-size:14px;margin-bottom:12px;box-sizing:border-box;border-radius:2px;font-family:inherit;outline:none}}
.rr-ct-field:focus{{border-color:{pc}}}
.rr-ct-submit{{width:100%;background:{pc};color:#fff;border:none;padding:15px;font-weight:700;font-size:15px;text-transform:uppercase;letter-spacing:1px;cursor:pointer;border-radius:2px;font-family:inherit}}
</style>
<!-- /wp:html -->"""

    hero = f"""<!-- wp:cover {{"url":"{img_url}","dimRatio":60,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-60 has-background-dim"></span><img class="wp-block-cover__image-background" src="{img_url}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"100px","bottom":"100px"}}}}}},"layout":{{"type":"constrained","contentSize":"700px"}}}} -->
<div class="wp-block-group" style="padding-top:100px;padding-bottom:100px"><!-- wp:heading {{"textAlign":"center","level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"clamp(28px, 4vw, 48px)","fontWeight":"800","textTransform":"uppercase"}}}}}} -->
<h1 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:clamp(28px, 4vw, 48px);font-weight:800;text-transform:uppercase">{content.get('h1', f'Contact {cfg.business_name}')}</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"17px"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:17px">{content.get('intro', f"Get a free quote from {cfg.city}'s trusted {cfg.business_name}.")}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group --></div></div>
<!-- /wp:cover -->"""

    form_html = """<!-- wp:html -->
<form id="rr-contact-form">
  <input class="rr-ct-field" type="text" name="rr_name" placeholder="Full Name" required>
  <input class="rr-ct-field" type="email" name="rr_email" placeholder="Email Address" required>
  <input class="rr-ct-field" type="tel" name="rr_phone" placeholder="Phone Number">
  <textarea class="rr-ct-field" name="rr_message" placeholder="Describe your project..." rows="5"></textarea>
  <button class="rr-ct-submit" type="submit" id="rr-ct-btn">Send Message</button>
  <p id="rr-ct-msg" style="margin-top:14px;font-size:15px;display:none"></p>
</form>
<script>
(function(){
  var form = document.getElementById('rr-contact-form');
  var btn  = document.getElementById('rr-ct-btn');
  var msg  = document.getElementById('rr-ct-msg');
  if (!form) return;
  form.addEventListener('submit', function(e) {
    e.preventDefault();
    btn.disabled = true;
    btn.textContent = 'Sending…';
    msg.style.display = 'none';
    var fd = new FormData(form);
    fd.append('action', 'rr_contact');
    fd.append('source', window.location.pathname);
    fetch('/wp-admin/admin-ajax.php', {method:'POST', body:fd})
    .then(function(r) { return r.json(); })
    .then(function(res) {
      if (res.success) {
        msg.style.color = '#2e7d32';
        msg.textContent = res.data || "Thank you! We'll be in touch soon.";
        form.reset();
      } else {
        msg.style.color = '#c62828';
        msg.textContent = res.data || 'Something went wrong. Please call us directly.';
      }
      msg.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Send Message';
    })
    .catch(function() {
      msg.style.color = '#c62828';
      msg.textContent = 'Connection error. Please call us directly.';
      msg.style.display = 'block';
      btn.disabled = false;
      btn.textContent = 'Send Message';
    });
  });
})();
</script>
<!-- /wp:html -->"""

    address_note = content.get("address_note", f"{cfg.city}, {cfg.state} and surrounding areas")
    info = f"""<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:heading {{"level":3,"style":{{"typography":{{"fontSize":"20px","fontWeight":"700","textTransform":"uppercase","letterSpacing":"1px"}}}}}} -->
<h3 class="wp-block-heading" style="font-size:20px;font-weight:700;text-transform:uppercase;letter-spacing:1px">Contact Info</h3>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"15px","lineHeight":"1.7"}}}}}} -->
<p class="has-text-color" style="color:#555555;font-size:15px;line-height:1.7"><strong>Phone</strong><br><a href="tel:{pd}" style="color:{pc};font-weight:700">{cfg.phone}</a></p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"15px","lineHeight":"1.7"}}}}}} -->
<p class="has-text-color" style="color:#555555;font-size:15px;line-height:1.7"><strong>Service Area</strong><br>{address_note}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"15px","lineHeight":"1.7"}}}}}} -->
<p class="has-text-color" style="color:#555555;font-size:15px;line-height:1.7"><strong>Hours</strong><br>Mon – Sat: 7am – 6pm<br>Sunday: By appointment</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->"""

    body = f"""<!-- wp:columns {{"style":{{"spacing":{{"padding":{{"top":"60px","bottom":"60px"}},"blockGap":{{"left":"60px"}}}}}}}} -->
<div class="wp-block-columns" style="padding-top:60px;padding-bottom:60px"><!-- wp:column -->
<div class="wp-block-column">
{form_html}
</div>
<!-- /wp:column -->

<!-- wp:column {{"width":"260px"}} -->
<div class="wp-block-column" style="flex-basis:260px">
{info}
</div>
<!-- /wp:column --></div>
<!-- /wp:columns -->"""

    sections = [reset_css, hero, body]

    if cfg.maps_embed_url:
        map_section = (
            f'<!-- wp:html -->\n'
            f'<iframe src="{cfg.maps_embed_url}" style="width:100%;height:480px;border:0;display:block;margin:0" allowfullscreen loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>\n'
            f'<!-- /wp:html -->'
        )
        sections.append(map_section)

    return "\n\n".join(sections)


def build_contact_payload(cfg: DeployConfig, content: dict, hero_img: dict | None = None) -> dict:
    return {
        "title": "Contact Us",
        "slug": "contact-us",
        "content": build_contact_page(cfg, content, hero_img),
        "status": "publish",
        "meta": {"_astra-site-sidebar-layout": "no-sidebar", "site-post-title": "disabled"},
    }
