# A multi-state lead pipeline with pre-send gates

**Type:** client project, code and data private. **Skills shown:** Playwright scraping, data normalisation, email campaign automation (Brevo API), guard-rail design, measurement discipline.

## Situation

A company recruiting licence holders (contractors and other licensed professionals) across many US states needed a steady stream of cold outreach: find who holds a licence in each state, get a working email, and enrol them in the right campaign at a deliverability-safe daily rate.

## Shape of the system

- **Per-state scrapers** produce raw rosters. States publish licence data in very different ways (bulk dumps, search portals, captcha-gated sites), so each scraper is hand-built for its source.
- **One compile step** normalises every state into a common schema and separates rows into enriched, not enriched and already pushed.
- **Push scripts** run nightly through a scheduler, sharing one core so a fix to send logic lands everywhere at once.
- **A manifest-driven campaign kit** wires a new multi-trade campaign from a manifest file and a copy file instead of forking a script per campaign.

## The gates I added

Each gate exists because something went wrong once.

- **Render gate.** An early version of a push script sent emails with an empty greeting. Every push script now refuses to send when any merge field would render empty, and copy is rendered only through shared functions for greetings and trade names.
- **Email validity and collision gates.** Rows are checked for a usable address, for already being in another pipeline, and for two campaigns sharing one inbox domain.
- **Sender caps per domain.** Capacity on a shared sending domain is capped explicitly, so adding a mailbox cannot quietly overrun a domain's safe volume.

## The measurement lesson

Headline numbers kept collapsing under a direct check, several sessions running. A figure that looked healthy turned out to be an artefact of how it was measured. The response was structural, not another correction: supply is measured by three separate artefacts that share one classifier set and are deliberately never reconciled with each other, because they answer different questions (what can be sent now versus what is owned at all). One generated status file is the only place a supply number is quoted.

## Result

A working outreach pipeline across a large number of states, with new sources wired as they were scraped and the send side protected by gates instead of memory. I have left counts and volumes out on purpose, since those belong to the client.

## What I would point to

Treating a surprising number as a bug report on my own measuring, and building the check that would have caught it.
