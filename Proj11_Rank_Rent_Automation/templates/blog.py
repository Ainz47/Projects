"""
blog.py — Blog listing page and individual post builder (both native Gutenberg).
Post bodies from Gemini are raw HTML; html_to_blocks() converts them to proper
wp:heading / wp:paragraph / wp:list blocks so content is fully editable in the
Gutenberg editor.
"""
import re
from src.config import DeployConfig

FALLBACK_THUMB = "https://images.pexels.com/photos/1108101/pexels-photo-1108101.jpeg?auto=compress&cs=tinysrgb&w=800"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return re.sub(r"-+", "-", text)


def build_blog_listing(cfg: DeployConfig, posts: list[dict], hero_img_url: str = "") -> str:
    pc = cfg.primary_color

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

    hero = f"""<!-- wp:cover {{"url":"{hero_img_url}","dimRatio":80,"overlayColor":"black","isUserOverlayColor":true,"align":"full"}} -->
<div class="wp-block-cover alignfull"><span aria-hidden="true" class="wp-block-cover__background has-black-background-color has-background-dim-80 has-background-dim"></span><img class="wp-block-cover__image-background" src="{hero_img_url}" data-object-fit="cover" alt=""/><div class="wp-block-cover__inner-container">
<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"100px","bottom":"100px"}}}}}},"layout":{{"type":"constrained","contentSize":"700px"}}}} -->
<div class="wp-block-group" style="padding-top:100px;padding-bottom:100px"><!-- wp:heading {{"textAlign":"center","level":1,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"clamp(28px, 4vw, 48px)","fontWeight":"800","textTransform":"uppercase"}}}}}} -->
<h1 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:clamp(28px, 4vw, 48px);font-weight:800;text-transform:uppercase">Blogs and Articles</h1>
<!-- /wp:heading -->

<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"17px"}}}}}} -->
<p class="has-text-align-center has-text-color" style="color:#ffffff;font-size:17px">Tips, guides, and local insights from {cfg.business_name}</p>
<!-- /wp:paragraph --></div>
<!-- /wp:group --></div></div>
<!-- /wp:cover -->"""

    cards = []
    for post in posts:
        thumb = (post.get("featured_image") or {}).get("url", "") or FALLBACK_THUMB
        title = post.get("title", "")
        excerpt = post.get("excerpt", "")
        excerpt = (excerpt[:140] + "...") if len(excerpt) > 140 else excerpt
        slug = post.get("slug", _slugify(title))
        cards.append(f"""<!-- wp:group {{"style":{{"border":{{"width":"1px","color":"#d8d8d8"}},"color":{{"background":"#ffffff"}},"spacing":{{"padding":{{"top":"0","bottom":"0","left":"0","right":"0"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group has-border-color has-background" style="border-color:#d8d8d8;border-width:1px;background-color:#ffffff;padding-top:0;padding-right:0;padding-bottom:0;padding-left:0"><!-- wp:image {{"sizeSlug":"large"}} -->
<figure class="wp-block-image size-large"><img src="{thumb}" alt="{title}"/></figure>
<!-- /wp:image -->

<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"24px","bottom":"24px","left":"24px","right":"24px"}}}}}},"layout":{{"type":"constrained"}}}} -->
<div class="wp-block-group" style="padding-top:24px;padding-right:24px;padding-bottom:24px;padding-left:24px"><!-- wp:heading {{"level":2,"style":{{"typography":{{"fontSize":"17px","lineHeight":"1.4"}}}}}} -->
<h2 class="wp-block-heading" style="font-size:17px;line-height:1.4">{title}</h2>
<!-- /wp:heading -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"#666666"}},"typography":{{"fontSize":"14px","lineHeight":"1.6"}}}}}} -->
<p class="has-text-color" style="color:#666666;font-size:14px;line-height:1.6">{excerpt}</p>
<!-- /wp:paragraph -->

<!-- wp:paragraph {{"style":{{"color":{{"text":"{pc}"}},"typography":{{"fontSize":"13px","fontWeight":"700","textTransform":"uppercase","letterSpacing":"1px"}}}}}} -->
<p class="has-text-color" style="color:{pc};font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1px"><a href="/{slug}/" style="color:{pc}">Read More →</a></p>
<!-- /wp:paragraph --></div>
<!-- /wp:group --></div>
<!-- /wp:group -->""")

    grid = f"""<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"60px","bottom":"60px"}},"blockGap":"28px"}}}},"layout":{{"type":"constrained","contentSize":"1100px"}}}} -->
<div class="wp-block-group" style="padding-top:60px;padding-bottom:60px"><!-- wp:group {{"style":{{"spacing":{{"blockGap":"28px"}}}},"layout":{{"type":"grid","columnCount":3}}}} -->
<div class="wp-block-group">
{chr(10).join(cards)}
</div>
<!-- /wp:group --></div>
<!-- /wp:group -->"""

    return "\n\n".join([reset_css, hero, grid])


def build_blog_listing_payload(cfg: DeployConfig, posts: list[dict], hero_img: dict | None) -> dict:
    hero_url = (hero_img or {}).get("url", "")
    content = build_blog_listing(cfg, posts, hero_url)
    return {
        "title": "Blog",
        "slug": "blog",
        "content": content,
        "status": "publish",
        "meta": {"_astra-site-sidebar-layout": "no-sidebar"},
    }


_CTA_HEADING_RE = re.compile(
    r'<h[2-6][^>]*>\s*(?:ready to start|contact us|get a free|call us|get started)[^<]*</h[2-6]>',
    re.IGNORECASE,
)


def html_to_blocks(content_html: str, primary_color: str = "#ff5e14") -> str:
    """Convert Gemini-generated HTML body to native Gutenberg block markup."""
    # Trim any AI-generated CTA section at the end — build_post_payload appends its own
    for m in _CTA_HEADING_RE.finditer(content_html):
        content_html = content_html[:m.start()].rstrip()
        break

    blocks = []
    pattern = re.compile(
        r'<(h[2-6]|p|ul|ol)(?:\s[^>]*)?>(.+?)</\1>',
        re.DOTALL | re.IGNORECASE,
    )
    for m in pattern.finditer(content_html):
        tag = m.group(1).lower()
        inner = m.group(2).strip()
        if not inner:
            continue

        if tag == "h2":
            attrs = f'{{"level":2,"style":{{"color":{{"text":"{primary_color}"}},"typography":{{"fontSize":"26px","fontWeight":"800","lineHeight":"1.3"}}}}}}'
            blocks.append(
                f'<!-- wp:heading {attrs} -->\n'
                f'<h2 class="wp-block-heading has-text-color" style="color:{primary_color};font-size:26px;font-weight:800;line-height:1.3">{inner}</h2>\n'
                f'<!-- /wp:heading -->'
            )
        elif tag == "h3":
            blocks.append(
                f'<!-- wp:heading {{"level":3,"style":{{"typography":{{"fontSize":"19px","fontWeight":"700","lineHeight":"1.4"}}}}}} -->\n'
                f'<h3 class="wp-block-heading" style="font-size:19px;font-weight:700;line-height:1.4">{inner}</h3>\n'
                f'<!-- /wp:heading -->'
            )
        elif tag[0] == "h":
            level = int(tag[1])
            blocks.append(
                f'<!-- wp:heading {{"level":{level}}} -->\n'
                f'<{tag} class="wp-block-heading">{inner}</{tag}>\n'
                f'<!-- /wp:heading -->'
            )
        elif tag == "p":
            blocks.append(
                f'<!-- wp:paragraph {{"style":{{"typography":{{"fontSize":"16px","lineHeight":"1.8"}},"color":{{"text":"#555555"}}}}}} -->\n'
                f'<p class="has-text-color" style="color:#555555;font-size:16px;line-height:1.8">{inner}</p>\n'
                f'<!-- /wp:paragraph -->'
            )
        elif tag in ("ul", "ol"):
            li_items = re.findall(r'<li[^>]*>([\s\S]*?)</li>', inner, re.IGNORECASE)
            if li_items:
                ordered = ' {"ordered":true}' if tag == "ol" else ""
                items_markup = "".join(
                    f'<!-- wp:list-item --><li>{li.strip()}</li><!-- /wp:list-item -->'
                    for li in li_items
                )
                blocks.append(
                    f'<!-- wp:list{ordered} {{"style":{{"typography":{{"fontSize":"15px","lineHeight":"1.7"}},"color":{{"text":"#555555"}}}}}} -->\n'
                    f'<{tag} class="wp-block-list has-text-color" style="color:#555555;font-size:15px;line-height:1.7">{items_markup}</{tag}>\n'
                    f'<!-- /wp:list -->'
                )

    return "\n\n".join(blocks)


def build_post_payload(cfg: DeployConfig, post_content: dict, featured_image: dict | None) -> dict:
    title = post_content.get("title", "")
    slug = post_content.get("slug", _slugify(title))
    content_html = post_content.get("content_html", "")
    img_url = (featured_image or {}).get("url", "")
    img_id = (featured_image or {}).get("id")
    pc = cfg.primary_color
    dc = cfg.dark_color

    # Make single posts white + full-width (matches reference layout)
    # White body removes the gray side margins; narrow-container override widens the column
    width_reset = (
        '<!-- wp:html -->\n'
        '<style>'
        'body.single{background:#fff!important;overflow-x:hidden}'
        'body.single.ast-narrow-container .ast-container{max-width:1100px!important}'
        'body.single .entry-content,.single .ast-article-single,.single .ast-article-post{padding:0!important;margin-top:0!important}'
        '.single .ast-container,.single .content-area,.single .site-main,.single .ast-article-single,.single .wp-block-html{overflow:visible!important}'
        '.single .entry-content[data-ast-blocks-layout]>*{max-width:none!important}'
        '</style>\n'
        '<!-- /wp:html -->\n\n'
    )

    if img_url:
        id_attr = f',"id":{img_id}' if img_id else ""
        img_class = f" wp-image-{img_id}" if img_id else ""
        img_block = (
            f'<!-- wp:image {{"sizeSlug":"full","align":"wide"{id_attr},"linkDestination":"none"}} -->\n'
            f'<figure class="wp-block-image alignwide size-full">'
            f'<img src="{img_url}" alt="{title}" class="wp-block-image{img_class}"/>'
            f'</figure>\n<!-- /wp:image -->\n\n'
        )
    else:
        img_block = ""

    inner_blocks = html_to_blocks(content_html, pc)
    # Gemini always opens the body with an H2 repeating the post title — drop it
    # since Astra already renders the title above the content
    inner_blocks = re.sub(
        r'^<!-- wp:heading \{"level":2[^}]*\} -->\n[\s\S]*?\n<!-- /wp:heading -->\n*',
        '', inner_blocks, count=1
    ).lstrip()
    content_blocks = (
        f'<!-- wp:group {{"style":{{"spacing":{{"padding":{{"top":"48px","bottom":"48px"}},"blockGap":"24px"}}}},"layout":{{"type":"constrained","contentSize":"860px"}}}} -->\n'
        f'<div class="wp-block-group" style="padding-top:48px;padding-bottom:48px">\n'
        f'{inner_blocks}\n'
        f'</div>\n<!-- /wp:group -->'
    )

    cta_block = (
        f'\n\n<!-- wp:group {{"style":{{"color":{{"background":"{dc}"}},"spacing":{{"padding":{{"top":"56px","bottom":"56px"}}}}}},"layout":{{"type":"constrained","contentSize":"700px"}}}} -->\n'
        f'<div class="wp-block-group has-background" style="background-color:{dc};padding-top:56px;padding-bottom:56px">'
        f'<!-- wp:heading {{"textAlign":"center","level":3,"style":{{"color":{{"text":"#ffffff"}},"typography":{{"fontSize":"26px","fontWeight":"700"}}}}}} -->\n'
        f'<h3 class="wp-block-heading has-text-align-center has-text-color" style="color:#ffffff;font-size:26px;font-weight:700">Ready to Start Your Project in {cfg.city}?</h3>\n'
        f'<!-- /wp:heading -->\n\n'
        f'<!-- wp:paragraph {{"align":"center","style":{{"color":{{"text":"#cccccc"}},"typography":{{"fontSize":"16px"}}}}}} -->\n'
        f'<p class="has-text-align-center has-text-color" style="color:#cccccc;font-size:16px">Contact {cfg.business_name} today for a free estimate.</p>\n'
        f'<!-- /wp:paragraph -->\n\n'
        f'<!-- wp:buttons {{"layout":{{"type":"flex","justifyContent":"center"}}}} -->\n'
        f'<div class="wp-block-buttons"><!-- wp:button {{"style":{{"color":{{"background":"{pc}","text":"#ffffff"}},"typography":{{"fontWeight":"700","textTransform":"uppercase"}}}}}} -->\n'
        f'<div class="wp-block-button"><a class="wp-block-button__link has-text-color has-background wp-element-button" href="/contact/" style="background-color:{pc};color:#ffffff;font-weight:700;text-transform:uppercase">Get a Free Quote</a></div>\n'
        f'<!-- /wp:button --></div>\n'
        f'<!-- /wp:buttons --></div>\n'
        f'<!-- /wp:group -->'
    )

    payload = {
        "title": title,
        "slug": slug,
        "content": width_reset + img_block + content_blocks + cta_block,
        "status": "publish",
        "comment_status": "closed",
        "excerpt": post_content.get("meta_description", ""),
        "meta": {"_astra-site-sidebar-layout": "no-sidebar"},
    }
    if img_id:
        payload["featured_media"] = img_id
    return payload
