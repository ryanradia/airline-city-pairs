# Where America flies

Interactive map and heatmap of domestic air journeys between the 100 busiest U.S. city markets,
July 2025–June 2026. Built from the results of the airline-city-pairs project (BTS DB1C Market,
40% ticket sample × 2.5). It's a static site: upload the folder's contents to GitHub Pages as-is.
Every library and map file is bundled, so the page loads nothing from other servers.

## What the page does
- **Map tab:** a circle at each market, sized by total journeys, with the 25 busiest pairs as gray
  lines. Resting the pointer on a market (or tapping it on a phone) resizes and recolors the circles
  by journeys with that market. Curved, tapered orange lines go to its top 10, top 25, or all 99
  connections. The sidebar lists every connection with journeys, share of the market's total, and %
  with stops. State and territory lines come from U.S. Atlas.
- **Heatmap tab:** the full 100 × 100 grid, ordered by region or rank. Hover, click, or use the
  arrow keys to inspect a pair; "Show on map" opens it on the map.
- **Search:** by market name or airport code (e.g., DCA → Washington - Baltimore).
- **Links:** `?m=Denver` opens with a market selected; `?view=matrix` opens the heatmap.
- **Phones:** a slim bottom bar (search + Explore). Selecting a city opens a scrollable results
  sheet that shows the top 10 destinations first, with a button for all 99.

## Files
| Path | Contents |
| --- | --- |
| `index.html` | The page (hand-written) |
| `markets.json` | Market shapes, airports, CBSAs, regions, and the journey matrix (generated) |
| `geo/` | U.S. Atlas 3.0.1 `states-10m.json` and World Atlas 2.0.2 `countries-50m.json`, with licenses |
| `vendor/` | MapLibre GL JS 4.7.1 and topojson-client 3.1.0, with licenses |
| `fonts/NotoSansBold/` | Label glyphs (Noto Sans, SIL Open Font License) |
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
`index.html` directly from disk won't load the data, because browsers block it; use a local server.
