"""Minify trailmark.css into the <style id='tm-css'> blob pasted into each page's HTML widget.

trailmark.css is the source of truth; the inline copies are generated, never hand-edited.
Output: tm-css.min.html next to this script.
"""
import re
from pathlib import Path

here = Path(__file__).parent
css = (here / "trailmark.css").read_text(encoding="utf-8")
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)        # comments
css = re.sub(r"\s+", " ", css)                         # whitespace runs
css = re.sub(r"\s*([{}:;,>])\s*", r"\1", css)          # around punctuation
css = css.replace(";}", "}").replace('"', "'").strip()
# keep the space in descendant selectors like ".tm-on-ink :focus-visible"
css = css.replace(".tm-on-ink:focus-visible", ".tm-on-ink :focus-visible")
(here / "tm-css.min.html").write_text(f"<style id='tm-css'>{css}</style>", encoding="utf-8")
print(len(css), "bytes")
