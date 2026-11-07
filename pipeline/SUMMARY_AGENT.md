# Weekly summary runbook (Claude Code, no API key)

Run this after the Monday data refresh (GitHub Actions, 11:00 UTC). It writes the
"What it means for you" page using your Claude plan instead of a paid API key.
The script applies the same guardrails as the API path.

## Steps

1. Get the latest data:
   ```sh
   git pull
   pip install -r requirements.txt
   ```
2. Write the brief (data digest, baseline projections, writing rules, output schema):
   ```sh
   python pipeline/generate_summary.py --emit /tmp/brief.json
   ```
3. Read the brief. Do the research in `research_brief` with web search, using ONLY sites
   on `approved_domains` (from `pipeline/approved_sources.txt`; `*.` means any subdomain).
   Sources on any other site are rejected at ingest. Note each page's URL and date.
4. Write `/tmp/draft.json`: one object matching `output_schema`, plus
   `web_sources: [{"id": "web:1", "title", "url", "page_age"}]`.
   - Follow `writing_rules` exactly (plain language, cite everything, no advice).
   - Every number must come from `data_digest` or a listed web source.
   - Give a `baseline_views` entry for every baseline series, and 2-5 cited
     `assumptions` per scenario.
5. Ingest. This checks the schema, opens every web URL, drops claims whose sources
   fail, logs your projections for scoring, and writes `src/data/summary.json`:
   ```sh
   python pipeline/generate_summary.py --ingest /tmp/draft.json --model "Claude (Claude Code)"
   ```
   If it reports schema errors, fix the draft and ingest again.
   If it stops because most web sources are unreachable, the machine's network is
   blocked: stop without pushing and report which domains failed.
6. Commit and push (the deploy workflow builds and publishes the site):
   ```sh
   git add src/data/summary.json src/data/forecast_log.csv
   git commit -m "summary: weekly plain-language update $(date -u +%Y-%m-%d)"
   git push
   ```
   The push triggers the deploy workflow.

## Rules

- Never copy text from paywalled or copyrighted sources beyond short facts with a link.
- If a week has no meaningful news, keep events from earlier weeks that still matter
  (re-cite them) rather than inventing new ones.
- Do not edit `baseline.json` or past rows of `forecast_log.csv`. Scores must stay honest.
