import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "make" / "order-stock-sync.blueprint.json"

SECRET_PATTERNS = {
    "google_api_key": r"AIza[0-9A-Za-z_-]{20,}",
    "sk_key": r"\bsk-[A-Za-z0-9_-]{20,}",
    "bearer_token": r"Bearer [A-Za-z0-9._-]{20,}",
    "github_token": r"gh[pousr]_[A-Za-z0-9]{20,}",
    "github_fine_grained": r"github_pat_[A-Za-z0-9_]{20,}",
    "airtable_token": r"\bpat[A-Za-z0-9]{14}\.[a-f0-9]{32,}",
    "shopify_client_secret": r"\bshpss_[a-f0-9]{20,}",
    "email_address": r"[A-Za-z0-9._%+-]+@(?!example\.com\b)[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "windows_user_path": r"[A-Za-z]:\\+Users",
}


class MakeBlueprintTests(unittest.TestCase):
    def test_the_blueprint_exists_and_parses(self):
        self.assertTrue(FILE.exists(), "export the Make scenario before running this test (Task 6, Step 3)")
        json.loads(FILE.read_text(encoding="utf-8"))

    def test_it_has_a_webhook_trigger_and_the_github_dispatch_call(self):
        text = FILE.read_text(encoding="utf-8")
        self.assertIn('"gateway:CustomWebHook"', text)
        self.assertIn("api.github.com/repos/Ainz47/Projects/dispatches", text)
        # Shopify stock lookups go through Make's native Shopify app (a connection
        # reference), not a hand-typed client-credentials HTTP flow, so there is no
        # myshopify.com/admin/oauth/access_token URL to check for here.
        self.assertIn('"shopify:makeAnApiCall"', text)

    def test_the_github_token_is_not_a_literal(self):
        # The dispatch module's Authorization header must reference the
        # datastore:GetRecord lookup (module id 7), never a typed-in token value.
        text = FILE.read_text(encoding="utf-8")
        self.assertIn('"Bearer {{7.value}}"', text)
        self.assertIn('"datastore:GetRecord"', text)

    def test_the_github_dispatch_call_retries_on_transient_failure(self):
        # The GitHub dispatch call hit an intermittent BundleValidationError in
        # live testing (2026-09-21) that resolved on an identical replay with no
        # config change, confirming it was a transient upstream blip rather than
        # a structural bug. A Retry directive on module 8 means a future blip
        # self-heals instead of auto-deactivating the whole scenario.
        blueprint = json.loads(FILE.read_text(encoding="utf-8"))
        dispatch = next(m for m in blueprint["flow"] if m["id"] == 8)
        self.assertEqual(dispatch["module"], "http:ActionSendData")
        onerror = dispatch.get("onerror", [])
        self.assertTrue(
            any(h["module"] == "builtin:Break" and h["mapper"].get("retry") for h in onerror),
            "module 8 should retry automatically on failure (builtin:Break)",
        )

    def test_no_secrets_anywhere_in_the_export(self):
        text = FILE.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), f"looks like a {label}")


if __name__ == "__main__":
    unittest.main()
