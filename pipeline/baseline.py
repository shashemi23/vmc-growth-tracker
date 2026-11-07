"""Baseline projections with error bands, plus a running forecast scorecard.

Method (after Klein & Young, "An Introduction to Econometric Forecasting and
Forecasting Models", 1980: judge a forecaster by its track record, and keep
judgment as a documented adjustment to a mechanical baseline):

  * For each series, two simple methods are backtested on history:
      - "no change"     tomorrow looks like today
      - "damped trend"  recent growth continues but fades out
    The method with the lower backtest error is used.
  * The 80% band comes from the 10th-90th percentile of that method's past
    errors at the same horizon, so its width is earned, not assumed.
  * Every new projection is appended to forecast_log.csv. Once a target date
    has passed, the actual value, error and whether it fell inside the band
    are filled in. Claude's adjusted calls (source=claude) are scored the same way.

Outputs (src/data/):
  baseline.json       current projections + backtest accuracy per series
  forecast_log.csv    every projection made, scored when its target arrives
"""

from __future__ import annotations

import datetime as dt
import json
import math
from statistics import mean

from common import DATA_DIR, read_csv, write_csv

LOG_FIELDS = ["origin", "source", "series_id", "target", "forecast", "low", "high",
              "actual", "error_pct", "in_band", "logged_on"]
PHI = 0.9            # monthly damping for trends
BACKTEST_FROM = 2005  # ignore older history for monthly CMHC series


# ---------------------------------------------------------------- helpers

def add_months(d: dt.date, n: int) -> dt.date:
    y, m = divmod(d.month - 1 + n, 12)
    return dt.date(d.year + y, m + 1, 1)


def quantile(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    if not xs:
        return 0.0
    pos = (len(xs) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return xs[lo] + (xs[hi] - xs[lo]) * (pos - lo)


def fnum(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- series

class Series:
    """A projectable quantity: values by period, plus how to forecast and resolve it."""

    def __init__(self, sid, label, unit, values, horizon, kind, freq="M", min_origin=None, note=""):
        self.id, self.label, self.unit, self.note = sid, label, unit, note
        self.values = values      # {period (date, or int year): float}
        self.h = horizon          # months (freq M) or years (freq Y)
        self.kind = kind          # "level" (value at target) or "flow12" (sum of next 12 months)
        self.freq = freq
        self.min_origin = min_origin

    def shift(self, p, n):
        return add_months(p, n) if self.freq == "M" else p + n

    def target(self, origin):
        return self.shift(origin, self.h)

    def current(self, origin):
        if self.kind == "flow12":
            vals = [self.values.get(self.shift(origin, -k)) for k in range(12)]
            return None if None in vals else sum(vals)
        return self.values.get(origin)

    def actual(self, origin):
        if self.kind == "flow12":
            vals = [self.values.get(self.shift(origin, k)) for k in range(1, 13)]
            return None if None in vals else sum(vals)
        return self.values.get(self.target(origin))

    def forecast(self, origin, method):
        now = self.current(origin)
        if now is None or now <= 0:
            return None
        if method == "no change":
            return now
        # Damped trend: growth over the last year (3 years for annual data), fading out.
        back = 12 if self.freq == "M" else 3
        before = self.current(self.shift(origin, -back))
        if not before or before <= 0:
            return None
        g = math.log(now / before) / back
        if self.kind == "flow12":
            return now * math.exp(g * 12 * 0.5)  # half of last year's change carries into next year
        phi = PHI if self.freq == "M" else PHI ** 12
        steps = sum(phi ** k for k in range(1, self.h + 1))
        return now * math.exp(g * steps)

    def origins(self):
        return [p for p in sorted(self.values) if self.min_origin is None or p >= self.min_origin]

    def last_origin(self):
        return max(p for p in self.values if self.current(p) is not None)


def backtest(s: Series) -> dict:
    out = {}
    for method in ("no change", "damped trend"):
        errs = []
        for o in s.origins():
            f, a = s.forecast(o, method), s.actual(o)
            if f and a and a > 0:
                errs.append(math.log(a / f))
        if len(errs) >= 5:
            out[method] = {"n": len(errs),
                           "mae_pct": round(mean(abs(math.exp(e) - 1) for e in errs) * 100, 1),
                           "q10": quantile(errs, 0.10), "q90": quantile(errs, 0.90)}
    return out


# ---------------------------------------------------------------- data

def load_series() -> list[Series]:
    series = []
    hpi = read_csv(DATA_DIR / "trreb_vaughan_hpi.csv")
    for ht, label in [("Composite", "Typical Vaughan home (all types)"),
                      ("Apartment", "Typical Vaughan condo apartment")]:
        vals = {dt.date.fromisoformat(r["month"]): fnum(r["benchmark_price"])
                for r in hpi if r["home_type"] == ht and fnum(r["benchmark_price"])}
        for h in (6, 12):
            series.append(Series(f"hpi_{ht.lower()}_h{h}", f"{label}: benchmark price in {h} months",
                                 "$", vals, h, "level", note="TRREB MLS Home Price Index"))

    monthly = read_csv(DATA_DIR / "cmhc_vaughan_monthly.csv")
    cut = dt.date(BACKTEST_FROM, 1, 1)
    for col, label in [("All", "Vaughan housing starts, all types"), ("Apartment", "Vaughan apartment starts")]:
        vals = {dt.date.fromisoformat(r["date"]): fnum(r[col]) or 0.0
                for r in monthly if r["series"] == "starts"}
        series.append(Series(f"starts_{col.lower()}_next12", f"{label}: total over the next 12 months",
                             "units", vals, 12, "flow12", min_origin=cut,
                             note="CMHC Starts and Completions Survey"))
    uc = {dt.date.fromisoformat(r["date"]): fnum(r["All"]) for r in monthly
          if r["series"] == "under_construction" and fnum(r["All"])}
    series.append(Series("under_construction_h12", "Vaughan units under construction in 12 months",
                         "units", uc, 12, "level", min_origin=cut, note="CMHC Starts and Completions Survey"))

    rent = read_csv(DATA_DIR / "cmhc_rental_zone.csv")
    rv = {int(r["year"]): fnum(r["avg_rent"]) for r in rent
          if r["bedroom"] == "Total" and r["geography"] != "Toronto CMA" and fnum(r["avg_rent"])}
    series.append(Series("rent_zone_h1", "Average rent next October (Richmond Hill/Vaughan/King zone)",
                         "$/month", rv, 1, "level", freq="Y", note="CMHC Rental Market Survey"))
    return series


def period_str(s: Series, p) -> str:
    return p.isoformat() if s.freq == "M" else str(p)


def parse_period(s: Series, text: str):
    return dt.date.fromisoformat(text) if s.freq == "M" else int(text)


# ---------------------------------------------------------------- main

def main() -> None:
    today = dt.date.today().isoformat()
    series = load_series()
    by_id = {s.id: s for s in series}
    out = []
    log_path = DATA_DIR / "forecast_log.csv"
    log = read_csv(log_path)
    keys = {(r["origin"], r["source"], r["series_id"]) for r in log}

    for s in series:
        bt = backtest(s)
        if not bt:
            continue
        method = min(bt, key=lambda m: (bt[m]["mae_pct"], m != "no change"))
        o = s.last_origin()
        f = s.forecast(o, method)
        if f is None:
            continue
        low, high = f * math.exp(bt[method]["q10"]), f * math.exp(bt[method]["q90"])
        rec = {
            "id": s.id, "label": s.label, "unit": s.unit, "source_note": s.note,
            "origin": period_str(s, o), "target": period_str(s, s.target(o)),
            "current": round(s.current(o), 1), "method": method,
            "forecast": round(f, 1), "low": round(low, 1), "high": round(high, 1), "interval": 0.8,
            "backtest": {m: {"n": v["n"], "typical_error_pct": v["mae_pct"]} for m, v in bt.items()},
        }
        out.append(rec)
        # One log row per new data point (origin), not per weekly run.
        key = (rec["origin"], "baseline", s.id)
        if key not in keys:
            log.append({"origin": rec["origin"], "source": "baseline", "series_id": s.id,
                        "target": rec["target"], "forecast": rec["forecast"], "low": rec["low"],
                        "high": rec["high"], "logged_on": today})
            keys.add(key)

    # Score every logged forecast (baseline or Claude) whose target has arrived.
    for r in log:
        s = by_id.get(r["series_id"])
        if not s or r.get("actual"):
            continue
        a = s.actual(parse_period(s, r["origin"]))
        if a is None:
            continue
        f, lo, hi = float(r["forecast"]), float(r["low"]), float(r["high"])
        r.update(actual=round(a, 1), error_pct=round((a / f - 1) * 100, 1), in_band=str(lo <= a <= hi))

    (DATA_DIR / "baseline.json").write_text(
        json.dumps({"generated": today, "series": out}, indent=1) + "\n", encoding="utf-8")
    write_csv(log_path, log, LOG_FIELDS)
    scored = sum(1 for r in log if r.get("actual"))
    print(f"baseline: {len(out)} series; log {len(log)} rows, {scored} scored")


if __name__ == "__main__":
    main()
