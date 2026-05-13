"""Gemini API diagnostics for the rank_rent_automation demo.

Runs a series of increasingly realistic calls so billing/model/quota failures
can be separated from prompt or pipeline bugs.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai


ROOT = Path(__file__).resolve().parents[1]
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")


def summarize_error(exc: Exception) -> str:
    text = str(exc).replace("\n", " ")
    return text[:500]


def run_case(client, model: str, name: str, prompt: str) -> tuple[bool, str]:
    print(f"\n--- {name} | {model} ---")
    started = time.perf_counter()
    try:
        response = client.models.generate_content(model=model, contents=prompt)
        elapsed = time.perf_counter() - started
        text = (response.text or "").strip()
        print(f"PASS {elapsed:.1f}s | chars={len(text)} | sample={text[:120]!r}")
        return True, text
    except Exception as exc:
        elapsed = time.perf_counter() - started
        print(f"FAIL {elapsed:.1f}s | {summarize_error(exc)}")
        return False, summarize_error(exc)


def main() -> int:
    api_key = os.getenv("GEMINI_API_KEY")
    configured_model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    print("Gemini diagnostics")
    print(f"time={datetime.now().isoformat(timespec='seconds')}")
    print(f"key_present={bool(api_key)}")
    print(f"key_suffix={api_key[-4:] if api_key else 'NONE'}")
    print(f"configured_model={configured_model}")

    if not api_key:
        print("No GEMINI_API_KEY found in .env")
        return 1

    client = genai.Client(api_key=api_key)

    models = [
        configured_model,
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
    ]
    models = list(dict.fromkeys(models))

    cases = [
        ("tiny", "Reply with OK only."),
        (
            "small_json",
            'Return only valid JSON: {"status":"ok","title":"test","items":["a","b"]}',
        ),
        (
            "medium_copy",
            "Write one concise 120 word paragraph about stamped concrete patios in Farmington Hills, MI. "
            "Mention Heritage Park and Orchard Lake Road.",
        ),
        (
            "seo_json_short",
            "Return only JSON with keys title_tag, meta_description, h1, slug, content_html. "
            "Topic: Stamped Concrete Patios in Farmington Hills, MI. "
            "content_html should be about 250 words and mention Heritage Park and Orchard Lake Road.",
        ),
        (
            "seo_json_large",
            "Return only JSON with keys title_tag, meta_description, h1, slug, content_html, "
            "landmark_references, keyword_count_estimate. Topic: Stamped Concrete Patios in "
            "Farmington Hills, MI. content_html should be 800+ words of semantic HTML with H2, H3, "
            "and bullets. Mention Heritage Park and Orchard Lake Road. Mention Stamped Concrete "
            "Patios at least 5 times.",
        ),
    ]

    any_passed = False
    for model in models:
        for name, prompt in cases:
            passed, _ = run_case(client, model, name, prompt)
            any_passed = any_passed or passed
            time.sleep(3)

    return 0 if any_passed else 1


if __name__ == "__main__":
    sys.exit(main())
