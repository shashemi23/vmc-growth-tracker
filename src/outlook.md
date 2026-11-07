---
title: What it means for you
toc: true
---

# What it means for you

A plain-language read of the numbers on this site, for people who aren't economists.

```js
import {seriesColor} from "./components/palette.js";

const summary = FileAttachment("data/summary.json").json();
const hpi = FileAttachment("data/trreb_vaughan_hpi.csv").csv({typed: true});
const boc = FileAttachment("data/boc_rates.csv").csv({typed: true});
const rental = FileAttachment("data/cmhc_rental_zone.csv").csv({typed: true});
```

```js
const sourceIds = Object.keys(summary.sources ?? {});
const srcNum = new Map(sourceIds.map((id, i) => [id, i + 1]));
function cites(ids) {
  const valid = (ids ?? []).filter((id) => srcNum.has(id));
  return valid.length
    ? html`<span class="cites">${valid.map((id) => html`<a href="#src-${srcNum.get(id)}" title=${summary.sources[id].title}>[${srcNum.get(id)}]</a>`)}</span>`
    : "";
}
const SIGNAL = {rising: "▲ Rising", falling: "▼ Falling", steady: "● Steady", mixed: "◆ Mixed"};
const DIRECTION = {"helps growth": "▲ Helps growth", "slows growth": "▼ Slows growth", mixed: "◆ Mixed"};
const PERSONAS = {
  first_time_buyer: "First-time buyer",
  renter: "Renter",
  family: "Planning a family",
  seller: "Planning to sell",
  investor: "Investor / landlord",
  downsizer: "Downsizer / retiree"
};
const genDate = summary.generated ? new Date(summary.generated) : null;
```

<div class="warning" label="Educational only">
This page explains public data in plain language. It is not financial, legal or real-estate advice, and its outlook is a set of possibilities, not a prediction. Talk to a licensed professional before making decisions.
</div>

## Right now

```js
display(html`<div class="card headline">
  <p class="lead">${summary.headline} ${cites(summary.headline_cite)}</p>
  <p class="muted small">${genDate
    ? html`Written by Claude (${summary.model}) on ${genDate.toLocaleDateString("en-CA", {year: "numeric", month: "long", day: "numeric"})} from this site's data and the news sources listed below. Every point links to its source. ${summary.dropped_uncited_items ? `${summary.dropped_uncited_items} statement(s) without a valid source were removed automatically.` : ""}`
    : "Not generated yet."}</p>
</div>`);
```

```js
if (summary.status.length) display(html`<div class="grid grid-cols-3">${summary.status.map((s) => html`<div class="card status">
  <h3>${s.area[0].toUpperCase() + s.area.slice(1)}</h3>
  <div class="signal">${SIGNAL[s.signal] ?? s.signal}</div>
  <strong>${s.label}</strong>
  <p>${s.explanation} ${cites(s.cite)}</p>
</div>`)}</div>`);
```

## Understand the basics

<div class="grid grid-cols-2 explainers">
<details class="card"><summary><strong>How a condo tower gets built</strong></summary>
<p>A developer files an <b>application</b> with the city (rezoning, site plan). Once <b>approved</b>, they pre-sell units. When enough are sold and financing is in place, construction <b>starts</b>. A few years later the building is <b>completed</b> and people move in. From application to move-in usually takes 4–7 years, so today's applications are homes for around 2030 and later.</p>
</details>
<details class="card"><summary><strong>Starts vs completions</strong></summary>
<p><b>Starts</b> count homes where construction began. They tell you about supply a few years from now. <b>Completions</b> count homes that just finished. They are supply arriving <i>today</i>. Many completions at once means more homes competing for buyers and renters, which tends to cool prices and rents.</p>
</details>
<details class="card"><summary><strong>Vacancy rate</strong></summary>
<p>The share of rental apartments sitting empty. Around <b>3%</b> is considered balanced. Below 2%, renters compete and rents tend to rise. Above 4%, landlords compete and rents tend to flatten or fall.</p>
</details>
<details class="card"><summary><strong>Interest rates and your payment</strong></summary>
<p>The Bank of Canada sets a <b>policy rate</b>; banks base mortgage rates on it and on bond markets. On a $500,000 mortgage over 25 years, each 1 percentage point higher rate adds roughly <b>$270–$300 a month</b>. Lower rates let buyers afford more, which supports prices.</p>
</details>
<details class="card"><summary><strong>Average vs benchmark price</strong></summary>
<p>The <b>average price</b> moves with whatever happened to sell that month (a few big houses can lift it). The <b>benchmark price</b> (MLS Home Price Index) estimates the value of a <i>typical</i> home, so it's steadier and better for comparing over time.</p>
</details>
<details class="card"><summary><strong>Why the VMC behaves differently</strong></summary>
<p>The VMC is almost all <b>condo apartments</b>, and many are bought by investors who rent them out. That makes it more sensitive to interest rates, rents and population growth (especially newcomers and students) than neighbourhoods of detached houses.</p>
</details>
</div>

## Pick your situation

```js
const personaIds = summary.personas.map((p) => p.id);
const persona = personaIds.length
  ? view(Inputs.radio(personaIds, {format: (id) => PERSONAS[id] ?? id, value: personaIds[0]}))
  : null;
```

```js
const p = summary.personas.find((d) => d.id === persona);
if (p) display(html`<div class="card persona">
  <h3>${PERSONAS[p.id]}</h3>
  <p class="lead">${p.bottom_line}</p>
  <ul>${p.points.map((pt) => html`<li>${pt.text} ${cites(pt.cite)}</li>`)}</ul>
  ${p.watch.length ? html`<p><strong>Keep an eye on:</strong> ${p.watch.join(" · ")}</p>` : ""}
</div>`);
else display(html`<p class="muted">Personal views appear here once the summary is generated.</p>`);
```

```js
// A supporting chart for the selected situation, drawn from this site's data.
// Benchmark price (MLS Home Price Index) = estimated value of a typical home; steadier than averages.
const bench = (types, labels = {}) => hpi
  .filter((d) => types.includes(d.home_type) && d.benchmark_price != null)
  .map((d) => ({month: d.month, home_type: labels[d.home_type] ?? d.home_type, value: d.benchmark_price}));
const HPI_NOTE = "TRREB MLS Home Price Index: the estimated value of a typical home in Vaughan.";
const chartFor = {
  seller: () => ({title: "What a typical Vaughan home is worth", note: `${HPI_NOTE} Compare today with past highs.`, rows: bench(["Composite", "Apartment"], {Composite: "All home types", Apartment: "Condo apartment"}), y: "value", z: "home_type", yLabel: "Benchmark price ($)"}),
  downsizer: () => ({title: "Detached house vs condo apartment, typical value", note: `${HPI_NOTE} The gap is roughly what downsizing frees up.`, rows: bench(["Detached", "Apartment"], {Apartment: "Condo apartment"}), y: "value", z: "home_type", yLabel: "Benchmark price ($)"}),
  first_time_buyer: () => ({title: "Interest rates", note: "Bank of Canada. The posted 5-year rate is higher than most people actually pay.", rows: boc.map((d) => ({...d, label: d.series === "policy_rate" ? "Policy rate" : "5-yr mortgage (posted)"})), y: "rate", z: "label", yLabel: "Rate (%)"}),
  investor: () => ({title: "Typical condo apartment value, Vaughan", note: `${HPI_NOTE} Compare with rents on the Housing page.`, rows: bench(["Apartment"], {Apartment: "Condo apartment"}), y: "value", z: "home_type", yLabel: "Benchmark price ($)"}),
  renter: () => ({title: "Average rent, purpose-built rentals", note: "CMHC October survey.", rows: rental.filter((d) => d.bedroom === "Total" && d.avg_rent != null).map((d) => ({...d, month: new Date(Date.UTC(d.year, 9, 1))})), y: "avg_rent", z: "geography", yLabel: "$/month"}),
  family: () => ({title: "Family-sized homes: townhouse vs detached, typical value", note: HPI_NOTE, rows: bench(["Townhouse", "Detached"]), y: "value", z: "home_type", yLabel: "Benchmark price ($)"})
};
const spec = persona && chartFor[persona]?.();
if (spec && spec.rows.length) {
  const zs = [...new Set(spec.rows.map((d) => d[spec.z]))];
  const fmtY = spec.y === "rate" ? (v) => `${v}%` : d3.format("$,.0f");
  display(html`<div class="card">${resize((width) => Plot.plot({
    title: spec.title,
    subtitle: spec.note,
    width,
    height: 300,
    x: {label: null},
    y: {grid: true, label: spec.yLabel},
    color: {domain: zs, range: zs.map((_, i) => seriesColor(dark, i)), legend: zs.length > 1},
    marks: [
      Plot.lineY(spec.rows, {x: "month", y: spec.y, stroke: spec.z, strokeWidth: 2}),
      Plot.ruleX(spec.rows, Plot.pointerX({x: "month", stroke: "var(--theme-foreground-faint)"})),
      Plot.tip(spec.rows, Plot.pointerX({x: "month", y: spec.y, stroke: spec.z, format: {x: d3.utcFormat("%b %Y"), y: fmtY}}))
    ]
  }))}</div>`);
}
```

## Outlook: three possible paths

```js
const order = ["optimistic", "base", "pessimistic"];
const NAMES = {optimistic: "Things improve", base: "Most likely path", pessimistic: "Things get harder"};
if (summary.scenarios.length) display(html`<div class="grid grid-cols-3">${order
  .map((n) => summary.scenarios.find((s) => s.name === n))
  .filter(Boolean)
  .map((s) => html`<div class="card scenario">
    <h3>${NAMES[s.name]}</h3>
    <div class="muted">${s.likelihood} · ${s.horizon}</div>
    <p>${s.summary}</p>
    <ul>${s.drivers.map((d) => html`<li><span class="dir">${DIRECTION[d.direction] ?? d.direction}</span> ${d.text} ${cites(d.cite)}</li>`)}</ul>
  </div>`)}</div>`);
else display(html`<p class="muted">Scenarios appear once the summary is generated.</p>`);
```

## Events that matter

```js
const events = summary.events.slice().sort((a, b) => d3.descending(a.date, b.date));
if (events.length) display(html`<div class="events">${events.map((e) => html`<div class="card event">
  <div class="muted small">${e.date} · ${e.level} · <strong>${DIRECTION[e.direction] ?? e.direction}</strong></div>
  <strong>${e.title}</strong> ${cites(e.cite)}
  <p>${e.impact}</p>
</div>`)}</div>`);
else display(html`<p class="muted">Events appear once the summary is generated.</p>`);
```

## What would change this outlook

```js
if (summary.watch_list.length) display(html`<div class="grid grid-cols-2">${summary.watch_list.map((w) => html`<div class="card">
  <strong>${w.signal}</strong>
  <div class="muted">Watch for: ${w.threshold}</div>
  <p>${w.why} ${cites(w.cite)}</p>
</div>`)}</div>`);
```

## Sources

```js
display(sourceIds.length
  ? html`<ol class="sources">${sourceIds.map((id) => {
      const s = summary.sources[id];
      return html`<li id="src-${srcNum.get(id)}"><a href=${s.url} target="_blank" rel="noopener">${s.title}</a> <span class="muted small">${s.kind === "data" ? "(this site's data)" : new URL(s.url).hostname}${s.page_age ? ` · ${s.page_age}` : ""}</span></li>`;
    })}</ol>`
  : html`<p class="muted">No sources yet.</p>`);
```

<style>
.headline .lead, .persona .lead { font-size: 1.15rem; line-height: 1.5; max-width: none; }
.small { font-size: 0.85rem; }
.cites a { font-size: 0.75em; vertical-align: super; margin-left: 1px; text-decoration: none; }
.status h3 { margin: 0; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 0.04em; color: var(--theme-foreground-muted); }
.status .signal { font-weight: 600; margin: 0.25rem 0; }
.explainers details summary { cursor: pointer; }
.explainers details p, .event p, .scenario p { max-width: none; }
.event { margin-bottom: 0.75rem; }
.scenario .dir { font-size: 0.8rem; font-weight: 600; white-space: nowrap; }
.scenario ul, .persona ul { padding-left: 1.1rem; }
.sources li { margin-bottom: 0.3rem; }
</style>
