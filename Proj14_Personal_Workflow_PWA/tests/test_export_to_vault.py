import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from export_to_vault import decide  # noqa: E402
from vault_render import GENERATED_MARKER  # noqa: E402

GENERATED = f"# Schedule\n\n{GENERATED_MARKER}\n> Last rendered: 2026-08-17T05:00:00\n\nbody\n"
SAME_LATER = f"# Schedule\n\n{GENERATED_MARKER}\n> Last rendered: 2026-08-17T23:00:00\n\nbody\n"
CHANGED = f"# Schedule\n\n{GENERATED_MARKER}\n> Last rendered: 2026-08-17T05:00:00\n\nother\n"
HAND_WRITTEN = "# Schedule\n\nMy own notes about the week.\n"


class TestDecide(unittest.TestCase):
    def test_missing_file_is_written(self):
        action, _ = decide(None, GENERATED)
        self.assertEqual(action, "write")

    def test_identical_content_is_skipped(self):
        action, _ = decide(GENERATED, GENERATED)
        self.assertEqual(action, "skip")

    def test_only_the_timestamp_differing_is_skipped(self):
        # The whole point of comparable(): otherwise every run rewrites the note.
        action, _ = decide(GENERATED, SAME_LATER)
        self.assertEqual(action, "skip")

    def test_changed_body_is_written(self):
        action, _ = decide(GENERATED, CHANGED)
        self.assertEqual(action, "write")

    def test_hand_written_file_is_refused_not_overwritten(self):
        action, reason = decide(HAND_WRITTEN, GENERATED)
        self.assertEqual(action, "refuse")
        self.assertIn("not generated", reason)

    def test_empty_existing_file_is_written(self):
        action, _ = decide("", GENERATED)
        self.assertEqual(action, "write")


if __name__ == "__main__":
    unittest.main()
