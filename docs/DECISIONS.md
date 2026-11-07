# Decision log

Newest last. Each entry: what was decided, why, and what it rules out. Add an entry whenever a
choice would surprise someone reading the code later.

## 2026-11-07

**D1. Scope v1: development pipeline + housing market.** Owner's choice. Population/jobs
(StatCan) and transit/business are deferred.

**D2. Stack: Python fetchers + Observable Framework on GitHub Pages, public repo.** Free hosting,
static site, data committed to git so its history is the data history. Python fetchers use the
standard library except `pdfplumber` (TRREB, quote checks) and the optional `anthropic` SDK.

**D3. Weekly refresh, Mondays 11:00 UTC.** Sources update monthly or slower (CMHC monthly, TRREB
monthly, rental survey annually); weekly is enough. Each run adds a snapshot row, so the repo
never goes 60 days without a commit (GitHub would disable the schedule).

**D4. VMC definition for applications:** York Region's `CENTRE_CORR_NAME = 'Vaughan Metropolitan
Centre'` or MTSA containing "Vaughan Metropolitan Centre Subway". The feed lists active files only,
so `devapps_registry.csv` keeps every file ever seen (closed ones become `active=False`).

**D5. Unit counts come from parsing application text** (the `UNITS` field is a Yes/null flag).
Shown per application type and never summed across types, because one project files several
applications.

**D6. CMHC via the HMIP CSV export** (unofficial; same endpoint as the `cmhc` R package). VMC =
census tract 0411.08 (2021), which also covers Concord employment lands. Tract completions were
archived by CMHC after 2022. Vaughan-only rents are suppressed, so rents use the Richmond
Hill/Vaughan/King zone vs Toronto CMA. Slow CMA-wide exports are cached by year.

**D7. TRREB Market Watch PDFs scraped for Vaughan resale data (2015+),** with attribution and a
"not affiliated" note. Mid-2022 to mid-2025 sales tables overlay two layers and can't be told
apart, so those sales rows are skipped rather than guessed; the MLS HPI table is complete.

**D8. Price history uses the MLS HPI benchmark price, not average price.** Averages swing with
what happened to sell; the benchmark is a typical home and has no gap.

**D9. Build slimmed (~55% smaller downloads):** wide CMHC CSV, no per-row `source_url` in TRREB
CSVs, GeoJSON keeps outlines only (5 dp) and the page joins attributes from the registry.

**D10. Plain-language page for non-economists** ("What it means for you"): headline, status
cards, six life-stage personas, explainers, scenarios, events, watch list, sources. Educational
only; no buy/sell advice.

**D11. Forecasting method after Klein & Young (1980) and Evans & Klein (Wharton model):**
- a mechanical baseline per measure ("no change" vs damped trend, chosen by backtest) with an
  80% band taken from past errors;
- Claude's judgment recorded as above/in line/below the baseline with its own range and cited
  reason;
- scenarios with explicit, checkable assumptions;
- every call logged in `forecast_log.csv` and scored when its target date arrives
  ("How well have we done?").
Ideas only; no text from the books is reproduced.

**D12. No paid Anthropic API key.** Owner wants it free. The summary is written by Claude Code
using the owner's plan: `--emit` brief, research, draft, `--ingest`. A weekly cloud routine
(Mondays 13:00 UTC, Sonnet 5.5, no connectors) does this. The API path in the workflow stays and
runs only if a key is ever added.

**D13. Guardrails at ingest:** schema check; every citation must exist in the source table; items
without a valid source are dropped; if most web sources are unreachable the run stops and keeps
last week's summary (protects against sandbox network blocks publishing a thin page).

**D14. Only owner-approved websites may be cited** (`pipeline/approved_sources.txt`). Full
hostnames, because the cloud environment's Allowed domains doesn't accept wildcards; the two lists
must match. Unapproved sources are rejected by name. `www.thestar.com` was removed because it
blocks Anthropic's search crawler.

**D15. Every web citation must be backed by a verbatim quote** stating the fact, tied to the item
it supports; ingest downloads the page (HTML or PDF) and checks the quote is on it. Prompted by a
real error: the December 9 decision date was cited to a Bank of Canada page that doesn't state it.
Limitation: proves the quote exists, not that the wording represents it fairly.

**D16. Page download and text extraction are checked separately,** so a page that loads but
can't be read (e.g. a PDF problem in the sandbox) still passes the link check; only its quotes go
unverified.

**D17. The routine doesn't build the site;** the deploy workflow does. The sandbox can't reach
the CDN the build needs, and a hidden build failure once let a bad summary through.
