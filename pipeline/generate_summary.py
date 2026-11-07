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
import html
import io
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

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
        if r["series"] in ("starts", "completions"):
            annual[(r["series"], r["date"][:4])] += f(r["All"]) or 0
    uc = [{"date": r["date"], "units": r["All"]} for r in monthly if r["series"] == "under_construction"]
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

    bl = load_baseline()
    if bl:
        add("data:baseline", "Baseline projections with 80% bands, backtested on history", "outlook#baseline", [
            {k: s[k] for k in ("id", "label", "unit", "origin", "target", "current", "method",
                               "forecast", "low", "high", "backtest")} for s in bl["series"]])

    return facts, sources


def load_baseline() -> dict | None:
    path = DATA_DIR / "baseline.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


APPROVED_PATH = Path(__file__).resolve().parent / "approved_sources.txt"


def load_approved() -> list[str]:
    """Domains the summary may cite (pipeline/approved_sources.txt). Empty list = no restriction."""
    if not APPROVED_PATH.exists():
        return []
    lines = (l.split("#", 1)[0].strip().lower() for l in APPROVED_PATH.read_text(encoding="utf-8").splitlines())
    return [l for l in lines if l]


def is_approved(url: str, approved: list[str]) -> bool:
    if not approved:
        return True
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    for d in approved:
        if d.startswith("*."):
            if host.endswith(d[1:]):  # ".example.com"
                return True
        elif host == d:
            return True
    return False


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
    tool = {"type": "web_search_20260209", "name": "web_search", "max_uses": 12,
            "user_location": {"type": "approximate", "city": "Vaughan",
                              "region": "Ontario", "country": "CA"}}
    approved = load_approved()
    if approved:
        # web_search matches subdomains itself, so "*.example.com" becomes "example.com".
        tool["allowed_domains"] = sorted({d.removeprefix("*.") for d in approved})
    tools = [tool]
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


def build_schema(baseline_ids: list[str]) -> dict:
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
            "assumptions": {"type": "array", "items": obj({
                "driver": {"type": "string", "description": "e.g. Bank of Canada policy rate"},
                "assumption": {"type": "string",
                               "description": "Concrete and checkable, e.g. 'falls to 2.0-2.25% by late 2027'"},
                "cite": cite})},
            "drivers": {"type": "array", "items": obj({
                "text": {"type": "string"}, "direction": direction, "cite": cite})}})},
        "baseline_views": {"type": "array", "items": obj({
            "series_id": {"type": "string", "enum": baseline_ids or ["none"]},
            "view": {"type": "string", "enum": ["above baseline", "in line with baseline", "below baseline"]},
            "expected_low": {"type": "number"},
            "expected_high": {"type": "number"},
            "reason": {"type": "string", "description": "Why you differ from (or agree with) the baseline"},
            "cite": cite})},
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
        "evidence": {"type": "array", "description": (
            "One entry per web source per fact used. A web citation on an item only counts if an "
            "entry here quotes that page for that item."), "items": obj({
            "source": {"type": "string", "description": "web:N id"},
            "quote": {"type": "string", "description": (
                "Exact sentence or phrase copied from the page (15-400 characters) that states the "
                "fact, including its key number or date")},
            "used_for": {"type": "array", "items": {"type": "string"}, "description": (
                "Paths of the items this quote supports, e.g. headline, status[0], events[2], "
                "watch_list[1], baseline_views[3], personas[0].points[1], scenarios[2].drivers[0], "
                "scenarios[1].assumptions[0]")}})},
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
- Cover all six personas, all three scenarios, 4-10 events, 4-8 watch-list items.
- BASELINE: data:baseline holds mechanical projections with 80% bands whose width comes
  from past errors. For every baseline series give a baseline_view: whether you expect
  the outcome above, in line with, or below the baseline, your own expected_low and
  expected_high in the same unit, and the reason with citations. Depart from the baseline
  only when cited evidence supports it; "in line" is a valid answer. These calls are
  logged and scored against what actually happens.
- SCENARIOS: give each scenario 2-5 explicit assumptions about outside drivers (interest
  rates, population/immigration, policy, the wider economy) that are concrete enough to
  check later, each with a citation.
- EVIDENCE: every web citation must be backed by an evidence entry: a quote copied exactly
  from that page which states the specific fact (with its number or date), listing the item
  paths it supports. Ingest downloads each page and checks the quote is really there; a web
  citation without a matching quote is removed, and an item left with no sources is dropped.
  If no page you read states a fact, leave the fact out."""


def write(client: anthropic.Anthropic, facts: dict, research_text: str, sources: dict,
          baseline_ids: list[str]) -> dict:
    table = "\n".join(f"{sid}: {s['title']} ({s['url']})" for sid, s in sources.items())
    user = (f"Today is {dt.date.today().isoformat()}.\n\n"
            f"<source_table>\n{table}\n</source_table>\n\n"
            f"<data_digest>\n{json.dumps(facts, indent=1, default=str)}\n</data_digest>\n\n"
            f"<research_notes>\n{research_text}\n</research_notes>")
    resp = client.beta.messages.create(
        model=MODEL, max_tokens=16000, betas=[FALLBACK_BETA], fallbacks="default",
        system=WRITE_SYSTEM,
        output_config={"effort": "high",
                       "format": {"type": "json_schema", "schema": build_schema(baseline_ids)}},
        messages=[{"role": "user", "content": user}])
    check(resp)
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


# ---------------------------------------------------------------- validation

def validate(summary: dict, valid_ids: set, baseline_ids: set) -> int:
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
        s["assumptions"] = clean(s.get("assumptions", []))
    views = [v for v in summary.get("baseline_views", [])
             if v["series_id"] in baseline_ids and 0 < v["expected_low"] <= v["expected_high"]]
    dropped += len(summary.get("baseline_views", [])) - len(views)
    summary["baseline_views"] = clean(views)
    return dropped


def cited_ids(summary: dict) -> set:
    used = set(summary["headline_cite"])
    for key in ("status", "events", "watch_list", "baseline_views"):
        used |= {c for it in summary[key] for c in it["cite"]}
    for p in summary["personas"]:
        used |= {c for it in p["points"] for c in it["cite"]}
    for s in summary["scenarios"]:
        used |= {c for it in s["drivers"] + s["assumptions"] for c in it["cite"]}
    return used


def log_views(summary: dict, baseline: dict) -> int:
    """Append Claude's adjusted calls to the forecast log so they are scored like the baseline."""
    from baseline import LOG_FIELDS
    from common import read_csv, write_csv
    path = DATA_DIR / "forecast_log.csv"
    log = read_csv(path)
    keys = {(r["origin"], r["source"], r["series_id"]) for r in log}
    recs = {s["id"]: s for s in baseline["series"]}
    added = 0
    for v in summary["baseline_views"]:
        b = recs[v["series_id"]]
        key = (b["origin"], "claude", b["id"])
        if key in keys:
            continue  # one Claude call per data point, like the baseline
        lo, hi = v["expected_low"], v["expected_high"]
        log.append({"origin": b["origin"], "source": "claude", "series_id": b["id"], "target": b["target"],
                    "forecast": round((lo + hi) / 2, 1), "low": lo, "high": hi,
                    "logged_on": dt.date.today().isoformat()})
        keys.add(key)
        added += 1
    write_csv(path, log, LOG_FIELDS)
    return added


def finalize(summary: dict, sources: dict, baseline: dict, model: str) -> None:
    """Shared tail of both modes: guardrails, scoring log, write summary.json."""
    baseline_ids = {s["id"] for s in baseline["series"]}
    summary["verification"] = verify_claims(summary, sources)
    dropped = validate(summary, set(sources), baseline_ids)
    logged = log_views(summary, baseline)
    used = cited_ids(summary)
    summary.update({
        "generated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
        "model": model,
        "dropped_uncited_items": dropped,
        "sources": {sid: s for sid, s in sources.items() if sid in used},
    })
    summary.pop("web_sources", None)
    write_json(OUT, summary)
    print(f"summary: {len(summary['sources'])} sources cited, {dropped} uncited/invalid items dropped, "
          f"{logged} Claude calls logged")


# ---------------------------------------------------------------- agent mode (no API key)
# A Claude Code session (or scheduled routine) does the research and writing with its own
# tools, using the brief from --emit, then hands the draft back through --ingest, which
# applies the same guardrails as the API path. See pipeline/SUMMARY_AGENT.md.

def emit(path: str) -> None:
    facts, sources = digest()
    baseline = load_baseline() or {"series": []}
    brief = {
        "today": dt.date.today().isoformat(),
        "research_brief": RESEARCH_PROMPT.format(today=dt.date.today().isoformat()),
        "writing_rules": WRITE_SYSTEM,
        "approved_domains": load_approved(),
        "draft_format": (
            "Write one JSON object matching output_schema, plus a top-level 'web_sources' list: "
            "[{\"id\": \"web:1\", \"title\": ..., \"url\": ..., \"page_age\": \"date if known\"}]. "
            "Cite data with the data:* ids in source_table and web pages with your web:N ids. "
            "Only list pages you actually opened or saw in search results. Cite ONLY pages on "
            "approved_domains ('*.' = any subdomain); sources on other sites are rejected at ingest. "
            "Fill 'evidence' with exact quotes from each page for each item that cites it (see "
            "writing_rules EVIDENCE); unquoted web citations are removed at ingest."),
        "source_table": sources,
        "data_digest": facts,
        "output_schema": build_schema([s["id"] for s in baseline["series"]]),
    }
    write_json(Path(path), brief)
    print(f"brief written to {path}")


def check_schema(value, schema: dict, where: str = "$") -> list[str]:
    """Minimal JSON-schema check (types, enums, required, no extra keys) for agent drafts."""
    errs = []
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            return [f"{where}: expected object"]
        props = schema.get("properties", {})
        errs += [f"{where}.{k}: missing" for k in schema.get("required", []) if k not in value]
        for k, v in value.items():
            if k in props:
                errs += check_schema(v, props[k], f"{where}.{k}")
            elif schema.get("additionalProperties") is False and not (where == "$" and k == "web_sources"):
                errs.append(f"{where}.{k}: unexpected key")
    elif t == "array":
        if not isinstance(value, list):
            return [f"{where}: expected array"]
        for i, item in enumerate(value):
            errs += check_schema(item, schema.get("items", {}), f"{where}[{i}]")
    elif t == "string":
        if not isinstance(value, str):
            errs.append(f"{where}: expected string")
        elif "enum" in schema and value not in schema["enum"]:
            errs.append(f"{where}: {value!r} not in {schema['enum']}")
    elif t == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        errs.append(f"{where}: expected number")
    return errs


_PAGES: dict[str, tuple[bool, str | None]] = {}


def page_text(raw: bytes, content_type: str) -> str:
    """Plain text of an HTML page or PDF, for quote matching."""
    if raw[:4] == b"%PDF" or "pdf" in content_type:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return " ".join((pg.extract_text() or "") for pg in pdf.pages[:60])
    text = raw.decode("utf-8", errors="replace")
    text = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", text)
    return re.sub(r"<[^>]+>", " ", text)


def fetch_page(url: str) -> tuple[bool, str | None]:
    """(exists, text). Text is None when the site exists but refuses bots (can't verify quotes)."""
    if url in _PAGES:
        return _PAGES[url]
    result: tuple[bool, str | None] = (False, None)
    if url.startswith("https://"):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (vmc-growth-tracker source check)"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                if resp.status < 400:
                    result = (True, page_text(resp.read(8_000_000), resp.headers.get("Content-Type", "")))
        except urllib.error.HTTPError as e:
            result = (e.code in (401, 403, 429), None)  # exists but blocks bots
        except Exception:  # noqa: BLE001 - DNS failure, timeout, bad URL, unreadable PDF
            result = (False, None)
    _PAGES[url] = result
    return result


def url_ok(url: str) -> bool:
    """The page must exist: https and a non-error response."""
    return fetch_page(url)[0]


def norm(text: str) -> str:
    """Normalise for quote matching: entities, quotes, dashes, spaces, case."""
    text = html.unescape(text)
    for a, b in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'),
                 ("\u2013", "-"), ("\u2014", "-"), ("\u2212", "-"), ("\xa0", " "), ("\u00ad", "")):
        text = text.replace(a, b)
    return re.sub(r"\s+", " ", text).strip().lower()


def citable_items(summary: dict):
    """(path, item, cite_key) for every item that carries citations."""
    yield "headline", summary, "headline_cite"
    for key in ("status", "events", "watch_list", "baseline_views"):
        for i, it in enumerate(summary.get(key, [])):
            yield f"{key}[{i}]", it, "cite"
    for i, p in enumerate(summary.get("personas", [])):
        for j, it in enumerate(p.get("points", [])):
            yield f"personas[{i}].points[{j}]", it, "cite"
    for i, sc in enumerate(summary.get("scenarios", [])):
        for part in ("drivers", "assumptions"):
            for j, it in enumerate(sc.get(part, [])):
                yield f"scenarios[{i}].{part}[{j}]", it, "cite"


def verify_claims(summary: dict, sources: dict) -> dict:
    """Keep a web citation on an item only if an evidence quote for that item is on the page.

    Data citations (data:*) are untouched. Runs before validate(), which then drops items
    left without any source.
    """
    verified: dict[str, set] = {}   # path -> web ids whose quote was found on the page
    kept_evidence, bad_quotes = [], []
    for ev in summary.get("evidence", []):
        sid, quote = ev.get("source", ""), norm(ev.get("quote", ""))
        src = sources.get(sid)
        if not src or not 15 <= len(quote) <= 400:
            bad_quotes.append((sid, "missing source or bad length"))
            continue
        exists, text = fetch_page(src["url"])
        if not text or quote not in norm(text):
            bad_quotes.append((sid, "quote not found on page" if text else "page unreadable"))
            continue
        kept_evidence.append(ev)
        for path in ev.get("used_for", []):
            verified.setdefault(path, set()).add(sid)
    checked = removed = 0
    for path, item, key in citable_items(summary):
        keep = []
        for c in item.get(key, []):
            if not c.startswith("web:"):
                keep.append(c)
                continue
            checked += 1
            if c in verified.get(path, set()):
                keep.append(c)
            else:
                removed += 1
        item[key] = keep
    summary["evidence"] = kept_evidence
    if bad_quotes:
        print(f"  {len(bad_quotes)} evidence quote(s) rejected: {bad_quotes[:12]}")
    print(f"  claim check: {checked - removed} of {checked} web citations verified against their pages")
    return {"web_citations_checked": checked, "verified": checked - removed, "removed": removed}


def ingest(path: str, model: str) -> None:
    draft = json.loads(Path(path).read_text(encoding="utf-8"))
    baseline = load_baseline() or {"series": []}
    errs = check_schema(draft, build_schema([s["id"] for s in baseline["series"]]))
    if errs:
        raise SystemExit("Draft does not match the schema; summary.json unchanged:\n  " + "\n  ".join(errs[:30]))
    _, sources = digest()
    approved = load_approved()
    bad, rejected = [], []
    for w in draft.get("web_sources", []):
        if not str(w.get("id", "")).startswith("web:"):
            continue
        if not is_approved(w.get("url", ""), approved):
            rejected.append(w.get("url"))
            continue
        if url_ok(w.get("url", "")):
            sources[w["id"]] = {"kind": "web", "title": w.get("title") or w["url"], "url": w["url"],
                                "page_age": w.get("page_age")}
        else:
            bad.append(w.get("url"))
    if bad:
        print(f"  {len(bad)} web source(s) failed the link check and were removed: {bad}")
    if rejected:
        print(f"  {len(rejected)} web source(s) are not on pipeline/approved_sources.txt and were rejected: {rejected}")
    total = len([w for w in draft.get("web_sources", [])
                 if str(w.get("id", "")).startswith("web:") and is_approved(w.get("url", ""), approved)])
    if total and len(bad) * 2 > total and "--allow-missing-sources" not in sys.argv:
        # Most links failing usually means this machine can't reach the web (e.g. a sandbox
        # network allowlist), not that the sources are bad. Publishing would strip the page
        # of its news, so keep last week's summary instead.
        raise SystemExit(f"{len(bad)} of {total} web sources unreachable; summary.json unchanged. "
                         "Check network access, or pass --allow-missing-sources to publish anyway.")
    finalize(draft, sources, baseline, model)


def main() -> None:
    if "--emit" in sys.argv:
        return emit(sys.argv[sys.argv.index("--emit") + 1])
    if "--ingest" in sys.argv:
        model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "Claude (Claude Code)"
        return ingest(sys.argv[sys.argv.index("--ingest") + 1], model)

    force = "--force" in sys.argv
    if OUT.exists() and not force:
        prev = json.loads(OUT.read_text(encoding="utf-8"))
        age = dt.date.today() - dt.date.fromisoformat((prev.get("generated") or "2000-01-01")[:10])
        if age.days < 6:
            print(f"summary: generated {age.days} days ago, skipping (use --force)")
            return

    import anthropic  # only the API path needs the SDK

    client = anthropic.Anthropic()
    facts, sources = digest()
    research_text, found = research(client)
    approved = load_approved()
    found = {u: m for u, m in found.items() if is_approved(u, approved)}
    for i, (url, meta) in enumerate(found.items(), 1):
        sources[f"web:{i}"] = {"kind": "web", "title": meta["title"] or url, "url": url,
                               "page_age": meta.get("page_age")}
    baseline = load_baseline() or {"series": []}
    summary = write(client, facts, research_text, sources, [s["id"] for s in baseline["series"]])
    finalize(summary, sources, baseline, MODEL)


if __name__ == "__main__":
    main()
