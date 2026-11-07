# Housing market

New supply from CMHC's Starts and Completions Survey, for the VMC census tract and the City of Vaughan as a whole, plus rents from CMHC's Rental Market Survey.

```js
import {dwellingColor, seriesColor} from "./components/palette.js";

const monthly = FileAttachment("data/cmhc_vaughan_monthly.csv").csv({typed: true});
const tract = FileAttachment("data/cmhc_vmc_tract_annual.csv").csv({typed: true});
const rental = FileAttachment("data/cmhc_rental_zone.csv").csv({typed: true});
```

```js
const types = dwellingColor(dark).domain;
const latestMonth = d3.max(monthly, (d) => d.date);
const partialYear = latestMonth.getUTCMonth() < 11 ? latestMonth.getUTCFullYear() : null;
// monthly has one column per dwelling type; unpivot the ones charted.
const annual = d3.flatRollup(
  monthly.filter((d) => d.series !== "under_construction")
    .flatMap((d) => types.map((t) => ({date: d.date, series: d.series, dwelling_type: t, units: d[t]}))),
  (v) => d3.sum(v, (d) => d.units),
  (d) => d.series,
  (d) => d.date.getUTCFullYear(),
  (d) => d.dwelling_type
).map(([series, year, dwelling_type, units]) => ({series, year, dwelling_type, units}));
```

## VMC census tract

```js
const tractAll = tract.filter((d) => d.dwelling_type === "All");
const tractLabel = tract.length ? d3.format("07.2f")(tract[0].tract) : "";
const vaughanAptStarts = new Map(annual.filter((d) => d.series === "starts" && d.dwelling_type === "Apartment").map((d) => [d.year, d.units]));
const share = tract
  .filter((d) => d.series === "starts" && d.dwelling_type === "Apartment" && vaughanAptStarts.get(d.year))
  .map((d) => ({year: d.year, share: d.units / vaughanAptStarts.get(d.year)}));
```

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Starts and completions per year",
      subtitle: `Tract ${tractLabel}${partialYear ? `, ${partialYear} is year to date` : ""}`,
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
      title: "VMC tract share of all Vaughan apartment starts",
      width,
      height: 300,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "Share", tickFormat: "%", domain: [0, 1]},
      marks: [
        Plot.ruleY([0]),
        Plot.lineY(share, {x: "year", y: "share", stroke: seriesColor(dark, 0), strokeWidth: 2}),
        Plot.dot(share, {x: "year", y: "share", fill: seriesColor(dark, 0), r: 4, tip: {format: {share: ".0%"}}})
      ]
    }))}
  </div>
</div>

<div class="note">Tract ${tractLabel} contains the VMC but also the surrounding Concord employment lands. Almost all of its apartment starts are VMC towers, but low-rise starts may fall outside the VMC. CMHC stopped publishing tract-level completions after 2022.</div>

## City of Vaughan

```js
const yearRange = view(Inputs.range([1990, d3.max(annual, (d) => d.year)], {label: "From year", step: 1, value: 2005}));
```

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Housing starts per year by dwelling type",
      subtitle: partialYear ? `${partialYear} is year to date` : "",
      width,
      height: 320,
      x: {label: null, tickFormat: "d", interval: 1},
      y: {grid: true, label: "Units"},
      color: dwellingColor(dark),
      marks: [
        Plot.barY(annual.filter((d) => d.series === "starts" && d.year >= yearRange), {x: "year", y: "units", fill: "dwelling_type", order: types, insetLeft: 1, insetRight: 1, tip: true}),
        Plot.ruleY([0])
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Housing completions per year by dwelling type",
      subtitle: partialYear ? `${partialYear} is year to date` : "",
      width,
      height: 320,
      x: {label: null, tickFormat: "d", interval: 1},
      y: {grid: true, label: "Units"},
      color: dwellingColor(dark),
      marks: [
        Plot.barY(annual.filter((d) => d.series === "completions" && d.year >= yearRange), {x: "year", y: "units", fill: "dwelling_type", order: types, insetLeft: 1, insetRight: 1, tip: true}),
        Plot.ruleY([0])
      ]
    }))}
  </div>
</div>

```js
const uc = monthly.filter((d) => d.series === "under_construction" && d.date.getUTCFullYear() >= yearRange).map((d) => ({date: d.date, units: d.All}));
display(resize((width) => Plot.plot({
  title: "Units under construction, monthly",
  width,
  height: 280,
  x: {label: null},
  y: {grid: true, label: "Units"},
  marks: [
    Plot.ruleY([0]),
    Plot.lineY(uc, {x: "date", y: "units", stroke: seriesColor(dark, 0), strokeWidth: 2}),
    Plot.ruleX(uc, Plot.pointerX({x: "date", stroke: "var(--theme-foreground-faint)"})),
    Plot.dot(uc, Plot.pointerX({x: "date", y: "units", fill: seriesColor(dark, 0), r: 4})),
    Plot.tip(uc, Plot.pointerX({x: "date", y: "units", format: {x: d3.utcFormat("%b %Y")}}))
  ]
})));
```

## Rental market

```js
const ZONE = "Richmond Hill/Vaughan/King";
const bedroom = view(Inputs.select(["Total", "Studio", "1 Bedroom", "2 Bedroom", "3 Bedroom +"], {label: "Bedrooms", value: "Total"}));
```

```js
const rentRows = rental.filter((d) => d.bedroom === bedroom);
const geoColor = {domain: [ZONE, "Toronto CMA"], range: [seriesColor(dark, 0), seriesColor(dark, 1)], legend: true};
```

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: `Average rent, ${bedroom === "Total" ? "all bedroom types" : bedroom}`,
      subtitle: "Purpose-built rental, October survey",
      width,
      height: 280,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "$/month"},
      color: geoColor,
      marks: [
        Plot.lineY(rentRows.filter((d) => d.avg_rent != null), {x: "year", y: "avg_rent", stroke: "geography", strokeWidth: 2, tip: true})
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: `Vacancy rate, ${bedroom === "Total" ? "all bedroom types" : bedroom}`,
      subtitle: "Purpose-built rental, October survey",
      width,
      height: 280,
      x: {label: null, tickFormat: "d"},
      y: {grid: true, label: "Vacancy (%)", zero: true},
      color: geoColor,
      marks: [
        Plot.ruleY([0]),
        Plot.lineY(rentRows.filter((d) => d.vacancy_rate != null), {x: "year", y: "vacancy_rate", stroke: "geography", strokeWidth: 2, tip: true})
      ]
    }))}
  </div>
</div>

<div class="note">CMHC suppresses most rental figures for the City of Vaughan alone, so this uses CMHC's <b>${ZONE}</b> survey zone. Gaps mean CMHC suppressed the value (sample too small). Condo rentals, a large share of the VMC's rental stock, are not part of this survey.</div>

## Resale market (Vaughan)

```js
const resale = FileAttachment("data/trreb_vaughan_monthly.csv").csv({typed: true});
const hpi = FileAttachment("data/trreb_vaughan_hpi.csv").csv({typed: true});
const rates = FileAttachment("data/boc_rates.csv").csv({typed: true});
```

```js
// Insert empty months so the line breaks at gaps instead of bridging them.
const allSales = new Map(resale.filter((d) => d.home_type === "All").map((d) => [+d.month, d]));
const salesFilled = allSales.size
  ? d3.utcMonth.range(d3.min(allSales.keys()), d3.utcMonth.offset(d3.max(allSales.keys()), 1))
      .map((m) => allSales.get(+m) ?? {month: m, sales: NaN, months_inventory: NaN})
  : [];
```

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Benchmark price by home type",
      subtitle: "MLS Home Price Index: value of a typical home",
      width,
      height: 300,
      x: {label: null},
      y: {grid: true, label: "Benchmark price ($)", tickFormat: "$~s"},
      color: {domain: ["Detached", "Townhouse", "Apartment"], range: [0, 1, 3].map((i) => seriesColor(dark, i)), legend: true},
      marks: [
        Plot.lineY(hpi.filter((d) => ["Detached", "Townhouse", "Apartment"].includes(d.home_type)), {x: "month", y: "benchmark_price", stroke: "home_type", strokeWidth: 2, tip: {format: {y: "$,.0f"}}})
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Homes sold per month, all types",
      subtitle: "TRREB Market Watch. Gap: mid-2022 to mid-2025 reports couldn't be read reliably.",
      width,
      height: 300,
      x: {label: null},
      y: {grid: true, label: "Sales"},
      marks: [
        Plot.ruleY([0]),
        Plot.lineY(salesFilled, {x: "month", y: "sales", stroke: seriesColor(dark, 0), strokeWidth: 1.5, tip: true})
      ]
    }))}
  </div>
</div>

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Months of inventory, all types",
      subtitle: "How long current listings would take to sell at today's pace. Under 3 favours sellers; over 5 favours buyers.",
      width,
      height: 280,
      x: {label: null},
      y: {grid: true, label: "Months", zero: true},
      marks: [
        Plot.lineY(salesFilled, {x: "month", y: "months_inventory", stroke: seriesColor(dark, 0), strokeWidth: 2, tip: true})
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Interest rates",
      subtitle: "Bank of Canada. Posted 5-year rates are above what most borrowers pay.",
      width,
      height: 280,
      x: {label: null},
      y: {grid: true, label: "Rate (%)", zero: true},
      color: {domain: ["policy_rate", "mortgage_5yr_posted"], range: [seriesColor(dark, 0), seriesColor(dark, 1)], legend: true, tickFormat: (d) => (d === "policy_rate" ? "Policy rate" : "5-yr mortgage (posted)")},
      marks: [
        Plot.lineY(rates, {x: "month", y: "rate", stroke: "series", strokeWidth: 2, tip: true})
      ]
    }))}
  </div>
</div>

<div class="note">Resale figures are for all of Vaughan, from TRREB's monthly Market Watch reports. The VMC is mostly condo apartments, so the apartment lines are the closest match.</div>
