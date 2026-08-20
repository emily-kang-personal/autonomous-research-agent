# Datapoint catalog — calendar-app competitor enrichment (13 fields)

Mirrors the client pattern: each field has a type, an authoritative public source, and a collection rule.
Three outcomes per field, never confused: `found`, `unreachable` (source exists but couldn't be read), `not_disclosed` (no public source states it). An invented value is a failed delivery.

**Per-datapoint envelope** (see `schema.json`): `{status, value?, source_url?, evidence_quote?, retrieved_at?, note?}`. A `found` field carries all of: `value`, `source_url`, `evidence_quote` (the exact ≤1-sentence text from the page that states it — a checkable handle, re-verified against the live page later), and `retrieved_at` (the tool-stamped `fetched_at` from `research_fetch`, never model-written). `unreachable`/`not_disclosed` carry only `status` + `note`. Independent verify verdicts live in a separate `results/<slug>.verify.json`, never merged into this file.

| # | Field | Type | Authoritative source | Collection rule |
|---|---|---|---|---|
| 1 | website | url | web search | Verify the official domain; homepage URL only |
| 2 | tagline | string | company homepage | Their own words from the homepage hero, verbatim |
| 3 | pricing_model | enum: free / freemium / paid_only / subscription | company /pricing page | From the official pricing page only |
| 4 | lowest_paid_price_usd | number | company /pricing page | Monthly USD price of cheapest paid tier; annual-billed monthly rate OK if labeled in note |
| 5 | platforms | array of enum: mac / ios / windows / android / web / linux | company site (download/pricing/footer) | Only platforms the company itself claims |
| 6 | founding_year | integer | company about page, press coverage, public registry | Prefer company's own statement; news OK with URL |
| 7 | hq_location | string | company about/contact page, press | City + country; not_disclosed if genuinely unstated |
| 8 | funding_status | enum: bootstrapped / funded / acquired / not_disclosed | press coverage, company blog | Only if publicly stated; no guessing from vibes |
| 9 | last_update_signal | date (YYYY-MM or YYYY-MM-DD) | changelog, blog, App Store version history | Most recent shippped-product update you can find with a URL |
| 10 | google_calendar_integration | boolean | company site (features/integrations) | Company's own claim only |
| 11 | target_user | string, ≤ 12 words | company homepage | Who they say it's for, paraphrase allowed |
| 12 | total_funding_usd | number | press coverage, company blog/announcements | Total publicly disclosed funding to date in USD; sum only rounds with a stated amount and cite the page stating the total or the rounds; not_disclosed if never stated (expected for bootstrapped — sanity-check against funding_status) |
| 13 | founders_background | string, ≤ 60 words | company about/team page, press, founders' own sites | Who founded it and what they did before (prior companies/roles). Public non-login pages only — no LinkedIn (credential-gated). Paraphrase allowed; every claim must appear on the cited page |

Rules of engagement: public web only, nothing behind a login, no hammering any site (one fetch per page, back off on errors). If a page fails twice, record `unreachable` with the URL you tried and move on. Never stop the run for one bad field or one bad company.

## V2 backlog (deliberately NOT in this catalog)

- **user_sentiment — what do their users actually say?** Multi-source by nature (Reddit, HN, App Store/Play reviews, G2/Capterra, X), subjective, and needs synthesis + quote-level citations rather than a single found/not_disclosed value — a different collection pattern from the per-field enrichment loop, hence V2. Replaces what `app_store_rating` (removed 2026-08-19 — weak single-number proxy, poor value per credit) was gesturing at.
- **features_advertised → feature matrix** (two-phase plan discussed 2026-08-19): phase 1 discovery field (array of {feature, source_url}), human-curated canonical taxonomy in between, phase 2 one boolean datapoint per canonical feature with claimed_yes / claimed_no / not_advertised semantics (absence is never inferred). Blocked-on-purpose behind the catalog.json refactor — adding ~20 feature rows under the current hardcoded-in-three-places setup is the pain that refactor exists to kill.
