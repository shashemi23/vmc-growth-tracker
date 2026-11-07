"""Fetch active development applications in the Vaughan Metropolitan Centre.

Source: York Region Open Data, "Development Application Status and Teams"
ArcGIS service. It lists *active* applications only, so this script keeps a
registry of every application ever seen. When an application drops off the
feed (approved, withdrawn or closed), the registry keeps it with active=False.

Outputs (src/data/):
  devapps.geojson           current active applications with geometry
  devapps_registry.csv      every application seen, with first/last seen dates
  devapps_snapshots.csv     one summary row per run date
"""

from __future__ import annotations

import datetime as dt
import json
import re

from common import DATA_DIR, http, read_csv, write_csv, write_json

URL = ("https://ww8.yorkmaps.ca/arcgis/rest/services/OpenData/"
       "DevelopmentApplicationStatusAndTeams/MapServer/0/query")

# VMC = the Regional Centre itself, plus anything inside the VMC subway MTSA.
WHERE = ("MUN_NAME='Vaughan' AND (CENTRE_CORR_NAME='Vaughan Metropolitan Centre' "
         "OR MTSA LIKE '%Vaughan Metropolitan Centre%')")

FIELDS = ["REG_FILE_NUM", "EXT_REF_NUM", "APPL_TYPE", "APPL_SUBTYPE", "DATE_RECVD",
          "APPL_STAGE", "APPL_STEP", "APPL_STATUS", "APPL_NAME", "APPL_DESC",
          "ADDRESS", "LOCATION", "MTSA", "CENTRE_CORR_NAME"]

REGISTRY_FIELDS = ["file_num", "ext_ref", "type", "subtype", "date_received", "stage",
                   "step", "status", "name", "address", "location", "units_est",
                   "storeys_max", "description", "first_seen", "last_seen", "active"]

NUM = r"(\d{1,3}(?:,\d{3})+|\d+)"
UNITS_RE = re.compile(NUM + r"\s+(?:[a-z\-]+\s+){0,3}?(?:units|dwellings|suites)", re.I)
STOREYS_RE = re.compile(r"((?:\d+\s*(?:,|and|&|-)\s*)*\d+)\s*-?\s*(?:storey|stories|story)", re.I)


def clean_text(s: str | None) -> str:
    if not s:
        return ""
    # The feed contains mangled non-ASCII characters (e.g. "7� storeys").
    s = re.sub(r"[^\x20-\x7E]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_units(desc: str) -> int | None:
    """Best-effort residential unit count from the free-text description."""
    vals = [int(m.group(1).replace(",", "")) for m in UNITS_RE.finditer(desc)]
    vals = [v for v in vals if 0 < v < 20000]
    return max(vals) if vals else None


def parse_storeys(desc: str) -> int | None:
    """Tallest building mentioned. Handles lists like '49, 45 and 7 storeys'."""
    nums = []
    for m in STOREYS_RE.finditer(desc):
        nums += [int(n) for n in re.findall(r"\d+", m.group(1))]
    nums = [n for n in nums if 0 < n < 120]
    return max(nums) if nums else None


def ms_to_date(ms) -> str:
    if ms in (None, ""):
        return ""
    return dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).date().isoformat()


def fetch() -> list[dict]:
    features, offset = [], 0
    while True:
        raw = http(URL, params={
            "where": WHERE, "outFields": ",".join(FIELDS), "outSR": 4326,
            "returnGeometry": "true", "f": "geojson", "orderByFields": "OBJECTID",
            "resultOffset": offset, "resultRecordCount": 1000,
        })
        page = json.loads(raw.decode("utf-8", errors="replace"))
        if "error" in page:
            raise RuntimeError(page["error"])
        batch = page.get("features", [])
        features += batch
        if len(batch) < 1000:
            return features
        offset += 1000


def main() -> None:
    today = dt.date.today().isoformat()
    features = fetch()
    if not features:
        raise SystemExit("No features returned; refusing to overwrite data.")

    current: dict[str, dict] = {}
    out_features = []
    for f in features:
        a = f["properties"]
        desc = clean_text(a.get("APPL_DESC"))
        rec = {
            "file_num": a["REG_FILE_NUM"],
            "ext_ref": clean_text(a.get("EXT_REF_NUM")),
            "type": clean_text(a.get("APPL_TYPE")),
            "subtype": clean_text(a.get("APPL_SUBTYPE")),
            "date_received": ms_to_date(a.get("DATE_RECVD")),
            "stage": clean_text(a.get("APPL_STAGE")),
            "step": clean_text(a.get("APPL_STEP")),
            "status": clean_text(a.get("APPL_STATUS")),
            "name": clean_text(a.get("APPL_NAME")),
            "address": clean_text(a.get("ADDRESS")),
            "location": clean_text(a.get("LOCATION")),
            "units_est": parse_units(desc) or "",
            "storeys_max": parse_storeys(desc) or "",
            "description": desc,
        }
        # One application can span several parcels; keep the first record's attributes.
        current.setdefault(rec["file_num"], rec)
        out_features.append({"type": "Feature", "geometry": f.get("geometry"),
                             "properties": {k: rec[k] for k in REGISTRY_FIELDS[:13]}})

    write_json(DATA_DIR / "devapps.geojson",
               {"type": "FeatureCollection", "generated": today, "features": out_features})

    # Registry: merge with history.
    reg_path = DATA_DIR / "devapps_registry.csv"
    registry = {r["file_num"]: r for r in read_csv(reg_path)}
    for fid, rec in current.items():
        prev = registry.get(fid, {})
        registry[fid] = {**rec, "first_seen": prev.get("first_seen") or today,
                         "last_seen": today, "active": "True"}
    for fid, rec in registry.items():
        if fid not in current:
            rec["active"] = "False"
    write_csv(reg_path, list(registry.values()), REGISTRY_FIELDS)

    # Snapshot summary row for this run.
    snap_path = DATA_DIR / "devapps_snapshots.csv"
    snaps = [s for s in read_csv(snap_path) if s["snapshot_date"] != today]
    active = list(current.values())
    snaps.append({
        "snapshot_date": today,
        "active_apps": len(active),
        "site_plans": sum(r["type"] == "Site Plan" for r in active),
        "rezonings": sum(r["type"] == "Zoning By-law Amendment" for r in active),
        "opas": sum(r["type"] == "Local Official Plan Amendment" for r in active),
        "condo_plans": sum("Condominium" in r["type"] for r in active),
        "units_est_site_plans": sum(int(r["units_est"] or 0) for r in active if r["type"] == "Site Plan"),
    })
    write_csv(snap_path, snaps, list(snaps[-1].keys()))
    print(f"devapps: {len(active)} active, registry {len(registry)}")


if __name__ == "__main__":
    main()
