# VMC Growth Tracker

Dashboard tracking economic growth in the **Vaughan Metropolitan Centre (VMC)**: the development pipeline and the housing market around it.

**Live dashboard:** https://shashemi23.github.io/vmc-growth-tracker/

## What it tracks

| Page | Data | Source |
|---|---|---|
| Development pipeline | Active planning applications in the VMC (map, types, units, storeys) | York Region Open Data (ArcGIS) |
| Housing market | Starts, completions, under construction (Vaughan + VMC census tract); rents and vacancy (Richmond Hill/Vaughan/King zone) | CMHC Housing Market Information Portal |

## How it works

```
GitHub Actions (weekly cron, Mondays)
  -> pipeline/*.py fetch public data (Python standard library only)
  -> commit CSV/GeoJSON to src/data/   (git history = data history)
  -> Observable Framework builds a static site
  -> GitHub Pages hosts it (free)
```

The York Region feed only lists *active* applications, so `devapps_registry.csv` keeps every file ever seen and marks closed ones `active=False`. History builds from the first run.

## Local development

```sh
npm install
npm run fetch      # refresh data (needs Python 3.10+)
npm run dev        # preview at http://127.0.0.1:3000
npm run build      # static site in dist/
```

## Repo layout

```
pipeline/           data fetchers (fetch_devapps.py, fetch_cmhc.py, common.py)
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
