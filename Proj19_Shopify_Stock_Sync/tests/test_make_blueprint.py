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

    def _flow(self):
        return json.loads(FILE.read_text(encoding="utf-8"))["flow"]

    def test_the_webhook_is_hmac_verified_before_any_work(self):
        # Shopify signs the raw body (base64 HMAC-SHA256, app secret). The webhook
        # runs in JSON pass-through so 1.value is the raw string; the secret comes
        # from the data store (module 10), and only a matching signature reaches
        # the Parse JSON step (module 11) that everything else reads from.
        flow = self._flow()
        self.assertEqual([m["id"] for m in flow[:3]], [1, 10, 11])
        secret = flow[1]
        self.assertEqual(secret["module"], "datastore:GetRecord")
        self.assertEqual(secret["mapper"]["key"], "shopify_webhook_secret")
        parse = flow[2]
        self.assertEqual(parse["module"], "json:ParseJSON")
        self.assertEqual(parse["mapper"]["json"], "{{1.value}}")
        check = json.dumps(parse["filter"])
        self.assertIn('sha256(1.value; \\"base64\\"; 10.value)', check)
        self.assertIn("x-shopify-hmac-sha256", check)

    def test_line_items_come_from_the_verified_body(self):
        feeder = next(m for m in self._flow() if m["id"] == 2)
        self.assertEqual(feeder["mapper"]["array"], "{{11.line_items}}")

    def test_stock_is_picked_by_exact_sku_not_the_first_search_hit(self):
        # sku:"X" is a loose Shopify search; nodes[1] could be another variant.
        text = FILE.read_text(encoding="utf-8")
        self.assertNotIn("nodes[1]", text)
        update = next(m for m in self._flow() if m["id"] == 5)
        self.assertIn('"sku"; 2.sku', update["mapper"]["record"]["fldOKzR4V97mX3pj2"])
        # exactly one variant with that SKU, or no write (missing or ambiguous)
        self.assertIn("length(map(", json.dumps(update["filter"]))

    def test_the_catalog_refresh_is_dispatched_once_per_order(self):
        # Option A: aggregate the changed line items, dispatch once if any changed.
        ids = [m["id"] for m in self._flow()]
        agg = next(m for m in self._flow() if m["id"] == 12)
        self.assertEqual(agg["module"], "builtin:BasicAggregator")
        self.assertEqual(agg["parameters"]["feeder"], 2)
        self.assertLess(ids.index(6), ids.index(12))
        self.assertLess(ids.index(12), ids.index(7))
        token = next(m for m in self._flow() if m["id"] == 7)
        self.assertIn("length(12.array)", json.dumps(token["filter"]))

    def test_modules_carry_the_defaults_make_requires_at_run_time(self):
        # A blueprint import drops any parameter the export left out, and Make
        # then fails the module with BundleValidationError (seen live 2026-10-18
        # on both data store lookups and on the GitHub dispatch call).
        flow = {m["id"]: m for m in self._flow()}
        for mid in (7, 10):
            self.assertIn("returnWrapped", flow[mid]["mapper"], f"module {mid}")
        for key in ("serializeUrl", "shareCookies", "rejectUnauthorized", "followRedirect",
                    "useQuerystring", "gzip", "useMtls"):
            self.assertIn(key, flow[8]["mapper"], f"module 8 needs {key}")
        self.assertTrue(flow[8]["mapper"]["rejectUnauthorized"], "TLS verification must stay on")

    def test_no_secrets_anywhere_in_the_export(self):
        text = FILE.read_text(encoding="utf-8")
        for label, pattern in SECRET_PATTERNS.items():
            self.assertIsNone(re.search(pattern, text), f"looks like a {label}")


if __name__ == "__main__":
    unittest.main()
