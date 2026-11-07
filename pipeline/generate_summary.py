"""Generate the plain-language "What it means for you" summary with Claude.

Two calls:
  1. Research: Claude uses web search to collect dated national / provincial /
     regional / local events that affect VMC housing and development.
  2. Writing: Claude turns the data digest + research into structured JSON
     (status, personas, scenarios, events, watch list). Every claim must cite
     a source id: "data:*" (this repo's datasets) or "web:N" (a page Claude
     actually retrieved in step 1).

Guardrail: after generation, any citation id not in the known source table is
removed, and any claim left without a valid citation is dropped. The number of
dropped items is recorded in the output.

Output: src/data/summary.json
Needs: ANTHROPIC_API_KEY (or another credential the SDK resolves).
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import sys
from collections import defaultdict

import anthropic

from common import DATA_DIR, write_json

MODEL = "claude-opus-5-5"
FALLBACK_BETA = "server-side-fallback-2026-07-01"
OUT = DATA_DIR / "summary.json"
SITE = "https://shashemi23.github.io/vmc-growth-tracker"


# ---------------------------------------------------------------- data digest

def load(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def digest() -> tuple[dict, dict]:
    """Return (facts keyed by source id, source table entries for data ids)."""
    facts, sources = {}, {}

    def add(sid, title, page, value):
        facts[sid] = value
        sources[sid] = {"kind": "data", "title": title, "url": f"{SITE}/{page}"}

    reg = load("devapps_registry.csv")
    active = [r for r in reg if r["active"] == "True"]
    snaps = load("devapps_snapshots.csv")
    by_type = defaultdict(int)
    for r in active:
        by_type[r["type"]] += 1
    recent_cut = (dt.date.today() - dt.timedelta(days=180)).isoformat()
    add("data:devapps", "Active VMC development applications (York Region)", "development", {
        "active_applications": len(active),
        "by_type": dict(by_type),
        "units_proposed_in_active_site_plans_est": snaps[-1]["units_est_site_plans"] if snaps else None,
        "applications_received_last_180_days": sum(r["date_received"] >= recent_cut for r in active),
        "largest_active_proposals": sorted(
            ({"name": r["name"], "type": r["type"], "units_est": int(r["units_est"]),
              "storeys_max": r["storeys_max"], "stage": r["stage"]}
             for r in active if r["units_est"]), key=lambda x: -x["units_est"])[:5],
        "closed_since_tracking": len(reg) - len(active),
        "tracking_started": snaps[0]["snapshot_date"] if snaps else None,
        "note": "Unit counts are parsed from application text; one project can have several files.",
    })

    tract = load("cmhc_vmc_tract_annual.csv")
    add("data:tract", "CMHC starts and completions, VMC census tract 0411.08", "housing", [
        {"year": int(r["year"]), "series": r["series"], "units": f(r["units"]),
         "year_to_date": r["partial_year"] == "True"}
        for r in tract if r["dwelling_type"] == "All"])

    monthly = load("cmhc_vaughan_monthly.csv")
    annual = defaultdict(float)
    for r in monthly:
        if r["series"] in ("starts", "completions") and r["dwelling_type"] == "All":
            annual[(r["series"], r["date"][:4])] += f(r["units"]) or 0
    uc = [r for r in monthly if r["series"] == "under_construction" and r["dwelling_type"] == "All"]
    latest_year = max(int(y) for _, y in annual) if annual else 0
    add("data:vaughan_supply", "CMHC starts, completions, under construction, City of Vaughan", "housing", {
        "annual_totals": {f"{s} {y}": v for (s, y), v in sorted(annual.items()) if int(y) >= latest_year - 9},
        "latest_month": uc[-1]["date"] if uc else None,
        "note": f"{latest_year} totals are year to date" if uc and not uc[-1]["date"].startswith(f"{latest_year}-12") else "",
        "under_construction_latest": f(uc[-1]["units"]) if uc else None,
        "under_construction_year_ago": f(uc[-13]["units"]) if len(uc) > 13 else None,
        "under_construction_peak": max((f(r["units"]) or 0 for r in uc), default=None),
    })

    rental = load("cmhc_rental_zone.csv")
    add("data:rental", "CMHC Rental Market Survey, Richmond Hill/Vaughan/King zone vs Toronto CMA", "housing", [
        {"year": int(r["year"]), "geography": r["geography"], "avg_rent": f(r["avg_rent"]),
         "vacancy_rate_pct": f(r["vacancy_rate"])}
        for r in rental if r["bedroom"] == "Total" and int(r["year"]) >= dt.date.today().year - 8])

    hpi = load("trreb_vaughan_hpi.csv")
    trreb = load("trreb_vaughan_monthly.csv")
    if hpi:
        def benchmark(ht):
            s = sorted((r for r in hpi if r["home_type"] == ht and f(r["benchmark_price"])),
                       key=lambda r: r["month"])
            if not s:
                return None
            last = s[-1]
            by_month = {r["month"]: f(r["benchmark_price"]) for r in s}

            def ago(years):
                d = dt.date.fromisoformat(last["month"])
                return by_month.get(d.replace(year=d.year - years).isoformat())

            peak = max(s, key=lambda r: f(r["benchmark_price"]))
            return {
                "latest_month": last["month"], "benchmark_price": f(last["benchmark_price"]),
                "yoy_pct": f(last["yoy_pct"]),
                "benchmark_1y_ago": ago(1), "benchmark_5y_ago": ago(5), "benchmark_10y_ago": ago(10),
                "peak_benchmark": f(peak["benchmark_price"]), "peak_month": peak["month"],
            }

        latest_all = max((r for r in trreb if r["home_type"] == "All"), key=lambda r: r["month"], default=None)
        latest_condo = max((r for r in trreb if r["home_type"] == "Condo Apartment" and r["avg_price"]),
                           key=lambda r: r["month"], default=None)
        add("data:resale", "TRREB Market Watch, Vaughan resale (MLS Home Price Index and sales)", "housing", {
            "benchmark_price_typical_home": {ht: benchmark(ht) for ht in
                                             ["Composite", "Detached", "Townhouse", "Apartment"]},
            "latest_sales_all_types": latest_all and {
                "month": latest_all["month"], "sales": f(latest_all["sales"]),
                "avg_price": f(latest_all["avg_price"]), "active_listings": f(latest_all["active_listings"]),
                "months_of_inventory": f(latest_all["months_inventory"]),
                "sale_to_list_pct": f(latest_all["sp_lp_pct"])},
            "latest_condo_apartment_sales": latest_condo and {
                "month": latest_condo["month"], "sales": f(latest_condo["sales"]),
                "avg_price": f(latest_condo["avg_price"]), "active_listings": f(latest_condo["active_listings"])},
            "note": "Benchmark = value of a typical home (steadier than averages). Prices are Vaughan-wide; "
                    "the VMC is mostly apartments. Monthly sales are missing for mid-2022 to mid-2025.",
        })

    boc = load("boc_rates.csv")
    if boc:
        def rate(series, months_back=0):
            s = [r for r in boc if r["series"] == series]
            return (s[-1 - months_back]["month"], f(s[-1 - months_back]["rate"])) if len(s) > months_back else None
        add("data:rates", "Bank of Canada policy rate and posted 5-year mortgage rate", "housing", {
            "policy_rate_latest": rate("policy_rate"), "policy_rate_12m_ago": rate("policy_rate", 12),
            "mortgage_5yr_posted_latest": rate("mortgage_5yr_posted"),
            "mortgage_5yr_posted_12m_ago": rate("mortgage_5yr_posted", 12),
            "note": "Posted rates are higher than typical negotiated rates.",
        })

    return facts, sources


# ---------------------------------------------------------------- Claude calls

def check(resp) -> None:
    if resp.stop_reason == "refusal":
        cat = resp.stop_details.category if resp.stop_details else None
        raise SystemExit(f"Claude declined the request (category: {cat}); keeping previous summary.")
    if resp.stop_reason == "max_tokens":
        raise SystemExit("Response hit max_tokens; keeping previous summary.")


RESEARCH_PROMPT = """Today is {today}. I maintain a public dashboard about growth in the
Vaughan Metropolitan Centre (VMC), a new high-rise downtown in Vaughan, Ontario
(York Region, Greater Toronto Area). It is mostly condo towers, plus office and retail,
next to the VMC subway station.

Use web search to find concrete, dated events and announcements from roughly the past
six months, plus anything scheduled for the next twelve months, that could affect housing
demand, prices, rents, or construction in the VMC. Cover:
- National: Bank of Canada rate decisions and next decision dates; immigration and
  temporary resident / international student targets; federal housing measures (GST
  rebates, amortization, mortgage rules, foreign buyer ban); trade/tariff effects on
  GTA jobs.
- Provincial: Ontario housing legislation, development charges, rent rules, transit.
- Regional/local: York Region and City of Vaughan development charges, major VMC
  project approvals or cancellations, transit, schools/parks, large employers.
- GTA condo market conditions (presale sales, unsold inventory, cancellations).

Prefer primary sources (bankofcanada.ca, canada.ca, ontario.ca, york.ca, vaughan.ca,
cmhc-schl.gc.ca, trreb.ca) and established news outlets. For each event give: date,
level (national/provincial/regional/local), what happened in one or two sentences,
and the URL you got it from. Only report what the sources say."""


def research(client: anthropic.Anthropic) -> tuple[str, dict]:
    messages = [{"role": "user", "content": RESEARCH_PROMPT.format(today=dt.date.today().isoformat())}]
    tools = [{"type": "web_search_20260209", "name": "web_search", "max_uses": 12,
              "user_location": {"type": "approximate", "city": "Vaughan",
                                "region": "Ontario", "country": "CA"}}]
    found: dict[str, dict] = {}
    text_parts: list[str] = []
    for _ in range(5):
        resp = client.beta.messages.create(
            model=MODEL, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
            output_config={"effort": "high"}, tools=tools, messages=messages)
        check(resp)
        for block in resp.content:
            if block.type == "web_search_tool_result" and isinstance(block.content, list):
                for r in block.content:
                    found.setdefault(r.url, {"title": r.title, "page_age": getattr(r, "page_age", None)})
            elif block.type == "text":
                text_parts.append(block.text)
                for c in getattr(block, "citations", None) or []:
                    url = getattr(c, "url", None)
                    if url:
                        found.setdefault(url, {"title": getattr(c, "title", None) or url, "page_age": None})
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        break
    return "\n".join(text_parts), found


def build_schema() -> dict:
    cite = {"type": "array", "items": {"type": "string"},
            "description": "Source ids backing this item, e.g. data:resale or web:3"}

    def obj(props: dict) -> dict:
        return {"type": "object", "additionalProperties": False,
                "required": list(props), "properties": props}

    point = obj({"text": {"type": "string"}, "cite": cite})
    direction = {"type": "string", "enum": ["helps growth", "slows growth", "mixed"]}
    return obj({
        "headline": {"type": "string", "description": "2-3 plain sentences on the VMC right now"},
        "headline_cite": cite,
        "status": {"type": "array", "items": obj({
            "area": {"type": "string", "enum": ["supply", "demand", "prices", "rents", "momentum"]},
            "signal": {"type": "string", "enum": ["rising", "steady", "falling", "mixed"]},
            "label": {"type": "string", "description": "3-6 words"},
            "explanation": {"type": "string"},
            "cite": cite})},
        "personas": {"type": "array", "items": obj({
            "id": {"type": "string", "enum": ["first_time_buyer", "renter", "family", "seller",
                                              "investor", "downsizer"]},
            "bottom_line": {"type": "string", "description": "One plain sentence"},
            "points": {"type": "array", "items": point},
            "watch": {"type": "array", "items": {"type": "string"}}})},
        "scenarios": {"type": "array", "items": obj({
            "name": {"type": "string", "enum": ["optimistic", "base", "pessimistic"]},
            "likelihood": {"type": "string", "enum": ["less likely", "most likely", "possible"]},
            "horizon": {"type": "string", "description": "e.g. next 12-24 months"},
            "summary": {"type": "string"},
            "drivers": {"type": "array", "items": obj({
                "text": {"type": "string"}, "direction": direction, "cite": cite})}})},
        "events": {"type": "array", "items": obj({
            "date": {"type": "string", "description": "YYYY-MM-DD or YYYY-MM"},
            "level": {"type": "string", "enum": ["national", "provincial", "regional", "local"]},
            "title": {"type": "string"},
            "impact": {"type": "string", "description": "What it means for the VMC, plainly"},
            "direction": direction,
            "cite": cite})},
        "watch_list": {"type": "array", "items": obj({
            "signal": {"type": "string"},
            "threshold": {"type": "string"},
            "why": {"type": "string"},
            "cite": cite})},
    })


WRITE_SYSTEM = """You write the "What it means for you" page of a public dashboard about the
Vaughan Metropolitan Centre (VMC). Readers are ordinary people with no economics
background: first-time buyers, renters, young families, people planning to sell, small
investors, downsizers.

Rules:
- Plain language, about a grade 8 reading level. Short sentences. Explain any term you use.
- Every number must come from the DATA DIGEST or a cited web source. Never invent figures.
- Cite every point, status item, driver, event and watch item with source ids from the
  SOURCE TABLE (e.g. "data:resale", "web:4"). Use only ids that appear in the table.
- Outlook is scenarios with likelihoods, never a single price prediction or a guarantee.
- Be balanced: say what favours each reader and what works against them.
- Educational only: no instructions to buy or sell, no financial advice.
- Note limits where relevant: rents are for a wider CMHC zone, resale prices are
  Vaughan-wide (the VMC is mostly condo apartments), the census tract is bigger than the VMC.
- Cover all six personas, all three scenarios, 4-10 events, 4-8 watch-list items."""


def write(client: anthropic.Anthropic, facts: dict, research_text: str, sources: dict) -> dict:
    table = "\n".join(f"{sid}: {s['title']} ({s['url']})" for sid, s in sources.items())
    user = (f"Today is {dt.date.today().isoformat()}.\n\n"
            f"<source_table>\n{table}\n</source_table>\n\n"
            f"<data_digest>\n{json.dumps(facts, indent=1, default=str)}\n</data_digest>\n\n"
            f"<research_notes>\n{research_text}\n</research_notes>")
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
        system=WRITE_SYSTEM,
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": build_schema()}},
        messages=[{"role": "user", "content": user}])
    check(resp)
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------- validation

def validate(summary: dict, valid_ids: set) -> int:
    """Strip unknown citation ids; drop items left with none. Returns items dropped."""
    dropped = 0

    def clean(items: list) -> list:
        nonlocal dropped
        kept = []
        for it in items:
            it["cite"] = [c for c in it.get("cite", []) if c in valid_ids]
            if it["cite"]:
                kept.append(it)
            else:
                dropped += 1
        return kept

    summary["headline_cite"] = [c for c in summary.get("headline_cite", []) if c in valid_ids]
    summary["status"] = clean(summary.get("status", []))
    summary["events"] = clean(summary.get("events", []))
    summary["watch_list"] = clean(summary.get("watch_list", []))
    for p in summary.get("personas", []):
        p["points"] = clean(p.get("points", []))
    for s in summary.get("scenarios", []):
        s["drivers"] = clean(s.get("drivers", []))
    return dropped


def cited_ids(summary: dict) -> set:
    used = set(summary["headline_cite"])
    for key in ("status", "events", "watch_list"):
        used |= {c for it in summary[key] for c in it["cite"]}
    for p in summary["personas"]:
        used |= {c for it in p["points"] for c in it["cite"]}
    for s in summary["scenarios"]:
        used |= {c for it in s["drivers"] for c in it["cite"]}
    return used


def main() -> None:
    force = "--force" in sys.argv
    if OUT.exists() and not force:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        age = dt.date.today() - dt.date.fromisoformat((prev.get("generated") or "2000-01-01")[:10])
        if age.days < 6:
            print(f"summary: generated {age.days} days ago, skipping (use --force)")
            return

    client = anthropic.Anthropic()
    facts, sources = digest()
    research_text, found = research(client)
    for i, (url, meta) in enumerate(found.items(), 1):
        sources[f"web:{i}"] = {"kind": "web", "title": meta["title"] or url, "url": url,
                               "page_age": meta.get("page_age")}
    summary = write(client, facts, research_text, sources)
    dropped = validate(summary, set(sources))
    used = cited_ids(summary)
    summary.update({
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "model": MODEL,
        "dropped_uncited_items": dropped,
        "sources": {sid: s for sid, s in sources.items() if sid in used},
    })
    write_json(OUT, summary)
    print(f"summary: {len(summary['sources'])} sources cited, {dropped} uncited items dropped")


if __name__ == "__main__":
    main()
