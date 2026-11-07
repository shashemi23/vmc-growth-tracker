"""Fetch Vaughan resale-market stats from TRREB's monthly Market Watch PDFs.

Source: Toronto Regional Real Estate Board, Market Watch
  https://trreb.ca/wp-content/files/market-stats/market-watch/mwYYMM.pdf
Each report has a "summary of existing home transactions" table per home type
(one row per municipality, including Vaughan) and an MLS Home Price Index table.

Months already in the CSV are not downloaded again (the PDFs are 1-2 MB each).

Outputs (src/data/):
  trreb_vaughan_monthly.csv   month, home_type, sales, avg/median price, listings, SP/LP
  trreb_vaughan_hpi.csv       month, home_type, HPI index, benchmark price, year-over-year change

Needs: pdfplumber (see requirements.txt).
"""

from __future__ import annotations

import datetime as dt
import io
from concurrent.futures import ProcessPoolExecutor

import pdfplumber

from common import DATA_DIR, http, read_csv, write_csv

URL = "https://trreb.ca/wp-content/files/market-stats/market-watch/mw{yymm}.pdf"
FIRST_MONTH = dt.date(2015, 1, 1)
AREA = "Vaughan"

SALES_FIELDS = ["month", "home_type", "sales", "dollar_volume", "avg_price", "median_price",
                "new_listings", "active_listings", "snlr_pct", "months_inventory", "sp_lp_pct",
                "source_url"]
HPI_FIELDS = ["month", "home_type", "index", "benchmark_price", "yoy_pct", "source_url"]
HPI_TYPES = ["Composite", "Detached", "Semi-Detached/Attached", "Townhouse", "Apartment"]

# Checked in order: more specific titles first ("Semi-Detached" contains "Detached").
# Title wording changed over the years (e.g. "CONDOMINIUM APARTMENT", "CONDO APT", "Condo Apartment").
PAGE_TYPES = [
    ("detached condo", None),
    ("det condo", None),
    ("co-op", None),
    ("co-ownership", None),
    ("link", None),
    ("condo apartment", "Condo Apartment"),
    ("condo apt", "Condo Apartment"),
    ("condominium apartment", "Condo Apartment"),
    ("condo townhouse", "Condo Townhouse"),
    ("condominium townhouse", "Condo Townhouse"),
    ("semi-detached", "Semi-Detached"),
    ("townhouse", "Townhouse"),       # "Att/Row/Townhouse"
    ("twnhouse", "Townhouse"),
    ("detached", "Detached"),
    ("all home types", "All"),
]


def num(tok: str):
    t = tok.replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(t) if "." in t else int(t)
    except ValueError:
        return ""


def page_kind(header: str):
    h = header.lower()
    if "year-to-date" in h:
        return None
    if "home price index" in h:
        return "HPI"
    for key, label in PAGE_TYPES:
        if key in h:
            return label
    return None


def parse_pdf(data: bytes, month: str, url: str):
    sales_rows, hpi_rows = [], []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            lines = text.splitlines()
            row = next((l for l in lines if l.startswith(AREA + " ")), None)
            if not row:
                continue
            kind = page_kind(" ".join(lines[:4]))
            if kind is None:
                continue
            toks = row[len(AREA):].split()
            if kind == "HPI":
                if hpi_rows:
                    continue
                vals = [num(t) for t in toks]
                for i, ht in enumerate(HPI_TYPES):
                    chunk = vals[i * 3:(i + 1) * 3]
                    if len(chunk) == 3:
                        hpi_rows.append({"month": month, "home_type": ht, "index": chunk[0],
                                         "benchmark_price": chunk[1], "yoy_pct": chunk[2],
                                         "source_url": url})
                continue
            if any(r["home_type"] == kind for r in sales_rows):
                continue  # first table of a type wins
            if any(t.count("$") > 1 for t in toks):
                # Mid-2022 to mid-2025 reports overlay two tables on one page, so
                # values interleave ("$$11,,220514..."). Skip rather than guess.
                continue
            rec = {"month": month, "home_type": kind, "source_url": url}
            if len(toks) < 5:  # no sales: "Vaughan 0 3 4" = sales, new listings, active
                vals = [num(t) for t in toks]
                rec.update(sales=vals[0] if vals else 0,
                           new_listings=vals[1] if len(vals) > 1 else "",
                           active_listings=vals[2] if len(vals) > 2 else "")
            else:
                rec.update(sales=num(toks[0]), dollar_volume=num(toks[1]), avg_price=num(toks[2]),
                           median_price=num(toks[3]), new_listings=num(toks[4]))
                rest = toks[5:]
                if kind == "All":
                    # SNLR %, active listings, months of inventory, SP/LP %, DOM...
                    if len(rest) >= 4:
                        rec.update(snlr_pct=num(rest[0]), active_listings=num(rest[1]),
                                   months_inventory=num(rest[2]), sp_lp_pct=num(rest[3]))
                elif len(rest) >= 2:
                    # active listings, SP/LP %, DOM...
                    rec.update(active_listings=num(rest[0]), sp_lp_pct=num(rest[1]))
            sales_rows.append(rec)
    return sales_rows, hpi_rows


def month_iter(start: dt.date, end: dt.date):
    d = start
    while d <= end:
        yield d
        d = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def fetch_month(month: str):
    """Download and parse one month. Runs in a worker process."""
    url = URL.format(yymm=dt.date.fromisoformat(month).strftime("%y%m"))
    try:
        data = http(url, retries=2, timeout=90)
    except RuntimeError:
        return month, None, None, "not available"
    if not data.startswith(b"%PDF"):
        return month, None, None, "not a PDF"
    s, h = parse_pdf(data, month, url)
    if not s and not h:
        return month, None, None, f"no {AREA} rows parsed"
    return month, s, h, f"{len(s)} home types, {len(h)} HPI rows"


def main() -> None:
    sales_path = DATA_DIR / "trreb_vaughan_monthly.csv"
    hpi_path = DATA_DIR / "trreb_vaughan_hpi.csv"
    sales = read_csv(sales_path)
    hpi = read_csv(hpi_path)
    # A month is done once either table has it (some months only yield the HPI table).
    have = {r["month"] for r in sales} | {r["month"] for r in hpi}
    today = dt.date.today()
    todo = [d.isoformat() for d in month_iter(FIRST_MONTH, dt.date(today.year, today.month, 1))
            if d.isoformat() not in have]
    # Parsing a 27-page PDF takes ~15 s, so a backfill runs months in parallel.
    with ProcessPoolExecutor(max_workers=min(6, max(1, len(todo)))) as pool:
        for month, s, h, msg in pool.map(fetch_month, todo):
            print(f"  {month}: {msg}", flush=True)
            if s or h:
                sales += s or []
                hpi += h or []
                # Save as we go so an interrupted backfill keeps its progress.
                write_csv(sales_path, sales, SALES_FIELDS)
                write_csv(hpi_path, hpi, HPI_FIELDS)
    write_csv(sales_path, sales, SALES_FIELDS)
    write_csv(hpi_path, hpi, HPI_FIELDS)
    print(f"trreb: {len({r['month'] for r in sales})} months")


if __name__ == "__main__":
    main()
