"""
services_hub.py — Builds native Gutenberg block markup for the /services/ hub
page (v2). Hero, intro, services card grid, process steps, "why us" stats,
and bottom CTA — all native blocks (wp:cover, wp:group with grid layout,
wp:image, wp:heading, wp:paragraph, wp:buttons) so clients can edit content
directly in the WordPress block editor. See docs/GUTENBERG_CONVERSION_NOTES.md
for the block-validation gotchas this template was built to avoid.
"""
import re
from src.config import DeployConfig

_FALLBACK_IMGS = [
    "https://images.pexels.com/photos/1078884/pexels-photo-1078884.jpeg",
    "https://images.pexels.com/photos/159306/construction-site-build-construction-work-159306.jpeg",
    "https://images.pexels.com/photos/585419/pexels-photo-585419.jpeg",
    "https://images.pexels.com/photos/209251/pexels-photo-209251.jpeg",
    "https://images.pexels.com/photos/1216589/pexels-photo-1216589.jpeg",
    "https://images.pexels.com/photos/1109541/pexels-photo-1109541.jpeg",
]


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def build_services_hub(cfg: DeployConfig, service_pages: list[dict], hero_img: dict | None = None) -> str:
    """
    service_pages: list of {service, link, excerpt, hero_url} — one per deployed service page.
    hero_img: {url, id} for the hub page hero, or None for solid fallback.
    """
    pc = cfg.primary_color
    dc = cfg.dark_color
    phone = cfg.phone
    pd = _phone_digits(phone)
    primary_service = cfg.services[0] if cfg.services else "our services"
    hero_url = (hero_img or {}).get("url", "") or FALLBACK_IMG

    # Technical reset — page-title hiding, Astra full-width fix. Not client-editable
    # content; kept as a single inline snippet on purpose.
    reset_css = """<!-- wp:html -->
<style>
.entry-title,.ast-archive-title,.entry-header,.ast-page-title-area{display:none!important;margin:0!important;padding:0!important}
body{overflow-x:hidden}
.entry-content,.ast-article-single,.ast-article-post{padding:0!important;margin-top:0!important}
.ast-container,.content-area,.site-main,.ast-article-single,.wp-block-html{overflow:visible!important}
.entry-content[data-ast-blocks-layout]>*{max-width:none!important}
.wp-block-html:first-child{margin-top:0!important;margin-bottom:0!important}
@media(max-width:900px){
  .wp-block-group.is-layout-grid{grid-template-columns:repeat(2,1fr)!important}
}
@media(max-width:600px){
  .wp-block-group.is-layout-grid{grid-template-columns:1fr!important}
}
</style>
<!-- /wp:html -->"""

    hero = f"""<!-- wp:cover {{"url":"{hero_url}","dimRatio":60,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-60 has-background-dim"></span><img class="wp-block-cover__image-background" src="{hero_url}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"120px","bottom":"120px"}}}}}},"layout":{{"type":"constrained","contentSize":"680px"}}}} -->
<div class="wp-block-group" style="padding-top:120px;padding-bottom:120px"><!-- wp:heading {{"textAlign":"center","level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"clamp(30px, 4vw, 52px)","fontWeight":"800","textTransform":"uppercase"}}}}}} -->
<h1 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:clamp(30px, 4vw, 52px);font-weight:800;text-transform:uppercase">Our Services in {cfg.city}</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"18px","lineHeight":"1.6"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:18px;line-height:1.6">{cfg.business_name} delivers professional {primary_service.lower()} and more for homeowners and businesses across {cfg.city}, {cfg.state}. Quality work. On time. Guaranteed.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-background wp-element-button" style="background-color:{pc}" href="tel:{pd}">Call {phone}</a></div>
<!-- /wp:button -->

<!-- wp:button {{"className":"is-style-outline","style":{{"color":{{"text":"#ffffff"}},"border":{{"color":"#ffffff","width":"2px"}}}}}} -->
<div class="wp-block-button is-style-outline"><a class="wp-block-button__link has-text-color has-border-color wp-element-button" style="border-color:#ffffff;border-width:2px;color:#ffffff" href="/contact-us/">Get Free Quote</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:group --></div></div>
<!-- /wp:cover -->"""

    intro = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"70px","bottom":"50px"}}}}}},"layout":{{"type":"constrained","contentSize":"900px"}}}} -->
<div class="wp-block-group" style="padding-top:70px;padding-bottom:50px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"typography":{{"textTransform":"uppercase","fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center" style="font-weight:800;text-transform:uppercase">What We Offer</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"16px","lineHeight":"1.85"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#555555;font-size:16px;line-height:1.85">We provide a full range of professional services for homeowners and businesses throughout {cfg.city} and the surrounding {cfg.state} area. Each project is handled by experienced professionals using quality materials, and backed by our satisfaction guarantee. Whether it's a small repair or a major installation, we deliver results that last.</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->"""

    # Services card grid — one wp:group "card" per deployed service page.
    cards = []
    for idx, svc in enumerate(service_pages):
        title = svc.get("service", "")
        link = svc.get("link", "#")
        excerpt = svc.get("excerpt", "")
        img = svc.get("hero_url", "") or _FALLBACK_IMGS[idx % len(_FALLBACK_IMGS)]
        cards.append(f"""<!-- wp:group {{"style":{{"border":{{"width":"1px","color":"#e5e5e5"}},"color":{{"background":"#ffffff"}},"spacing":{{"padding":{{"top":"0","bottom":"24px","left":"0","right":"0"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group has-border-color has-background" style="border-color:#e5e5e5;border-width:1px;background-color:#ffffff;padding-top:0;padding-right:0;padding-bottom:24px;padding-left:0"><!-- wp:image {{"sizeSlug":"large"}} -->
<figure class="wp-block-image size-large"><img src="{img}" alt="{title}"/></figure>
<!-- /wp:image -->

<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"20px","bottom":"0","left":"24px","right":"24px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group" style="padding-top:20px;padding-right:24px;padding-bottom:0;padding-left:24px"><!-- wp:heading {{"level":2,"style":{{"typography":{{"fontSize":"17px","lineHeight":"1.3"}}}}}} -->
<h2 class="wp-block-heading" style="font-size:17px;line-height:1.3">{title}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#666666"}},"typography":{{"fontSize":"14px","lineHeight":"1.7"}}}}}} -->
<p class="has-text-color" style="color:#666666;font-size:14px;line-height:1.7">{excerpt}</p>
<!-- /wp:paragraph -->

<!-- wp:buttons -->
<div class="wp-block-buttons"><!-- wp:button {{"className":"is-style-outline","style":{{"color":{{"text":"{pc}"}},"border":{{"color":"{pc}","width":"2px"}},"typography":{{"fontSize":"13px","textTransform":"uppercase"}}}}}} -->
<div class="wp-block-button is-style-outline"><a class="wp-block-button__link has-text-color has-border-color has-custom-font-size wp-element-button" style="border-color:{pc};border-width:2px;color:{pc};font-size:13px;text-transform:uppercase" href="{link}">Learn More →</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:group --></div>
<!-- /wp:group -->""")

    cards_grid = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"bottom":"70px"}},"blockGap":"28px"}}}},"layout":{{"type":"constrained","contentSize":"1200px"}}}} -->
<div class="wp-block-group" style="padding-bottom:70px"><!-- wp:group {{"style":{{"spacing":{{"blockGap":"28px"}}}},"layout":{{"type":"grid","columnCount":3}}}} -->
<div class="wp-block-group">
{chr(10).join(cards)}
</div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    process = f"""<!-- wp:group {{"style":{{"color":{{"background":"#f8f8f8"}},"spacing":{{"padding":{{"top":"70px","bottom":"70px"}}}}}},"layout":{{"type":"constrained","contentSize":"1100px"}}}} -->
<div class="wp-block-group has-background" style="background-color:#f8f8f8;padding-top:70px;padding-bottom:70px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"typography":{{"textTransform":"uppercase","fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center" style="font-weight:800;text-transform:uppercase">Our Process</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#555555"}},"spacing":{{"margin":{{"bottom":"48px"}}}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#555555;margin-bottom:48px">Simple steps from first call to finished job.</p>
<!-- /wp:paragraph -->

<!-- wp:group {{"style":{{"spacing":{{"blockGap":"24px"}}}},"layout":{{"type":"grid","columnCount":4}}}} -->
<div class="wp-block-group">
{chr(10).join(_process_steps(pc))}
</div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    why_us = f"""<!-- wp:group {{"style":{{"color":{{"background":"{dc}"}},"spacing":{{"padding":{{"top":"70px","bottom":"70px"}}}}}},"layout":{{"type":"constrained","contentSize":"1200px"}}}} -->
<div class="wp-block-group has-background" style="background-color:{dc};padding-top:70px;padding-bottom:70px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"textTransform":"uppercase","fontWeight":"800"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-weight:800;text-transform:uppercase">Why {cfg.city} Chooses {cfg.business_name}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"spacing":{{"margin":{{"bottom":"32px"}}}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;margin-bottom:32px">Built on quality, honesty, and results.</p>
<!-- /wp:paragraph -->

<!-- wp:group {{"style":{{"spacing":{{"blockGap":"32px"}}}},"layout":{{"type":"grid","columnCount":3}}}} -->
<div class="wp-block-group">
{chr(10).join(_stats(pc))}
</div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    cta = f"""<!-- wp:group {{"align":"full","style":{{"color":{{"background":"{pc}"}},"spacing":{{"padding":{{"top":"70px","bottom":"70px","left":"24px","right":"24px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group alignfull has-background" style="background-color:{pc};padding-top:70px;padding-right:24px;padding-bottom:70px;padding-left:24px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"textTransform":"uppercase"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;text-transform:uppercase">Ready to Get Started in {cfg.city}?</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff">Call us today for a free, no-obligation estimate. We proudly serve {cfg.city} and surrounding {cfg.state} communities.</p>
<!-- /wp:paragraph -->

<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"#ffffff","text":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-text-color has-background wp-element-button" style="color:{pc};background-color:#ffffff" href="tel:{pd}">Call {phone}</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:group -->"""

    return "\n\n".join([reset_css, hero, intro, cards_grid, process, why_us, cta])


def _process_steps(pc: str) -> list[str]:
    steps = [
        ("1", "Free Consultation", "Tell us about your project and we'll walk you through your options at no cost."),
        ("2", "On-Site Assessment", "We visit your property, take measurements, and evaluate the scope of work."),
        ("3", "Detailed Estimate", "You receive a clear, itemized quote with no hidden fees or surprise charges."),
        ("4", "Expert Execution", "Our crew gets to work and keeps you updated every step of the way."),
    ]
    out = []
    for num, title, body in steps:
        out.append(f"""<!-- wp:group {{"style":{{"spacing":{{"blockGap":"8px"}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:paragraph {{"align":"center","style":{{"color":{{"background":"{pc}","text":"#ffffff"}},"typography":{{"fontSize":"20px","fontWeight":"800"}},"border":{{"radius":"50%"}},"spacing":{{"padding":{{"top":"0","right":"0","bottom":"0","left":"0"}}}}}}}} -->
<p class="has-text-align-center has-text-color has-background" style="background-color:{pc};border-radius:50%;color:#ffffff;font-size:20px;font-weight:800;padding-top:0;padding-right:0;padding-bottom:0;padding-left:0;width:52px;height:52px;line-height:52px;margin:0 auto">{num}</p>
<!-- /wp:paragraph -->

<!-- wp:heading {{"textAlign":"center","level":3,"style":{{"typography":{{"fontSize":"15px","textTransform":"uppercase"}}}}}} -->
<h3 class="wp-block-heading has-text-align-center" style="font-size:15px;text-transform:uppercase">{title}</h3>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#666666"}},"typography":{{"fontSize":"13px","lineHeight":"1.6"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#666666;font-size:13px;line-height:1.6">{body}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->""")
    return out


def _stats(pc: str) -> list[str]:
    stats = [("850+", "Projects Completed"), ("15+", "Years Experience"), ("100%", "Satisfaction Rate")]
    out = []
    for num, label in stats:
        out.append(f"""<!-- wp:group {{"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group"><!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"52px","fontWeight":"800","lineHeight":"1"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:{pc};font-size:52px;font-weight:800;line-height:1">{num}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"13px","textTransform":"uppercase"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:13px;text-transform:uppercase">{label}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group -->""")
    return out


def build_services_hub_payload(cfg: DeployConfig, service_pages: list[dict], hero_img: dict | None = None) -> dict:
    return {
        "title": "Services",
        "slug": "services",
        "content": build_services_hub(cfg, service_pages, hero_img),
        "status": "publish",
        "meta": {
            "_astra-site-sidebar-layout": "no-sidebar",
            "site-post-title": "disabled",
        },
    }
