# Shopify fixes and SEO tooling for a handmade-jewelry store

**Type:** client project, code private. **Skills shown:** Shopify Liquid, Admin GraphQL API, catalog QA, Google Search Console API, plain-language client reporting.

## Situation

A small handmade-jewelry brand ran on Shopify. Sold-out pieces were showing first on collection pages, the owner kept adding new products by hand, and the store had almost no search visibility work behind it.

## The sold-out problem

Several collections carried a smart-collection rule meant to hide sold-out items, and it was not filtering them. I confirmed through GraphQL that products with zero inventory were still coming back as collection members. On one collection, seventeen sold-out products sat above the first in-stock item.

That is a Shopify-side membership problem, not a theme bug, so it was not fixable from the theme. Since the owner wanted sold pieces to stay visible, just not first, I fixed the display instead of chasing the rule. A change to the collection section in Liquid renders available products first and pushes sold-out ones to the end of each page. It applies site-wide because every collection shares that one section. I verified it on the live storefront.

## Catalog QA through the Admin API

When the owner added three new products, I reviewed them against the catalog's conventions and fixed the gaps directly: title case, image alt text, backend SEO title and description following the site's existing pattern, and a missing materials metafield, filled from the owner's own wording rather than new copy. Anything that needed content only the owner had, like extra photos, I asked for instead of inventing.

## Search Console tooling

- A baseline script that snapshots 90-day search performance to a dated file, and a comparison between two snapshots.
- A sitemap submission script. The store had never registered a sitemap with Search Console. One detail that cost a failed run: the API needs the full sitemap URL as the feed path, not a relative path.
- A re-auth flow for the expired token.

## Result

The sold-out ordering was fixed and confirmed live. The comparison between baselines showed search impressions roughly doubling as more products and collection pages began appearing at all. The two snapshots overlap heavily, so I reported that as an early directional signal and did not claim more than that. The larger structured-data work is prepared but not yet applied to the live theme.

## What I would point to

Choosing the fix that matches what the owner wants instead of the fix that is technically purest, and keeping the client-facing message free of jargon while the technical report stays exact.
