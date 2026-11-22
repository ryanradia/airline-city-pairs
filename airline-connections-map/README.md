# Air travel connections among the top 100 U.S. city markets

Interactive map and matrix of domestic air journeys between the 100 busiest U.S. city markets,
July 2025–June 2026. Built from the results of the airline-city-pairs project (BTS DB1C Market,
40% ticket sample × 2.5). `index.html` is served by GitHub Pages.

## What the page does
- **Map:** a circle at each market, sized by total journeys. Rest the pointer on a market (or tap
  it) to resize and recolor the circles by journeys with that market. Curved, tapered lines go to
  its top 10, top 25, or all 99 connections, and the panel lists all 99. Click to keep a market
  selected; the map zooms out only if some of its lines are off screen.
- **Matrix view:** the full 100 × 100 grid of journeys, grouped by Census region or ordered by rank.
  Clicking a cell shows that pair on the map.
- **Links:** `?m=Denver` opens with a market selected; `?view=matrix` opens the matrix.
- **Phones:** the panel is a bottom sheet.
- **Methodology:** the "Methodology & sources" pop-up is in `index.html`.

## Files
| Path | Contents |
| --- | --- |
| `index.html` | The page (hand-written) |
| `markets.json` | Market shapes, airports, CBSAs, regions, and the journey matrix (generated) |
| `scripts/build_map.py` | Rebuilds `markets.json` from `airline-city-pairs/results` (read only) and Census boundaries |
| `scripts/map_market_names.csv` | Display names for the 100 markets |
| `scripts/airport_coords.csv` | Airport locations (NTAD Aviation Facilities; FAA reference points for PBI and AZA) |

## Rebuild and preview
```
pip install pandas geopandas
python scripts/build_map.py ../airline-city-pairs/results
python -m http.server 8000      # then open http://localhost:8000/
```
Census CBSA and county files download to `.cache/` on the first run (not committed). Opening
`index.html` directly from disk will not load the data; browsers block that, so use a local server.

## Geography in brief
Each market is drawn as the 2025 Census CBSAs containing its airports, the same boundaries as the
housing-cost map. CBSAs shared by two markets are split by county: Miami (Palm Beach → West Palm
Beach), Orlando (Seminole → Sanford), and Riverside–San Bernardino (San Bernardino → Los Angeles;
Riverside → Palm Springs). Details are in the docstring of `scripts/build_map.py` and in the page's
Methodology pop-up.
