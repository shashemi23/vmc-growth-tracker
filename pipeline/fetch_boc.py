"""Fetch interest rates from the Bank of Canada Valet API.

Outputs (src/data/):
  boc_rates.csv   month, series, rate (last observation of each month)
    policy_rate          V39079     target for the overnight rate
    mortgage_5yr_posted  V80691335  5-year conventional mortgage, posted rate
                                    (actual contract rates are usually lower)
"""

from __future__ import annotations

import json

from common import DATA_DIR, http, write_csv

SERIES = {"V39079": "policy_rate", "V80691335": "mortgage_5yr_posted"}
URL = "https://www.bankofcanada.ca/valet/observations/{codes}/json"


def main() -> None:
    raw = http(URL.format(codes=",".join(SERIES)), params={"start_date": "2010-01-01"})
    obs = json.loads(raw)["observations"]
    last: dict[tuple, dict] = {}
    for o in obs:
        month = o["d"][:7] + "-01"
        for code, name in SERIES.items():
            v = o.get(code, {}).get("v")
            if v not in (None, ""):
                last[(month, name)] = {"month": month, "series": name, "rate": float(v)}
    rows = list(last.values())
    if not rows:
        raise SystemExit("No Bank of Canada observations returned")
    write_csv(DATA_DIR / "boc_rates.csv", rows, ["month", "series", "rate"])
    print(f"boc: {len(rows)} rows")


if __name__ == "__main__":
    main()
