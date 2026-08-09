"""
homepage.py — Builds native Gutenberg block markup for the homepage (v2).
Hero (with lead form), intro, why-choose-us, 3-col highlight grid, 3
alternating media+text sections, 5-step process, why-us + stats, map embed,
and bottom CTA — all native blocks. See docs/GUTENBERG_CONVERSION_NOTES.md
for the block-validation gotchas this template was built to avoid.

Unlike v1, the hero lives in this file too (build_homepage_payload no longer
takes a separate hero_block argument — deployer.py was updated to match).
"""
import re
from src.config import DeployConfig


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def _reset_css() -> str:
    return """<!-- wp:html -->
<style>
.entry-title,.ast-archive-title,.entry-header,.ast-page-title-area{display:none!important;margin:0!important;padding:0!important}
body{overflow-x:hidden}
.entry-content,.ast-article-single,.ast-article-post{padding:0!important;margin-top:0!important}
.ast-container,.content-area,.site-main,.ast-article-single,.wp-block-html{overflow:visible!important}
.entry-content[data-ast-blocks-layout]>*{max-width:none!important}
.wp-block-html:first-child{margin-top:0!important;margin-bottom:0!important}
.rr-top-accent{border-left:none!important;border-right:none!important;border-bottom:none!important}
.rr-hf{display:block;width:100%;padding:12px 16px;border:1px solid #ddd;font-size:14px;margin-bottom:12px;box-sizing:border-box;border-radius:2px;font-family:inherit}
@media(max-width:900px){
  .wp-block-group.is-layout-grid{grid-template-columns:repeat(2,1fr)!important}
}
@media(max-width:768px){
  .rr-hero-form-wrap{display:none!important}
}
@media(max-width:600px){
  .wp-block-group.is-layout-grid{grid-template-columns:1fr!important}
}
</style>
<!-- /wp:html -->"""


def _hero(cfg: DeployConfig, content: dict, hero_img: dict | None) -> str:
    pc = cfg.primary_color
    phone = cfg.phone
    pd = _phone_digits(phone)
    hero_url = (hero_img or {}).get("url", "")
    primary = cfg.services[0] if cfg.services else "Local Service"
    hero_h1 = content.get("hero_h1", f"{cfg.city}'s Trusted {primary} Contractor")
    hero_tagline = content.get("hero_tagline", f"Professional {primary.lower()} services for {cfg.city} homeowners and businesses.")

    return f"""<!-- wp:cover {{"url":"{hero_url}","dimRatio":60,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-60 has-background-dim"></span><img class="wp-block-cover__image-background" src="{hero_url}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:columns {{"className":"rr-hero-inner","style":{{"spacing":{{"padding":{{"top":"100px","bottom":"100px","left":"40px","right":"40px"}},"blockGap":{{"left":"48px"}}}}}}}} -->
<div class="wp-block-columns rr-hero-inner" style="padding-top:100px;padding-right:40px;padding-bottom:100px;padding-left:40px"><!-- wp:column -->
<div class="wp-block-column"><!-- wp:heading {{"level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"clamp(32px, 4vw, 54px)","fontWeight":"800","lineHeight":"1.15"}}}}}} -->
<h1 class="wp-block-heading has-text-color" style="color:#ffffff;font-size:clamp(32px, 4vw, 54px);font-weight:800;line-height:1.15">{hero_h1}</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"18px","lineHeight":"1.6"}}}}}} -->
<p class="has-text-color" style="color:#ffffff;font-size:18px;line-height:1.6">{hero_tagline}</p>
<!-- /wp:paragraph -->

<!-- wp:buttons -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-background wp-element-button" style="background-color:{pc}" href="/contact-us/">Get Free Quote</a></div>
<!-- /wp:button -->

<!-- wp:button {{"className":"is-style-outline","style":{{"color":{{"text":"#ffffff"}},"border":{{"color":"#ffffff","width":"2px"}}}}}} -->
<div class="wp-block-button is-style-outline"><a class="wp-block-button__link has-text-color has-border-color wp-element-button" style="border-color:#ffffff;border-width:2px;color:#ffffff" href="tel:{pd}">Call {phone}</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:column -->

<!-- wp:column {{"className":"rr-hero-form-wrap","width":"380px"}} -->
<div class="wp-block-column rr-hero-form-wrap" style="flex-basis:380px"><!-- wp:group {{"style":{{"color":{{"background":"#ffffff"}},"spacing":{{"padding":{{"top":"34px","bottom":"34px","left":"30px","right":"30px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group has-background" style="background-color:#ffffff;padding-top:34px;padding-right:30px;padding-bottom:34px;padding-left:30px"><!-- wp:paragraph {{"style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"11px","fontWeight":"700","letterSpacing":"2px","textTransform":"uppercase"}}}}}} -->
<p class="has-text-color" style="color:{pc};font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase">Free Estimate</p>
<!-- /wp:paragraph -->

<!-- wp:heading {{"level":3,"style":{{"typography":{{"fontSize":"22px","fontWeight":"800"}}}}}} -->
<h3 class="wp-block-heading" style="font-size:22px;font-weight:800">Get A Free Quote</h3>
<!-- /wp:heading -->

<!-- wp:html -->
<form class="rr-ajax-form">
  <input class="rr-hf" type="text" name="rr_name" placeholder="Full Name" required>
  <input class="rr-hf" type="email" name="rr_email" placeholder="Email Address" required>
  <input class="rr-hf" type="tel" name="rr_phone" placeholder="Phone Number">
  <textarea class="rr-hf" name="rr_message" placeholder="Describe your project..." rows="3" style="resize:none"></textarea>
  <button class="rr-hf" type="submit" style="background:{pc};color:#fff;border:none;font-weight:700;text-transform:uppercase;letter-spacing:1px;cursor:pointer">GET MY FREE QUOTE</button>
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
          msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(0,200,100,.15);color:#2d6a4f';
          msg.textContent = res.data || "Thank you! We'll be in touch soon.";
          form.reset();
        }} else {{
          msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(220,53,69,.1);color:#842029';
          msg.textContent = res.data || 'Something went wrong. Please try again.';
        }}
      }})
      .catch(function(){{
        msg.style.cssText='display:block;margin-top:10px;padding:10px;border-radius:4px;font-size:13px;font-weight:600;text-align:center;background:rgba(220,53,69,.1);color:#842029';
        msg.textContent = 'Network error. Please try again.';
      }})
      .finally(function(){{ btn.disabled=false; btn.textContent='GET MY FREE QUOTE'; }});
  }});
}})();
</script>
<!-- /wp:html --></div>
<!-- /wp:group --></div>
<!-- /wp:column --></div>
<!-- /wp:columns --></div></div>
<!-- /wp:cover -->"""


def _eyebrow(text: str, pc: str) -> str:
    return f"""<!-- wp:paragraph {{"style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"11px","fontWeight":"700","letterSpacing":"3px","textTransform":"uppercase"}}}}}} -->
<p class="has-text-color" style="color:{pc};font-size:11px;font-weight:700;letter-spacing:3px;text-transform:uppercase">{text}</p>
<!-- /wp:paragraph -->"""


def build_homepage(cfg: DeployConfig, content: dict, images: dict) -> str:
    pc = cfg.primary_color
    dc = cfg.dark_color
    phone = cfg.phone
    pd = _phone_digits(phone)

    def img(slot: str) -> str:
        d = images.get(slot) or {}
        return d.get("url", "")

    svcs = cfg.services or ["Our Services"]
    svc1 = svcs[0] if len(svcs) > 0 else "Our Services"
    svc2 = svcs[1] if len(svcs) > 1 else svc1
    svc3 = svcs[2] if len(svcs) > 2 else svc1

    reset_css = _reset_css()
    hero = _hero(cfg, content, images.get("hero"))

    intro = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"60px","bottom":"60px"}}}}}},"layout":{{"type":"constrained","contentSize":"820px"}}}} -->
<div class="wp-block-group" style="padding-top:60px;padding-bottom:60px"><!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"17px","lineHeight":"1.85"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#555555;font-size:17px;line-height:1.85">{content.get('intro_paragraph', '')}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->"""

    separator = """<!-- wp:separator {"opacity":"css"} -->
<hr class="wp-block-separator has-css-opacity"/>
<!-- /wp:separator -->"""

    # "Why choose us" — image + text, image on the left.
    best = f"""<!-- wp:media-text {{"mediaPosition":"left","mediaType":"image","mediaUrl":"{img('best')}","mediaLink":"","style":{{"spacing":{{"padding":{{"top":"72px","bottom":"72px"}}}}}}}} -->
<div class="wp-block-media-text alignwide is-stacked-on-mobile has-media-on-the-left" style="padding-top:72px;padding-bottom:72px"><figure class="wp-block-media-text__media"><img src="{img('best')}" alt="{cfg.business_name} {cfg.city}"/></figure><div class="wp-block-media-text__content">
{_eyebrow('Why Choose Us', pc)}

<!-- wp:heading {{"style":{{"typography":{{"fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading" style="font-weight:800">{content.get('best_h2', f'Best {svc1} Company in {cfg.city}')}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}}}}}} -->
<p class="has-text-color" style="color:#555555">{content.get('best_body', '')}</p>
<!-- /wp:paragraph -->

<!-- wp:buttons -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-background wp-element-button" style="background-color:{pc}" href="/contact-us/">Get A Free Quote</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div></div>
<!-- /wp:media-text -->"""

    # 3-column highlight grid, dark bg, orange top-border accent cards.
    service_cards = content.get("service_cards", [])[:3]
    d3_cards = []
    for card in service_cards:
        d3_cards.append(f"""<!-- wp:group {{"className":"rr-top-accent","style":{{"border":{{"top":{{"color":"{pc}","width":"4px"}}}},"color":{{"background":"#222222"}},"spacing":{{"padding":{{"top":"32px","bottom":"32px","left":"28px","right":"28px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group rr-top-accent has-border-color has-background" style="border-top-color:{pc};border-top-width:4px;background-color:#222222;padding-top:32px;padding-right:28px;padding-bottom:32px;padding-left:28px"><!-- wp:heading {{"level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"20px","fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-color" style="color:#ffffff;font-size:20px;font-weight:800">{card.get('title', '')}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#cccccc"}},"typography":{{"fontSize":"14px","lineHeight":"1.7"}}}}}} -->
<p class="has-text-color" style="color:#cccccc;font-size:14px;line-height:1.7">{card.get('description', '')}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->""")

    d3 = f"""<!-- wp:group {{"style":{{"color":{{"background":"{dc}"}},"spacing":{{"padding":{{"top":"72px","bottom":"72px"}}}}}},"layout":{{"type":"constrained","contentSize":"1100px"}}}} -->
<div class="wp-block-group has-background" style="background-color:{dc};padding-top:72px;padding-bottom:72px"><!-- wp:group {{"style":{{"spacing":{{"blockGap":"3px"}}}},"layout":{{"type":"grid","columnCount":3}}}} -->
<div class="wp-block-group">
{chr(10).join(d3_cards)}
</div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    # 3 alternating media+text sections — white/gray/white, image side alternates.
    alt_defs = [
        ("right", False, "Services", f"Local {svc1} in {cfg.city}",
         f"Our team specializes in {svc1.lower()} for homeowners and businesses across {cfg.city}, {cfg.state}. We deliver quality workmanship backed by years of local experience and a commitment to customer satisfaction.",
         img("svc1"), f"{svc1} {cfg.city}"),
        ("left", True, "Expert Service", f"{svc2} in {cfg.city}",
         f"We bring expertise and professionalism to every {svc2.lower()} job in {cfg.city}, {cfg.state}. Our specialists use high-quality materials and proven techniques to deliver results that last.",
         img("svc2"), f"{svc2} {cfg.city}"),
        ("right", False, "Quality Work", f"{svc3} Professionals",
         f"Our {svc3.lower()} team proudly serves {cfg.city} and surrounding {cfg.state} communities. Every project is handled with professionalism, attention to detail, and a satisfaction guarantee.",
         img("svc3"), f"{svc3} {cfg.city}"),
    ]
    alt_sections = []
    for media_position, is_gray, eyebrow, heading, body, image_url, alt_text in alt_defs:
        position_class = "has-media-on-the-right" if media_position == "right" else "has-media-on-the-left"
        figure = f'<figure class="wp-block-media-text__media"><img src="{image_url}" alt="{alt_text}"/></figure>'
        content_div = f"""<div class="wp-block-media-text__content">
{_eyebrow(eyebrow, pc)}

<!-- wp:heading {{"style":{{"typography":{{"fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading" style="font-weight:800">{heading}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}}}}}} -->
<p class="has-text-color" style="color:#555555">{body}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"13px","fontWeight":"700","textTransform":"uppercase","letterSpacing":"1px"}}}}}} -->
<p class="has-text-color" style="color:{pc};font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px"><a href="/contact-us/" style="color:{pc}">Learn More →</a></p>
<!-- /wp:paragraph --></div>"""
        inner = figure + content_div
        media_text = f"""<!-- wp:media-text {{"mediaPosition":"{media_position}","mediaType":"image","mediaUrl":"{image_url}","mediaLink":"","style":{{"spacing":{{"padding":{{"top":"72px","bottom":"72px"}}}}}}}} -->
<div class="wp-block-media-text alignwide is-stacked-on-mobile {position_class}" style="padding-top:72px;padding-bottom:72px">{inner}</div>
<!-- /wp:media-text -->"""
        if is_gray:
            alt_sections.append(f"""<!-- wp:group {{"style":{{"color":{{"background":"#f7f7f7"}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group has-background" style="background-color:#f7f7f7">
{media_text}
</div>
<!-- /wp:group -->""")
        else:
            alt_sections.append(media_text)

    # 5-step process grid.
    steps_in = content.get("process_steps", [])[:5]
    step_blocks = []
    for i, s in enumerate(steps_in):
        step_blocks.append(f"""<!-- wp:group {{"style":{{"spacing":{{"blockGap":"8px"}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:paragraph {{"align":"center","style":{{"color":{{"background":"{pc}","text":"#ffffff"}},"typography":{{"fontSize":"20px","fontWeight":"800"}},"border":{{"radius":"50%"}},"spacing":{{"padding":{{"top":"0","right":"0","bottom":"0","left":"0"}}}}}}}} -->
<p class="has-text-align-center has-text-color has-background" style="background-color:{pc};border-radius:50%;color:#ffffff;font-size:20px;font-weight:800;padding-top:0;padding-right:0;padding-bottom:0;padding-left:0;width:52px;height:52px;line-height:52px;margin:0 auto">{i + 1}</p>
<!-- /wp:paragraph -->

<!-- wp:heading {{"textAlign":"center","level":3,"style":{{"typography":{{"fontSize":"14px"}}}}}} -->
<h3 class="wp-block-heading has-text-align-center" style="font-size:14px">{s.get('title', '')}</h3>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#666666"}},"typography":{{"fontSize":"13px","lineHeight":"1.6"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#666666;font-size:13px;line-height:1.6">{s.get('description', '')}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->""")

    process = f"""<!-- wp:group {{"style":{{"color":{{"background":"#f7f7f7"}},"spacing":{{"padding":{{"top":"72px","bottom":"72px"}}}}}},"layout":{{"type":"constrained","contentSize":"1000px"}}}} -->
<div class="wp-block-group has-background" style="background-color:#f7f7f7;padding-top:72px;padding-bottom:72px"><!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group">
{_eyebrow('How It Works', pc)}

<!-- wp:heading {{"textAlign":"center","style":{{"typography":{{"fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center" style="font-weight:800">Our Process</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#666666"}},"spacing":{{"margin":{{"bottom":"48px"}}}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#666666;margin-bottom:48px">We make every project simple from start to finish.</p>
<!-- /wp:paragraph -->

<!-- wp:group {{"style":{{"spacing":{{"blockGap":"24px"}}}},"layout":{{"type":"grid","columnCount":5}}}} -->
<div class="wp-block-group">
{chr(10).join(step_blocks)}
</div>
<!-- /wp:group --></div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    # Why-us: text column + a small fixed-width 3-stat grid column.
    stats_in = [("850+", "Projects Done"), ("15+", "Years Experience"), ("100%", "Satisfaction")]
    stat_blocks = []
    for num, label in stats_in:
        stat_blocks.append(f"""<!-- wp:group {{"className":"rr-top-accent","style":{{"border":{{"top":{{"color":"{pc}","width":"4px"}}}},"color":{{"background":"#f7f7f7"}},"spacing":{{"padding":{{"top":"24px","bottom":"24px","left":"6px","right":"6px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group rr-top-accent has-border-color has-background" style="border-top-color:{pc};border-top-width:4px;background-color:#f7f7f7;padding-top:24px;padding-right:6px;padding-bottom:24px;padding-left:6px"><!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"26px","fontWeight":"800"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:{pc};font-size:26px;font-weight:800">{num}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#888888"}},"typography":{{"fontSize":"10px","textTransform":"uppercase"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#888888;font-size:10px;text-transform:uppercase">{label}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->""")

    why = f"""<!-- wp:columns {{"style":{{"spacing":{{"padding":{{"top":"72px","bottom":"72px"}},"blockGap":{{"left":"60px"}}}}}}}} -->
<div class="wp-block-columns" style="padding-top:72px;padding-bottom:72px"><!-- wp:column -->
<div class="wp-block-column">
{_eyebrow('Our Promise', pc)}

<!-- wp:heading {{"style":{{"typography":{{"fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading" style="font-weight:800">Why Choose {cfg.business_name}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}}}}}} -->
<p class="has-text-color" style="color:#555555">{content.get('why_body', '')}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:column -->

<!-- wp:column {{"width":"360px"}} -->
<div class="wp-block-column" style="flex-basis:360px"><!-- wp:group {{"style":{{"spacing":{{"blockGap":"3px"}}}},"layout":{{"type":"grid","columnCount":3}}}} -->
<div class="wp-block-group">
{chr(10).join(stat_blocks)}
</div>
<!-- /wp:group --></div>
<!-- /wp:column --></div>
<!-- /wp:columns -->"""


    cta = f"""<!-- wp:group {{"align":"full","style":{{"color":{{"background":"{dc}"}},"spacing":{{"padding":{{"top":"72px","bottom":"72px","left":"24px","right":"24px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group alignfull has-background" style="background-color:{dc};padding-top:72px;padding-right:24px;padding-bottom:72px;padding-left:24px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-weight:800">{content.get('cta_h2', f'Ready to Get Started in {cfg.city}?')}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff">{content.get('cta_body', '')}</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-background wp-element-button" style="background-color:{pc}" href="/contact-us/">Get A Free Quote</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"15px"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:15px"><a href="tel:{pd}" style="color:#ffffff">Call {phone}</a></p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->"""

    parts = [reset_css, hero, intro, separator, best, d3] + alt_sections + [process, why]
    parts.append(cta)
    return "\n\n".join(parts)


def build_homepage_payload(cfg: DeployConfig, content: dict, images: dict) -> dict:
    return {
        "title": "Home",
        "slug": "home",
        "content": build_homepage(cfg, content, images),
        "status": "publish",
        "meta": {
            "_astra-site-sidebar-layout": "no-sidebar",
            "site-post-title": "disabled",
        },
    }
