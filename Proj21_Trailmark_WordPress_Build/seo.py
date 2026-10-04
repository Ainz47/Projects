"""Per-page SEO for Trailmark through Yoast SEO's own bulk-editor REST route
(/yoast/v1/bulk_editor/update_search), which writes the title and description into Yoast's
indexables. EMCP update-post refuses Yoast's protected `_yoast_wpseo_*` meta keys.
Yoast must have built its indexables first (indexing/* routes, done once on 2026-10-04).

  py seo.py apply     -> write titles and descriptions
  py seo.py check     -> fetch each live page and print <title>, description, robots

Cart, checkout and my-account are noindexed by Yoast's WooCommerce integration itself (checked by `check`).
Titles stay under ~60 characters and descriptions under ~155, no em dashes.
"""
import re
import sys

import requests

from wp_api import BASE, SESSION

# post id: (path, title, description). Title None = keep Yoast's "%title% %sep% %sitename%" default.
PAGES = {
    10: ("/", "Trailmark: see which new accounts are stuck in onboarding",
         "Trailmark turns onboarding into a checklist for every new account and puts an account on hold "
         "the day a step stalls, so your team calls the right customer."),
    16: ("/product/", "Trailmark product: checklist, account cards, hold list",
         "One card per new account, one checklist they all work through, and a hold list each morning "
         "that names the account, the step and how long it has waited."),
    52: ("/for-cs-teams/", "Trailmark for customer success teams",
         "Start each day with the hold list: which new accounts stalled, on which step, and for how long. "
         "Call the right account before it goes quiet."),
    57: ("/for-implementation/", "Trailmark for implementation teams",
         "Track setup that runs over several calls and waits on the customer. See who each step is waiting on "
         "and hand off to CS when the card is clear."),
    59: ("/for-revops/", "Trailmark for RevOps",
         "Read onboarding risk by step instead of one activation number. Agree one checklist across teams and "
         "flag accounts before renewal does."),
    139: ("/about/", "About Trailmark: a checklist, not a score",
          "Why Trailmark tracks named onboarding steps instead of a health score, and how this demo site was "
          "built with WordPress, Elementor and WooCommerce."),
    142: ("/onboarding-checklist/", "How to write an onboarding checklist in six steps",
          "Write a milestone checklist for new accounts: describe a working account, break it into milestones, "
          "set time limits, name owners and work the hold list."),
    145: ("/book-a-demo/", "Book a Trailmark demo",
          "Thirty minutes on a call. Bring your onboarding steps and a few recent signups, and see which "
          "accounts would be on hold today."),
    147: ("/contact/", "Contact Trailmark",
          "Questions about Trailmark, this demo or how it was built. Messages go to the person who built it "
          "and get a reply within one working day."),
    156: ("/resources/", "Onboarding templates and notes - Trailmark",
          "A free printable onboarding checklist template and short notes on running onboarding by "
          "milestone, with or without Trailmark."),
    155: ("/notes/", "Notes on running onboarding by milestone - Trailmark",
          "Short pieces on onboarding milestones: picking time limits, milestones versus health scores, "
          "and working a hold list."),
    153: ("/milestones-or-health-score/", None,
          "A health score says something is wrong somewhere. A milestone says which step, for which account, "
          "since when. Here is when each one earns its place."),
    154: ("/milestone-time-limits/", None,
          "The time limit is what turns a slow account into a held one. Set it from your own healthy accounts, "
          "not from a target, and revisit it after a month."),
    129: ("/shop/", "Shop: free onboarding checklist template - Trailmark",
          "Download the Trailmark onboarding checklist template: a two-page printable worksheet with a "
          "milestones table, account cards and a hold list. Free."),
    136: ("/product/onboarding-checklist-template/", "Free onboarding checklist template (PDF) - Trailmark",
          "A two-page printable worksheet: list your onboarding milestones with time limits, keep one card "
          "per new account, and work the hold list each morning."),
}
NOINDEX = {130: "/cart/", 131: "/checkout/", 132: "/my-account/"}


def apply():
    items = []
    for pid, (_, title, desc) in PAGES.items():
        item = {"id": pid, "meta_description": desc}
        if title:
            item["seo_title"] = title
        items.append(item)
    r = SESSION.post(f"{BASE}/wp-json/yoast/v1/bulk_editor/update_search", json={"items": items}, timeout=120)
    r.raise_for_status()
    for res in r.json()["results"]:
        print(res["id"], "ok" if res["success"] else f"FAILED {res}")


def check():
    for path in [p for p, *_ in PAGES.values()] + list(NOINDEX.values()):
        html = requests.get(BASE + path, params={"nc": "1"}, timeout=60).text
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        desc = re.search(r'<meta name="description" content="([^"]*)"', html)
        robots = re.search(r"<meta name=['\"]robots['\"] content=['\"]([^'\"]*)", html)
        print(f"{path}\n  title: {title and title.group(1)}\n  desc:  {desc and desc.group(1)[:90]}\n  robots: {robots and robots.group(1)}")


if __name__ == "__main__":
    {"apply": apply, "check": check}[sys.argv[1]]()
