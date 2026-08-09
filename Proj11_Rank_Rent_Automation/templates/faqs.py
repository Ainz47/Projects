"""
faqs.py — FAQ page builder (native Gutenberg blocks, v2).
Hero (cover) + an accordion of native wp:details blocks (one per Q&A —
exactly matches the block's intended use, fully editable per-question in the
block editor) + bottom CTA.
"""
import re
from src.config import DeployConfig


def _phone_digits(phone: str) -> str:
    return re.sub(r"\D", "", phone)


def build_faqs_page(cfg: DeployConfig, content: dict, hero_img: dict | None = None) -> str:
    pc = cfg.primary_color
    faqs = content.get("faqs", [])
    fallback = "https://images.pexels.com/photos/1108101/pexels-photo-1108101.jpeg"
    img_url = (hero_img or {}).get("url", "") or fallback
    pd = _phone_digits(cfg.phone)

    reset_css = f"""<!-- wp:html -->
<style>
.entry-title,.entry-header,.ast-page-title-area{{display:none!important;margin:0!important;padding:0!important}}
body{{overflow-x:hidden}}
.entry-content,.ast-article-single,.ast-article-post{{padding:0!important;margin-top:0!important}}
.ast-container,.content-area,.site-main,.ast-article-single,.wp-block-html{{overflow:visible!important}}
.entry-content[data-ast-blocks-layout]>*{{max-width:none!important}}
.wp-block-html:first-child{{margin-top:0!important;margin-bottom:0!important}}
.wp-block-details{{border-top:none!important;border-left:none!important;border-right:none!important;outline:none!important}}
.wp-block-details summary{{cursor:pointer;font-size:18px;font-weight:700;color:#1a1a1a;list-style:none;outline:none;padding-left:26px;position:relative}}
.wp-block-details summary::-webkit-details-marker{{display:none}}
.wp-block-details summary::before{{content:"+";color:{pc};font-weight:800;position:absolute;left:0;top:0}}
.wp-block-details[open] summary::before{{content:"−"}}
.wp-block-details:focus,.wp-block-details summary:focus{{outline:none!important;box-shadow:none!important}}
</style>
<!-- /wp:html -->"""

    hero = f"""<!-- wp:cover {{"url":"{img_url}","dimRatio":60,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-60 has-background-dim"></span><img class="wp-block-cover__image-background" src="{img_url}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"100px","bottom":"100px"}}}}}},"layout":{{"type":"constrained","contentSize":"700px"}}}} -->
<div class="wp-block-group" style="padding-top:100px;padding-bottom:100px"><!-- wp:heading {{"textAlign":"center","level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"clamp(28px, 4vw, 48px)","fontWeight":"800","textTransform":"uppercase"}}}}}} -->
<h1 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:clamp(28px, 4vw, 48px);font-weight:800;text-transform:uppercase">Frequently Asked Questions</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"17px"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:17px">Everything you need to know about our services in {cfg.city}, {cfg.state}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group --></div></div>
<!-- /wp:cover -->"""

    items = []
    for faq in faqs:
        question = faq.get("question", "")
        answer = faq.get("answer", "")
        items.append(f"""<!-- wp:details {{"showContent":false,"style":{{"spacing":{{"padding":{{"top":"28px","bottom":"28px"}}}},"border":{{"bottom":{{"color":"#efefef","width":"1px"}}}}}}}} -->
<details class="wp-block-details has-border-color" style="border-bottom-color:#efefef;border-bottom-width:1px;padding-top:28px;padding-bottom:28px"><summary>{question}</summary><!-- wp:paragraph {{"style":{{"color":{{"text":"#555555"}},"typography":{{"fontSize":"15px","lineHeight":"1.75"}}}}}} -->
<p class="has-text-color" style="color:#555555;font-size:15px;line-height:1.75">{answer}</p>
<!-- /wp:paragraph --></details>
<!-- /wp:details -->""")

    faq_list = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"60px","bottom":"60px"}}}}}},"layout":{{"type":"constrained","contentSize":"820px"}}}} -->
<div class="wp-block-group" style="padding-top:60px;padding-bottom:60px">
{chr(10).join(items)}
</div>
<!-- /wp:group -->"""

    cta = f"""<!-- wp:group {{"align":"full","style":{{"color":{{"background":"{pc}"}},"spacing":{{"padding":{{"top":"60px","bottom":"60px","left":"40px","right":"40px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group alignfull has-background" style="background-color:{pc};padding-top:60px;padding-right:40px;padding-bottom:60px;padding-left:40px"><!-- wp:heading {{"textAlign":"center","level":2,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"28px","fontWeight":"800","textTransform":"uppercase"}}}}}} -->
<h2 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:28px;font-weight:800;text-transform:uppercase">Still Have Questions? Call Us!</h2>
<!-- /wp:heading -->

<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->
<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"#ffffff","text":"{pc}"}}}}}} -->
<div class="wp-block-button"><a class="wp-block-button__link has-text-color has-background wp-element-button" style="color:{pc};background-color:#ffffff" href="tel:{pd}">{cfg.phone}</a></div>
<!-- /wp:button --></div>
<!-- /wp:buttons --></div>
<!-- /wp:group -->"""

    return "\n\n".join([reset_css, hero, faq_list, cta])


def build_faqs_payload(cfg: DeployConfig, content: dict, hero_img: dict | None = None) -> dict:
    return {
        "title": "FAQs",
        "slug": "faqs",
        "content": build_faqs_page(cfg, content, hero_img),
        "status": "publish",
        "meta": {"_astra-site-sidebar-layout": "no-sidebar", "site-post-title": "disabled"},
    }
