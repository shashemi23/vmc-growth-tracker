# VMC Growth Tracker

Dashboard tracking economic growth in the **Vaughan Metropolitan Centre (VMC)**: the development pipeline and the housing market around it.

**Live dashboard:** https://shashemi23.github.io/vmc-growth-tracker/

## What it tracks

| Page | Data | Source |
|---|---|---|
| Development pipeline | Active planning applications in the VMC (map, types, units, storeys) | York Region Open Data (ArcGIS) |
| What it means for you | Plain-language summary, life-stage views, scenarios, events, with citations | Claude (weekly) from the data below + web search |
| Housing market | Starts, completions, under construction (Vaughan + VMC census tract); rents and vacancy (Richmond Hill/Vaughan/King zone); Vaughan resale prices; interest rates | CMHC HMIP, TRREB Market Watch, Bank of Canada |

## How it works

```
GitHub Actions (weekly cron, Mondays)
  -> pipeline/fetch_*.py pull public data (York Region, CMHC, TRREB, Bank of Canada)
  -> pipeline/generate_summary.py has Claude write the cited plain-language summary
  -> commit CSV/GeoJSON to src/data/   (git history = data history)
  -> Observable Framework builds a static site
  -> GitHub Pages hosts it (free)
```

The York Region feed only lists *active* applications, so `devapps_registry.csv` keeps every file ever seen and marks closed ones `active=False`. History builds from the first run.

## AI summary setup

The summary page needs an Anthropic API key stored as a repo secret:

```sh
gh secret set ANTHROPIC_API_KEY
```

Without it, the workflow skips that step and the page shows a placeholder. A failed or declined generation keeps the previous week's summary. Each run is two Claude calls (research with web search, then writing), roughly $1 per run.

## Local development

```sh
npm install
pip install -r requirements.txt
npm run fetch      # refresh data (needs Python 3.10+)
npm run summary    # regenerate AI summary (needs ANTHROPIC_API_KEY)
npm run dev        # preview at http://127.0.0.1:3000
npm run build      # static site in dist/
```

## Repo layout

```
pipeline/           data fetchers (fetch_*.py), summary generator, shared helpers
src/data/           fetched data, committed
src/*.md            dashboard pages (Observable Framework)
src/components/     shared JS (chart palette)
.github/workflows/  weekly refresh + Pages deploy
```

## Adding a data source

1. Add `pipeline/fetch_<name>.py` that writes tidy CSV to `src/data/`.
2. Call it from the "Fetch data" step in `.github/workflows/deploy.yml` and the `fetch` npm script.
3. Load it in a page with `FileAttachment("data/<file>.csv").csv({typed: true})`.

## Caveats

- CMHC's HMIP CSV export is not an official API (the [`cmhc` R package](https://github.com/mountainMath/cmhc) uses the same endpoint).
- Unit and storey counts are parsed from application descriptions and are estimates.
- CMHC tract 0411.08 includes the VMC plus parts of the Concord employment lands.
