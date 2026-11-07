"""Fetch CMHC housing data for Vaughan and the VMC census tract.

Source: CMHC Housing Market Information Portal (HMIP) CSV export, the same
endpoint the `cmhc` R package uses. Not an official API, so it may change.

Outputs (src/data/):
  cmhc_vaughan_monthly.csv   starts / completions / under construction, monthly, 1990+,
                             one column per dwelling type
  cmhc_vmc_tract_annual.csv  starts / completions for VMC census tract(s), annual
  cmhc_rental_zone.csv       purpose-built rental vacancy and average rent (October survey),
                             Richmond Hill/Vaughan/King zone vs Toronto CMA
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import time

from common import DATA_DIR, http, read_csv, write_csv

URL = "https://www03.cmhc-schl.gc.ca/hmip-pimh/en/TableMapChart/ExportTable"
VAUGHAN_CSD = "3519028"
TORONTO_CMA_CMHC = "2270"
# 2021 census tract containing the VMC (also covers Concord employment lands).
VMC_TRACTS = ["0411.08"]
TRACT_FIRST_YEAR = 2011
# CMHC archived the census-tract completions series after 2022 ("This data series is now archived").
TRACT_COMPLETIONS_LAST_YEAR = 2022
RENTAL_FIRST_YEAR = 2010
RENTAL_ZONE_MATCH = "Vaughan"
RENTAL_ZONE_LABEL = "Richmond Hill/Vaughan/King"

MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def export(**params) -> list[list[str]]:
    raw = http(URL, data={"exportType": "csv", **params})
    text = raw.decode("latin-1")
    if text.lstrip().startswith("<"):
        raise RuntimeError(f"CMHC returned HTML for {params}")
    return list(csv.reader(io.StringIO(text)))


def table_body(rows: list[list[str]]):
    """Return (header, data_rows) for the table that starts at the first ',x,y' row.

    Returns ([], []) when the export holds no table (e.g. no data for that period).
    """
    start = next((i for i, r in enumerate(rows) if r and r[0] == "" and len(r) > 2), None)
    if start is None:
        return [], []
    header = rows[start]
    body = []
    for r in rows[start + 1:]:
        if not r or not r[0].strip() or r[0].startswith(("Source", "Notes")):
            break
        body.append(r)
    return header, body


def num(s: str):
    s = (s or "").replace(",", "").replace("$", "").strip()
    try:
        return float(s) if "." in s else int(s)
    except ValueError:
        return ""  # "**" = suppressed, "-" = none


MONTHLY_TYPES = ["Single", "Semi-Detached", "Row", "Apartment", "All"]


def vaughan_monthly() -> None:
    """One row per (month, series) with a column per dwelling type (wide = ~4x smaller)."""
    rows = []
    for series, table in [("starts", "1.2.1"), ("completions", "1.2.2"), ("under_construction", "1.2.3")]:
        header, body = table_body(export(TableId=table, GeographyId=VAUGHAN_CSD,
                                         GeographyTypeId="4", Frequency="Monthly"))
        if not header:
            raise RuntimeError(f"CMHC table {table} returned no data for Vaughan")
        types = [h for h in header[1:] if h]
        for r in body:
            mon, year = r[0].split()
            row = {"date": f"{year}-{MONTHS[mon]:02d}-01", "series": series}
            row.update({t: num(v) for t, v in zip(types, r[1:])})
            rows.append(row)
        time.sleep(1)
    write_csv(DATA_DIR / "cmhc_vaughan_monthly.csv", rows, ["date", "series", *MONTHLY_TYPES])
    print(f"cmhc vaughan monthly: {len(rows)} rows")


def vmc_tract_annual() -> None:
    """Annual tract data. Each request downloads the whole Toronto CMA (slow), so
    years older than last year are reused from the existing CSV."""
    path = DATA_DIR / "cmhc_vmc_tract_annual.csv"
    this_year = dt.date.today().year
    cached = [r for r in read_csv(path) if int(r["year"]) < this_year - 1]
    have = {(int(r["year"]), r["series"]) for r in cached}
    rows: list[dict] = list(cached)
    for year in range(TRACT_FIRST_YEAR, this_year + 1):
        for series, table in [("starts", "1.1.1.11"), ("completions", "1.1.2.11")]:
            if (year, series) in have:
                continue
            if series == "completions" and year > TRACT_COMPLETIONS_LAST_YEAR:
                continue
            header, body = table_body(export(TableId=table, GeographyId=TORONTO_CMA_CMHC,
                                             GeographyTypeId="3", Frequency="Annual",
                                             **{"ForTimePeriod.Year": year}))
            if not header:
                print(f"  no {series} table for {year}, skipping")
                continue
            types = [h for h in header[1:] if h]
            for r in body:
                if r[0] in VMC_TRACTS:
                    for t, v in zip(types, r[1:]):
                        rows.append({"year": year, "partial_year": year == this_year,
                                     "series": series, "tract": r[0], "dwelling_type": t,
                                     "units": num(v)})
            time.sleep(1)
    write_csv(path, rows,
              ["year", "partial_year", "series", "tract", "dwelling_type", "units"])
    print(f"cmhc vmc tract annual: {len(rows)} rows")


def zone_rental() -> None:
    """October Rental Market Survey for the CMHC zone containing Vaughan, plus the
    Toronto CMA total for comparison. CMHC suppresses most Vaughan CSD values, so
    the zone ("Richmond Hill/Vaughan/King") is the finest usable geography.
    Past years are reused from the existing CSV."""
    path = DATA_DIR / "cmhc_rental_zone.csv"
    fields = ["year", "geography", "bedroom", "vacancy_rate", "vacancy_rate_quality",
              "avg_rent", "avg_rent_quality"]
    this_year = dt.date.today().year
    cached = [r for r in read_csv(path) if int(r["year"]) < this_year - 1]
    have = {int(r["year"]) for r in cached}
    merged: dict[tuple, dict] = {}
    for year in range(RENTAL_FIRST_YEAR, this_year + 1):
        if year in have:
            continue
        for metric, table in [("vacancy_rate", "2.1.1.3"), ("avg_rent", "2.1.11.3")]:
            rows = export(TableId=table, GeographyId=TORONTO_CMA_CMHC, GeographyTypeId="3",
                          Frequency="Annual", **{"ForTimePeriod.Year": year})
            start = next((i for i, r in enumerate(rows) if r and r[0] == "" and len(r) > 2), None)
            if start is None:
                continue  # survey for this year not published yet
            # Header alternates value / reliability-code columns: ",Studio,,1 Bedroom,,..."
            cols = [(i, h) for i, h in enumerate(rows[start]) if i > 0 and h]
            for r in rows[start + 1:]:
                if not r or r[0].startswith(("Notes", "Source")):
                    break
                if RENTAL_ZONE_MATCH in r[0]:
                    geo = RENTAL_ZONE_LABEL
                elif r[0] == "":
                    geo = "Toronto CMA"  # unlabelled total row
                else:
                    continue
                for i, bedroom in cols:
                    rec = merged.setdefault((year, geo, bedroom),
                                            {"year": year, "geography": geo, "bedroom": bedroom})
                    rec[metric] = num(r[i]) if i < len(r) else ""
                    rec[f"{metric}_quality"] = r[i + 1].strip() if i + 1 < len(r) else ""
            time.sleep(1)
    rows_out = cached + list(merged.values())
    write_csv(path, rows_out, fields)
    print(f"cmhc rental zone: {len(rows_out)} rows")


if __name__ == "__main__":
    vaughan_monthly()
    vmc_tract_annual()
    zone_rental()
