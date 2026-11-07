# VMC Growth Tracker: notes for Claude Code sessions

Public dashboard tracking growth in the Vaughan Metropolitan Centre (VMC): development
pipeline, housing market, and a plain-language "What it means for you" page.

- Live: https://shashemi23.github.io/vmc-growth-tracker/
- Repo: https://github.com/shashemi23/vmc-growth-tracker (public)
- Start here when resuming: `docs/STATUS.md` (what's live, open issues, next ideas),
  then `docs/DECISIONS.md` (why things are the way they are).

## How it fits together

```
GitHub Actions, Mondays 11:00 UTC (.github/workflows/deploy.yml)
  pipeline/fetch_devapps.py   York Region ArcGIS: active VMC applications (registry keeps closed ones)
  pipeline/fetch_cmhc.py      CMHC HMIP export: Vaughan starts/completions/UC, VMC tract, rental zone
  pipeline/fetch_trreb.py     TRREB Market Watch PDFs: Vaughan sales + MLS HPI (parallel, cached by month)
  pipeline/fetch_boc.py       Bank of Canada Valet: policy rate, posted 5-yr mortgage
  pipeline/baseline.py        backtested projections + 80% bands; scores forecast_log.csv
  (API summary step runs only if ANTHROPIC_API_KEY secret exists; currently none)
  -> commit src/data/ -> Observable Framework build -> GitHub Pages

Claude Code cloud routine, Mondays 13:00 UTC (trig_013MynYaKrxGxAjNgCEWbRbV, Sonnet 5.5)
  follows pipeline/SUMMARY_AGENT.md:
  generate_summary.py --emit brief -> research (approved sites only) -> draft with quotes
  -> generate_summary.py --ingest (schema, approved-site, link and quote checks) -> push summary.json
```

Pages are Markdown in `src/` (`index`, `outlook`, `development`, `housing`, `about`); shared chart
colours in `src/components/palette.js`. All data is committed under `src/data/`.

## Commands

```sh
npm install && pip install -r requirements.txt
npm run fetch          # all fetchers + baseline (TRREB backfill from scratch ~10 min; weekly ~1 min)
npm run dev -- --port 3317   # port 3000 is taken by another local app
npm run build
python pipeline/generate_summary.py --emit /tmp/brief.json     # free summary, step 1
python pipeline/generate_summary.py --ingest /tmp/draft.json --model "..."   # step 2
```

## Rules that must hold

- **No paid API key.** The summary is written by Claude Code (routine or a session) via
  `--emit`/`--ingest`. Don't add API-only features without asking.
- **Cite only approved sites.** `pipeline/approved_sources.txt` (full hostnames) must match the
  cloud environment's Allowed domains. Never edit it without the owner's say-so.
- **Every web citation needs a verbatim quote** in `evidence`; ingest checks it on the live page.
  Never weaken `verify_claims`, `validate`, or the unreachable-sources stop to make a run pass.
- **Never rewrite history in `src/data/forecast_log.csv`** (only `baseline.py` fills in actuals).
  Scores must stay honest.
- **Educational only.** No buy/sell advice; scenarios, not price predictions.
- Don't copy text from the econometrics books (copyright); cite ideas only.
- Files are LF (`.gitattributes`); `write_csv` writes `\n`.
- Before a commit, `npm run build` must pass; check pages render (preview + browser) when
  touching `src/*.md`.

## Gotchas

- TRREB Market Watch PDFs from mid-2022 to mid-2025 overlay two tables; sales rows are skipped
  (HPI is fine). May 2022 is missing entirely.
- CMHC tract completions were archived after 2022; Vaughan-only rents are suppressed, so rents use
  the "Richmond Hill/Vaughan/King" zone.
- The cloud sandbox only reaches hosts in the environment's Allowed domains; WebFetch/WebSearch run
  outside it, but ingest's link/quote checks run inside it.
- Writing Python through a bash heredoc turns `"\n"` into a real newline; write patch scripts as
  files instead.
