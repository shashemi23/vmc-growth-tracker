---
toc: false
---

# VMC Growth Tracker

Tracking the build-out of the **Vaughan Metropolitan Centre**: the development pipeline and the housing market around it. Data refreshes weekly from public sources.

```js
import {seriesColor} from "./components/palette.js";

const registry = FileAttachment("data/devapps_registry.csv").csv({typed: true});
const snapshots = FileAttachment("data/devapps_snapshots.csv").csv({typed: true});
const tract = FileAttachment("data/cmhc_vmc_tract_annual.csv").csv({typed: true});
const monthly = FileAttachment("data/cmhc_vaughan_monthly.csv").csv({typed: true});
const rental = FileAttachment("data/cmhc_rental_zone.csv").csv({typed: true});
```

```js
const active = registry.filter((d) => String(d.active) === "True");
const latestSnap = snapshots.at(-1);
const tractAll = tract.filter((d) => d.dwelling_type === "All");
const fullYears = tractAll.filter((d) => String(d.partial_year) !== "True");
const lastFullYear = d3.max(fullYears, (d) => d.year);
const startsLastYear = fullYears.find((d) => d.series === "starts" && d.year === lastFullYear)?.units;
const startsYtd = tractAll.find((d) => String(d.partial_year) === "True" && d.series === "starts");
const ucAll = monthly.filter((d) => d.series === "under_construction" && d.dwelling_type === "All");
const ucLatest = ucAll.at(-1);
const ucYearAgo = ucAll.at(-13);
const ZONE = "Richmond Hill/Vaughan/King";
const rentTotal = rental.filter((d) => d.bedroom === "Total" && d.avg_rent != null);
const zoneRent = rentTotal.filter((d) => d.geography === ZONE);
const rentLatest = zoneRent.at(-1);
const rentPrev = zoneRent.at(-2);
const fmt = d3.format(",");
const pct = (a, b) => (b ? d3.format("+.1%")(a / b - 1) : "");
const monthFmt = d3.utcFormat("%b %Y");
const dayFmt = d3.utcFormat("%b %-d, %Y");
const tractLabel = tract.length ? d3.format("07.2f")(tract[0].tract) : "";
```

<div class="grid grid-cols-4">
  <a class="card kpi" href="./development">
    <h2>Active applications in VMC</h2>
    <span class="big">${fmt(active.length)}</span>
    <span class="muted">York Region feed, as of ${dayFmt(latestSnap.snapshot_date)}</span>
  </a>
  <a class="card kpi" href="./development">
    <h2>Units proposed in active site plans</h2>
    <span class="big">${fmt(latestSnap.units_est_site_plans)}</span>
    <span class="muted">Estimated from application text</span>
  </a>
  <a class="card kpi" href="./housing">
    <h2>Housing starts, VMC tract, ${lastFullYear}</h2>
    <span class="big">${fmt(startsLastYear ?? 0)}</span>
    <span class="muted">${startsYtd ? `${fmt(startsYtd.units)} so far in ${startsYtd.year}` : ""}</span>
  </a>
  <a class="card kpi" href="./housing">
    <h2>Units under construction, Vaughan</h2>
    <span class="big">${fmt(ucLatest.units)}</span>
    <span class="muted">${monthFmt(ucLatest.date)} · ${pct(ucLatest.units, ucYearAgo?.units)} year over year</span>
  </a>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Annual housing starts and completions, VMC census tract",
      subtitle: `Tract ${tractLabel} (2021 census).${startsYtd ? ` ${startsYtd.year} is year to date.` : ""}`,
      width,
      height: 300,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "Units"},
      color: {domain: ["starts", "completions"], range: [seriesColor(dark, 0), seriesColor(dark, 1)], legend: true},
      marks: [
        Plot.ruleY([0]),
        Plot.lineY(tractAll, {x: "year", y: "units", stroke: "series", strokeWidth: 2, tip: true}),
        Plot.dot(tractAll, {x: "year", y: "units", fill: "series", r: 4, stroke: "var(--theme-background)", strokeWidth: 2})
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Average purpose-built rent (October survey)",
      subtitle: rentLatest ? `${ZONE} zone, ${rentLatest.year}: $${fmt(rentLatest.avg_rent)} (${pct(rentLatest.avg_rent, rentPrev?.avg_rent)} vs ${rentPrev?.year})` : "",
      width,
      height: 300,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "Monthly rent ($)"},
      color: {domain: [ZONE, "Toronto CMA"], range: [seriesColor(dark, 0), seriesColor(dark, 1)], legend: true},
      marks: [
        Plot.lineY(rentTotal, {x: "year", y: "avg_rent", stroke: "geography", strokeWidth: 2, tip: true})
      ]
    }))}
  </div>
</div>

<style>
.kpi { text-decoration: none; color: inherit; display: flex; flex-direction: column; gap: 0.25rem; }
.kpi:hover { border-color: var(--theme-foreground-focus); }
.kpi .big { font-size: 2.2rem; font-weight: 600; font-variant-numeric: tabular-nums; }
</style>
