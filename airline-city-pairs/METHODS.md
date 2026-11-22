# Methods

## Data and period
- Source: BTS DB1C Market, one ZIP per reporting month, July 2025 through June 2026. Each ZIP holds
  three copies of the same month (`.asc.zip`, `.csv.zip`, `.parquet`). Only the parquet is read. The
  other two are logged in `results/input_alternate_formats_not_read_*.csv` so they cannot be double
  counted.
- Coverage comes from `RpYear`/`RpMonth` inside each file, not from filenames. Months outside
  2025-07…2026-06 are excluded and logged. A month that appears twice is used once, and the second
  copy is logged as a duplicate. The scheduled-flight date fields (`SchFl*`) are not used. Results are
  traffic *reported* for the selected months.
- If any of the 12 months is missing, the script still runs, but every output is labelled
  `PREVIEW_<first>_to_<last>` and the page shows a warning. Nothing is annualized.
- Checks: one schema across all 12 files (column names are normalized case-insensitively); `MktID` is
  unique within every month; `ItinID` begins with the reporting YYYYMM on every row. `ItinID` is 15
  digits through February 2026 and 14 from March 2026, so the check compares the first six
  characters. The 2026 ZIPs are larger than the 2025 ones, but the schema is identical and record
  counts are comparable.
- Monthly totals follow normal seasonality: 40.1M estimated journeys in January 2026 and 57.8M in
  July 2025. The connecting share stays between 23% and 26% in every month, with no break between
  the 2025 and 2026 files.

## Passengers and expansion
- `Passengers` equals 1.0 on every record in every file. These are unexpanded sample records.
  Estimated passengers = `Passengers × 2.5` (40% sample). Records are summed by month and then across
  months, with no further annualization. Full precision is kept; rounding happens only for display.
- Fare fields are not used to filter anything. No records are deduplicated: identical-looking rows
  are separate observations, and `MktID` uniqueness confirms there are no duplicate records.

## Domestic scope
- DB1C Market is the domestic product. Geography codes 1 (non-contiguous: Alaska, Hawaii,
  territories) and 2 (contiguous) are both kept. No other code appears, and every endpoint country is
  US. The filter remains in place and is reported in the diagnostics.
- Coverage is domestic market journeys reported in DB1C. It does not count domestic segments flown on
  international tickets.

## City markets
- The crosswalk (`results/airport_crosswalk_*.csv`) starts from BTS `OriginCityMarketID` /
  `DestCityMarketID`. Each airport has exactly one city-market ID in the data.
- Airport groups in the table note: New York City (JFK, EWR, LGA, HPN, ISP, SWF); Los Angeles (LAX,
  SNA, BUR, ONT, LGB); Chicago (ORD, MDW); Washington - Baltimore (BWI, DCA, IAD); Dallas (DFW, DAL);
  Houston (IAH, HOU); Greater Boston (BOS, PVD, MHT); San Francisco Bay Area (SFO, OAK, SJC); Phoenix
  (PHX, AZA); Miami - Fort Lauderdale (MIA, FLL); Tampa Bay (TPA, PIE, LAL); Cleveland - Akron/Canton
  (CLE, CAK); Norfolk - Newport News (ORF, PHF); Columbus (CMH, LCK).
- Every group matches its current BTS city market. West Palm Beach (PBI, market 34027) is already
  separate from Miami–Fort Lauderdale (32467), so no overrides were needed. The override logic stays
  in the code (`FORCE_SEPARATE`, and reassignment of listed airports to their group) in case BTS
  definitions change.
- BTS markets include two tiny airports the note does not list, kept per the BTS definition and
  flagged in the crosswalk: SCF (Scottsdale) in Phoenix and HHR (Hawthorne) in Los Angeles. Each has
  well under 1,000 sampled passengers per month.
- Other multi-airport BTS markets in the top 100 also follow BTS: Denver (incl. APA), Seattle (incl.
  BFI, KEH, LKE), Las Vegas (incl. HSH), and San Juan (incl. SIG).
- Decision: BTS city markets are used throughout, with no metro-area (MSA) adjustments. So, for example,
  Orlando Sanford (SFB), Punta Gorda (PGD), Provo (PVU), and Paine Field (PAE) remain separate markets
  rather than being merged into Orlando, Fort Myers, Salt Lake City, and Seattle.
- Display names for markets outside the airport-group note come from `scripts/market_names.csv`. Any
  market missing from that file falls back to its airport codes, and the validation file lists such
  markets.

## Pairs
- Each Market record is one O&D journey within BTS market boundaries. A New York–Atlanta–Orlando
  connection belongs to New York–Orlando only. Endpoints are mapped to city markets, and the pair key
  is (min key, max key), so both directions combine. There is no division by two and no
  multiplication by coupons.
- Records whose two endpoints fall in the same city market (e.g., a JFK–EWR market record) are
  excluded and reported: 610,316 sample records, or 1,525,790 estimated.
- Records whose endpoint has no BTS airport or city-market ID are excluded as invalid endpoints:
  1,429 sample records, or 3,572.5 estimated. The codes are EKW, FBT, TRP, WPT, and ZYP. ZYP is New
  York Penn Station, a rail code-share point; the others are unidentified non-airport codes.
- Retained: 244,484,392 sample records = 611,210,980 estimated journeys.
- The top 100 are chosen after aggregating all months and airport pairs. Sort order: unrounded total
  descending, then pair key.
- Display order: "City market 1" is the endpoint with more total retained O&D traffic across all pairs.

## Connecting vs. "nonstop"
- Connecting = `MktCoupons ≥ 2`. Single-coupon ("Nonstop O&D traffic*") = `MktCoupons = 1`. Percent
  connecting is computed from pooled expanded counts.
- Caveat: one coupon can be a through flight with an intermediate stop. The DB1C `Nonstop` flag shows
  this affects 0.26–0.44% of single-coupon passengers per month (`single_coupon_with_stop_est` in the
  diagnostics, and `single_coupon_with_intermediate_stop` per pair). The primary definition stays
  coupon-based to match the reconstructed 2023 rule. The exact original code is unavailable, so this
  rule is a reconstruction assumption.
- Records with missing or <1 coupon counts would be excluded as "unclassifiable" and reported. None
  occur.

## Published table and images
- Columns: City market 1, City market 2, 12-month journeys (both ways), average daily journeys each way
  (12-month journeys ÷ 365 ÷ 2; July 1, 2025–June 30, 2026 has 365 days), and % with stops (= percent
  connecting, `MktCoupons ≥ 2`).
- `index.html` and `social/*.png` take their wording, columns, and rows from the same code
  (`scripts/build_page.py`), so they always match.

## Display rounding
- Total and connecting are rounded half-up to whole passengers. The displayed single-coupon value is
  total − connecting, so the columns always add up. The validation file counts rows where this differs
  by 1 from independently rounding the single-coupon value. Percentages show one decimal.

## Limits
- These are survey estimates from a 40% ticket sample, not census counts. They count journeys, not
  people.
- The 2023 table used an earlier survey (the 10% DB1B) with different processing and reporting
  windows. Differences from it are not pure changes in travel demand.
