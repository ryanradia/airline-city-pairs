# Top 100 U.S. domestic airline city-market pairs, July 2025–June 2026

The 100 busiest U.S. domestic city-market pairs, ranked by passenger origin–destination journeys with
both directions combined. Connecting traffic is included. Nearby airports are grouped into city
markets. Based on Bureau of Transportation Statistics DB1C Market survey (40% ticket sample)
for reporting months July 2025–June 2026.

**Interactive table:** `index.html`, served by GitHub Pages.
- Desktop version is a searchable table, sortable by any column, and scrolling with a sticky header.
- On phones (600px wide or less) each pair is a compact card, with a search box and "Sort" menu.
- "Methodology & sources" pop-up summarizes the methods. Keep in sync with `METHODS.md` when method
  changes (pop-up text is in `scripts/page_template.html`).

## Top 10

| Rank | City market 1 | City market 2 | Journeys, both ways | % with stops |
| ---: | --- | --- | ---: | ---: |
| 1 | New York City | Miami - Fort Lauderdale | 7,101,200 | 1.6% |
| 2 | Los Angeles | San Francisco Bay Area | 6,833,538 | 0.3% |
| 3 | New York City | Orlando | 5,219,760 | 2.3% |
| 4 | New York City | Los Angeles | 4,928,735 | 10.2% |
| 5 | New York City | Chicago | 4,230,520 | 1.0% |
| 6 | New York City | Atlanta | 3,721,593 | 1.2% |
| 7 | New York City | San Francisco Bay Area | 3,348,010 | 8.8% |
| 8 | Los Angeles | Las Vegas | 3,203,550 | 0.3% |
| 9 | New York City | West Palm Beach | 2,816,398 | 1.1% |
| 10 | Los Angeles | Seattle | 2,801,880 | 4.8% |

Full list: [`results/top100_display_2025-07_to_2026-06.csv`](results/top100_display_2025-07_to_2026-06.csv).
Every eligible pair: [`results/all_city_pairs_2025-07_to_2026-06.csv`](results/all_city_pairs_2025-07_to_2026-06.csv).

## Definitions in brief
- One DB1C Market record is one O&D journey. One round trip normally counts once each way, and a
  connection (New York–Atlanta–Orlando) counts only in its end-to-end market.
- Estimates. Each sampled record multiplied by 2.5, summed over 12 reporting months.
- "Nonstop" means single-coupon markets, which includes a small share (≈0.3–0.4%) of through flights
  with an intermediate stop. Connecting (shown as "% with stops") means two or more coupons.
- City markets follow BTS city-market IDs. The groupings that matter most are listed in the table note
  (e.g., New York City = JFK, EWR, LGA, HPN, ISP, SWF). West Palm Beach is kept separate from
  Miami–Fort Lauderdale.

Full details and data-quality notes: [METHODS.md](METHODS.md).

## Repository layout

| Path | Contents |
| --- | --- |
| `index.html` | The interactive table (generated; do not edit by hand) |
| `scripts/run_all.py` | Full pipeline: raw BTS ZIPs → `results/` (including per-airport traffic) → `index.html` |
| `scripts/airport_traffic.py` | Per-airport retained passengers → `results/airport_traffic_*.csv` (called by `run_all.py`; the airport-group note lists only airports with traffic) |
| `scripts/build_page.py` | Rebuilds `index.html` from `results/` only |
| `scripts/page_template.html` | Page layout and styling |
| `scripts/market_names.csv` | Display names for BTS city markets |
| `social/` | Four 1800×2600 PNGs for social media, ranks 1–25, 26–50, 51–75, 76–100, with 12-month journeys and average daily journeys each way (12-month ÷ 365 ÷ 2) |
| `scripts/build_social.py` | Rebuilds the `social/` PNGs from `results/` (needs Edge or Chrome) |
| `results/` | Top 100 (analytical/unrounded, display-formatted, and the rounded table that feeds the page), all pairs, airport crosswalk, monthly diagnostics, input manifest with checksums, validation checks |
| `data/` | Where the raw BTS ZIPs go locally (not committed) |

## Reproduce

```
pip install -r requirements.txt
python scripts/run_all.py --data-dir data --output-dir results
python scripts/build_social.py
```

Download 12 monthly DB1C Market ZIPs into `data/` first (see `data/README.md`). `run_all.py` writes
every file in `results/` (including `airport_traffic_*.csv`) and `index.html`. `build_social.py`
renders the four PNGs in seconds; it needs Edge or Chrome.

To change only the wording or look, edit `scripts/build_page.py` (shared text) or
`scripts/page_template.html`, then run `python scripts/build_page.py` and `python scripts/build_social.py`.
Both take seconds and need no raw data.

## Source and credit
Author’s calculations from Bureau of Transportation Statistics, DB1C Market, July 2025–June 2026; 40%
sample expanded by 2.5. Table by @ryanradia. Updates the 2023 version: https://www.datawrapper.de/_/MLoFa/
