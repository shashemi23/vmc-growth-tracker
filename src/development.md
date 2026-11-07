# Development pipeline

Active planning applications inside the VMC Regional Centre and the VMC subway Major Transit Station Area (MTSA). Source: York Region's development application feed.

```js
import {seriesColor} from "./components/palette.js";

const geo = FileAttachment("data/devapps.geojson").json();
const registry = FileAttachment("data/devapps_registry.csv").csv({typed: true});
const snapshots = FileAttachment("data/devapps_snapshots.csv").csv({typed: true});
```

```js
const active = registry.filter((d) => String(d.active) === "True");
const closed = registry.filter((d) => String(d.active) !== "True");
const blue = seriesColor(dark, 0);
```

## Map

```js
import * as L from "npm:leaflet";

const div = display(document.createElement("div"));
div.style = "height: 520px; border-radius: 8px;";
const map = L.map(div, {scrollWheelZoom: false});
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
const layer = L.geoJSON(
  {...geo, features: geo.features.filter((f) => f.geometry)},
  {
    style: {color: blue, weight: 1.5, fillOpacity: 0.25},
    onEachFeature: (f, l) => {
      const p = f.properties;
      l.bindPopup(html`<div style="max-width:280px">
        <strong>${p.name || p.file_num}</strong><br>
        ${p.type}${p.subtype ? ` (${p.subtype})` : ""} · ${p.stage}<br>
        ${p.address || p.location}<br>
        ${p.units_est ? html`<b>~${p.units_est} units</b>` : ""} ${p.storeys_max ? `· up to ${p.storeys_max} storeys` : ""}
        <p style="font-size:12px;margin:.5em 0 0">${p.description}</p>
        <small>${p.file_num} · received ${p.date_received}</small>
      </div>`);
    }
  }
).addTo(map);
map.fitBounds(layer.getBounds(), {padding: [10, 10]});
invalidation.then(() => map.remove());
```

## What's in the pipeline

<div class="grid grid-cols-2">
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Active applications by type",
      width: Math.max(width, 360),
      height: 300,
      marginLeft: 190,
      x: {grid: true, label: "Applications"},
      y: {label: null},
      marks: [
        Plot.barX(active, Plot.groupY({x: "count"}, {y: "type", fill: blue, sort: {y: "-x"}, rx: 4, insetTop: 1, insetBottom: 1, tip: true})),
        Plot.ruleX([0])
      ]
    }))}
  </div>
  <div class="card">
    ${resize((width) => Plot.plot({
      title: "Active applications by year received",
      subtitle: "Older files are still open, often large multi-phase plans",
      width,
      height: 300,
      x: {label: null, tickFormat: "d", interval: 1},
      y: {grid: true, label: "Applications"},
      marks: [
        Plot.barY(active.filter((d) => d.date_received), Plot.groupX({y: "count"}, {x: (d) => d.date_received.getUTCFullYear(), fill: blue, rx: 4, insetLeft: 1, insetRight: 1, tip: true})),
        Plot.ruleY([0])
      ]
    }))}
  </div>
</div>

<div class="note">Unit counts are parsed from each application's free-text description and are estimates. One project often has several files open at once (official plan amendment, rezoning, site plan, condominium), so totals are shown per application type rather than summed across types.</div>

## Pipeline over time

The York Region feed only lists *active* files. This tracker snapshots it every week, so history builds up from the first run (${d3.utcFormat("%b %-d, %Y")(snapshots[0].snapshot_date)}). ${closed.length ? `${closed.length} applications have left the feed (approved, closed or withdrawn) since tracking began.` : "No applications have left the feed yet."}

```js
display(resize((width) => Plot.plot({
  width,
  height: 260,
  x: {label: null},
  y: {grid: true, label: "Active applications", zero: true},
  marks: [
    Plot.lineY(snapshots, {x: "snapshot_date", y: "active_apps", stroke: blue, strokeWidth: 2}),
    Plot.dot(snapshots, {x: "snapshot_date", y: "active_apps", fill: blue, r: 4, tip: true})
  ]
})));
```

## All applications

```js
const typeFilter = view(Inputs.select(["All types", ...[...new Set(registry.map((d) => d.type))].sort()], {label: "Type", value: "All types"}));
const query = view(Inputs.search(registry, {placeholder: "Search name, address, description…"}));
```

```js
display(Inputs.table(query.filter((d) => typeFilter === "All types" || d.type === typeFilter), {
  columns: ["file_num", "name", "type", "stage", "status", "date_received", "units_est", "storeys_max", "address", "active"],
  header: {file_num: "File", name: "Name", type: "Type", stage: "Stage", status: "Status", date_received: "Received", units_est: "Units (est.)", storeys_max: "Max storeys", address: "Address", active: "Active"},
  format: {date_received: d3.utcFormat("%Y-%m-%d")},
  width: {file_num: 130, name: 220, type: 190, address: 200},
  layout: "auto",
  sort: "date_received",
  reverse: true,
  rows: 20
}));
```
