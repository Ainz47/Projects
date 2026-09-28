"""The Upwork copy of the portfolio page must match its source and carry no contact details."""
import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_work_page as b  # noqa: E402


class WorkPage(unittest.TestCase):
    def setUp(self):
        self.source = b.SOURCE.read_text(encoding="utf-8")
        self.committed = b.TARGET.read_text(encoding="utf-8").replace("\r\n", "\n")

    def test_committed_copy_matches_the_main_page(self):
        self.assertEqual(self.committed, b.build(self.source),
                         "docs/work/index.html is stale: run py tools/build_work_page.py")

    def test_no_contact_details(self):
        for marker in b.CONTACT_MARKERS:
            self.assertNotIn(marker, self.committed)

    def test_footer_points_at_upwork(self):
        self.assertIn("message me here on Upwork", self.committed)

    def test_relative_links_climb_out_of_work_folder(self):
        relative = re.findall(r'(?:href|src)="(?!https?:|#)([^"]+)"', self.committed)
        self.assertTrue(relative, "expected the demo links to be present")
        for link in relative:
            self.assertTrue(link.startswith("../"), link)

    def test_build_refuses_when_the_markup_it_edits_is_gone(self):
        # If the Email link is reworded on the main page, the build must stop, not ship it.
        changed = self.source.replace('">Email</a>', '">Mail me</a>')
        with self.assertRaises(ValueError):
            b.build(changed)


if __name__ == "__main__":
    unittest.main()
