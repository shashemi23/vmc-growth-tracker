# About the data

## Sources

| Dataset | Source | Geography | Refresh |
|---|---|---|---|
| Development applications | [York Region Open Data: Development Application Status](https://ww8.yorkmaps.ca/arcgis/rest/services/OpenData/DevelopmentApplicationStatusAndTeams/MapServer/0) | VMC Regional Centre and VMC subway MTSA | Weekly snapshot |
| Starts, completions, under construction | [CMHC Housing Market Information Portal](https://www03.cmhc-schl.gc.ca/hmip-pimh/) | City of Vaughan (CSD 3519028), monthly from 1990 | Weekly check (CMHC publishes monthly) |
| Starts and completions by census tract | CMHC HMIP, Toronto CMA by census tract | Tract 0411.08 (2021 census), annual from 2011. CMHC archived tract-level completions after 2022; starts continue. | Weekly check |
| Resale sales, prices, listings, benchmark prices | [TRREB Market Watch](https://trreb.ca/market-data/market-watch/) monthly PDFs | City of Vaughan, monthly from 2015 | Weekly check (TRREB publishes early each month) |
| Policy rate, posted 5-year mortgage rate | [Bank of Canada Valet API](https://www.bankofcanada.ca/valet/docs) | Canada | Weekly |
| Plain-language summary | Written by Claude from the data above plus web search | VMC | Weekly |
| Average rent and vacancy rate | CMHC Rental Market Survey | Richmond Hill/Vaughan/King survey zone vs Toronto CMA, from 2010 (Vaughan-only values are mostly suppressed) | Annual (October survey) |

## Method and caveats

- **VMC boundary.** An application counts as VMC if York Region tags it with the *Vaughan Metropolitan Centre* Regional Centre or the *Vaughan Metropolitan Centre Subway* MTSA.
- **Active files only.** The York Region feed drops files once they close. The pipeline keeps a registry (`devapps_registry.csv`) of every file it has seen, so closures show up as `active = False`.
- **Unit estimates.** Unit and storey counts are parsed from free-text descriptions. Treat them as approximate.
- **Census tract vs VMC.** CMHC does not publish VMC-specific figures. Tract 0411.08 contains the VMC plus parts of the Concord employment area.
- **CMHC endpoint.** The HMIP CSV export is not an official API. The [`cmhc` R package](https://github.com/mountainMath/cmhc) uses the same endpoint. If the export changes, the weekly job fails visibly rather than writing bad data.
- **Resale data.** TRREB figures are Vaughan-wide and come from parsing TRREB's public PDF reports. They are reproduced with attribution; TRREB is not affiliated with this site. Some months' PDFs can't be parsed reliably and are skipped.
- **AI-written summary.** The "What it means for you" page is generated weekly by Claude. Every statement must cite a source from this site's data or a web page Claude retrieved; statements citing anything else are removed automatically before publishing. It can still misread a source, so follow the citations for anything important. It is educational, not financial advice.

## Raw data

All data files are in the [GitHub repo](https://github.com/shashemi23/vmc-growth-tracker/tree/main/src/data) as CSV/GeoJSON, with full history in the git log.
