# Datapoint catalog — calendar-app competitor enrichment (12 fields)

Mirrors the client pattern: each field has a type, an authoritative public source, and a collection rule.
Three outcomes per field, never confused: `found` (value + source_url), `unreachable` (source exists but couldn't be read), `not_disclosed` (no public source states it). An invented value is a failed delivery.

| # | Field | Type | Authoritative source | Collection rule |
|---|---|---|---|---|
| 1 | website | url | web search | Verify the official domain; homepage URL only |
| 2 | tagline | string | company homepage | Their own words from the homepage hero, verbatim |
| 3 | pricing_model | enum: free / freemium / paid_only / subscription | company /pricing page | From the official pricing page only |
| 4 | lowest_paid_price_usd | number | company /pricing page | Monthly USD price of cheapest paid tier; annual-billed monthly rate OK if labeled in note |
| 5 | platforms | array of enum: mac / ios / windows / android / web | company site (download/pricing/footer) | Only platforms the company itself claims |
| 6 | founding_year | integer | company about page, press coverage, public registry | Prefer company's own statement; news OK with URL |
| 7 | hq_location | string | company about/contact page, press | City + country; not_disclosed if genuinely unstated |
| 8 | funding_status | enum: bootstrapped / funded / acquired / not_disclosed | press coverage, company blog | Only if publicly stated; no guessing from vibes |
| 9 | app_store_rating | number 0–5 | Apple App Store public listing | Current rating on the public web listing; unreachable if no listing loads; not_disclosed if no iOS app |
| 10 | last_update_signal | date (YYYY-MM or YYYY-MM-DD) | changelog, blog, App Store version history | Most recent shippped-product update you can find with a URL |
| 11 | google_calendar_integration | boolean | company site (features/integrations) | Company's own claim only |
| 12 | target_user | string, ≤ 12 words | company homepage | Who they say it's for, paraphrase allowed |

Rules of engagement: public web only, nothing behind a login, no hammering any site (one fetch per page, back off on errors). If a page fails twice, record `unreachable` with the URL you tried and move on. Never stop the run for one bad field or one bad company.
