"""Build docs/og-card.png: the link-preview image for the portfolio page (og:image).

LinkedIn, Slack and chat apps only render a preview card when the page has Open Graph
tags, and LinkedIn's Featured "Add a link" refuses the URL without one. Colours match
the page's light theme; fonts are the page's own (Bricolage Grotesque, IBM Plex Mono),
passed in because they are not committed here.

    py tools/make_og_card.py <BricolageGrotesque[opsz,wdth,wght].ttf> <IBMPlexMono-Regular.ttf>
"""
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "og-card.png"
W, H, PAD = 1200, 627, 72
PAPER, INK, MUTED, LINE, CLEAR = "#edf1ee", "#10201c", "#566661", "#c9d3ce", "#1b7f5c"

HEADLINE = "Tell me what's slowing your team down. I'll build the fix."
KICKER = "JHURALD LANTAPE  /  BACK-END & AUTOMATION DEVELOPER"
STACK = "Python  ·  FastAPI  ·  n8n  ·  Make  ·  Claude Code  ·  APIs & integrations"
URL = "ainz47.github.io/Projects"


def display_font(path, size):
    font = ImageFont.truetype(path, size)
    try:
        want = {b"Optical size": min(size, 96), b"Width": 100, b"Weight": 700}
        axes = font.get_variation_axes()
        font.set_variation_by_axes([want.get(a.get("name"), a["default"]) for a in axes])
    except OSError:
        pass
    return font


def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=font) <= width:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line]


def main(display_path, mono_path):
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    mono = ImageFont.truetype(mono_path, 22)
    head = display_font(display_path, 76)

    d.rectangle([0, 0, 14, H], fill=CLEAR)
    d.text((PAD, PAD), KICKER, font=mono, fill=MUTED)

    y = PAD + 70
    for line in wrap(d, HEADLINE, head, W - 2 * PAD):
        d.text((PAD, y), line, font=head, fill=INK)
        y += 90

    d.line([PAD, H - PAD - 70, W - PAD, H - PAD - 70], fill=LINE, width=2)
    d.text((PAD, H - PAD - 44), STACK, font=mono, fill=INK)
    d.text((PAD, H - PAD - 8), URL, font=mono, fill=CLEAR)

    img.save(OUT, optimize=True)
    print(f"wrote {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
