# Status and handoff

_Last updated: 2026-11-07. Update this file at the end of any working session._

## Live

| Piece | Where | Schedule |
|---|---|---|
| Dashboard (5 pages) | https://shashemi23.github.io/vmc-growth-tracker/ | redeploys on every push |
| Data refresh + baseline + deploy | `.github/workflows/deploy.yml` | Mondays 11:00 UTC |
| Plain-language summary | cloud routine `trig_013MynYaKrxGxAjNgCEWbRbV` ([manage](https://claude.ai/code/routines/trig_013MynYaKrxGxAjNgCEWbRbV)), runbook `pipeline/SUMMARY_AGENT.md` | Mondays 13:00 UTC |

The routine runs in cloud environment `env_01QufB35V8FbQtM6xbV2HyQv` ("Default"), Network access:
Custom, Allowed domains = `pipeline/approved_sources.txt` + default package managers.

Data coverage: York Region applications (snapshots from 2026-11-07), CMHC Vaughan monthly since
1990, VMC tract 2011+, rental zone 2010+, TRREB Vaughan 2015+ (sales gap mid-2022 to mid-2025),
Bank of Canada rates 2010+.

Forecast scorecard: 16 calls logged (8 baseline, 8 Claude). First result due when CMHC publishes
the October 2026 rental survey (usually December); price calls resolve from April 2027.

## Open issues

1. **PDF text extraction fails inside the routine's sandbox** (news.ontario.ca PDF), while it
   works locally. Code now degrades gracefully and prints the cause; read the next run's log
   (`list_runs` / `get_run_log` on the routine) to find out why (likely a `pdfplumber`
   dependency).
2. **canada.ca fails the link check inside the sandbox** although it's in Allowed domains and
   WebFetch can read it. Probably the site blocking the sandbox's IP or user agent. Immigration
   facts get dropped as a result.
3. **vaughan.ca returns 403 to WebFetch** (but passes the ingest link check). The routine can't
   quote it, so Vaughan development-charge facts drop out. Could add a raw-download fallback for
   quoting.
4. **Quote check limitation:** confirms the quote is on the page, not that the summary's wording
   matches it. Quotes are kept in `summary.json` → `evidence` for review.
5. **TRREB terms of use** not reviewed; data is reproduced with attribution.
6. **TRREB mid-2022 to mid-2025 sales tables unreadable** (overlaid layers). Could be recovered
   by working out which layer is the current month.

## Next ideas (not started)

- Condo unit mix (2- and 3-bedroom share) parsed from application text, for the family persona.
- Statistics Canada building permits for Vaughan, if published monthly at municipal level.
- Statistics Canada building construction price index (Toronto) as a cost-pressure signal.
- Turning-point flags on status cards (e.g. "condo values stopped falling").
- Measure the actual lag from rate changes to Vaughan apartment starts.
- Bank of Canada Survey of Consumer Expectations as a sentiment input.
- Show evidence quotes as tooltips on citations.

## Resuming work

1. Read `CLAUDE.md`, this file, then `docs/DECISIONS.md`.
2. `git pull`; check the last Actions run and the last routine run.
3. When you finish, update this file and add any new decisions to `docs/DECISIONS.md`.
