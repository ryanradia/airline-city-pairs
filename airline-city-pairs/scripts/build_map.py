"""Build the connections map's data file, map/markets.json, from results/ (no raw BTS data needed).

Usage (from the repo root): python scripts/build_map.py

- The 100 busiest city markets are ranked by total O&D journeys: the sum of every pair the market is in
  (results/all_city_pairs_*.csv, both directions, connecting traffic included).
- Each market is drawn with the Census 2025 cartographic CBSA (metro/micro area) boundaries that contain
  its airports, the same CBSA file the housing-cost map uses. Airports carrying under 0.25% of a market's
  journeys are ignored. Where two markets have airports in the same CBSA (e.g. PBI in the Miami CBSA),
  that CBSA is split by county: each county with an airport goes to that airport's market and the rest go
  to the market with the most traffic in the CBSA. An airport outside every CBSA gets its own county.
- The matrix holds every pair among the 100 markets with at least one sampled journey (pairs that are
  absent have none and show as 0).
Census boundary files are downloaded into .cache/ on first run.
"""
import json, pathlib, urllib.request, zipfile
import numpy as np, pandas as pd, geopandas as gpd

ROOT = pathlib.Path(__file__).resolve().parent.parent
RES, CACHE, OUT = ROOT / 'results', ROOT / '.cache', ROOT / 'map'
TAG = json.loads((RES / 'run_info.json').read_text())['tag']
N_TOP = 100
MIN_AIRPORT_SHARE = 0.0025
TOLERANCE = 0.002   # degrees, display simplification
CENSUS = {
    'cbsa': 'https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_cbsa_500k.zip',
    'county': 'https://www2.census.gov/geo/tiger/GENZ2025/shp/cb_2025_us_county_500k.zip',
}


def census(name):
    d = CACHE / name
    if not d.exists():
        d.mkdir(parents=True)
        z = d / 'src.zip'
        urllib.request.urlretrieve(CENSUS[name], z)
        zipfile.ZipFile(z).extractall(d)
    return gpd.read_file(next(d.glob('*.shp'))).to_crs(4326)


# ---- market totals and the top 100
pairs = pd.read_csv(RES / f'all_city_pairs_{TAG}.csv')
ends = pd.concat([pairs[['market1_key', 'total_traffic']].set_axis(['k', 't'], axis=1),
                  pairs[['market2_key', 'total_traffic']].set_axis(['k', 't'], axis=1)])
total = ends.groupby('k').t.sum().sort_values(ascending=False)
top = total.head(N_TOP)
keys = list(top.index)
names = pd.read_csv(ROOT / 'scripts' / 'map_market_names.csv').set_index('analysis_key').map_name
missing = set(keys) - set(names.index)
assert not missing, f'add names to scripts/map_market_names.csv for {missing}'

# ---- airports of each market
at = pd.read_csv(RES / f'airport_traffic_{TAG}.csv')
at = at[at.analysis_key.isin(keys) & (at.est_pax > 0)].copy()
at['share'] = at.est_pax / at.groupby('analysis_key').est_pax.transform('sum')
at = at[at.share >= MIN_AIRPORT_SHARE]
xy = pd.read_csv(ROOT / 'scripts' / 'airport_coords.csv').set_index('Code')
assert at.Code.isin(xy.index).all(), f'no coordinates for {set(at.Code) - set(xy.index)}'
at = gpd.GeoDataFrame(at, geometry=gpd.points_from_xy(at.Code.map(xy.lng), at.Code.map(xy.lat)), crs=4326)

# ---- counties, the CBSA each belongs to, and the county each airport is in
cb = census('cbsa')[['GEOID', 'NAME', 'geometry']].rename(columns={'GEOID': 'cbsa', 'NAME': 'cbsa_name'})
co = census('county')[['GEOID', 'NAMELSAD', 'STUSPS', 'geometry']].rename(columns={'GEOID': 'county'})
rp = gpd.GeoDataFrame(co[['county']], geometry=co.representative_point(), crs=4326)
co = co.merge(gpd.sjoin(rp, cb, predicate='within')[['county', 'cbsa', 'cbsa_name']], on='county', how='left')
at = gpd.sjoin(at, co[['county', 'cbsa', 'cbsa_name', 'geometry']], predicate='within', how='left')
assert at.county.notna().all(), at[at.county.isna()].Code.tolist()
at['unit'] = at.cbsa.fillna('county:' + at.county)   # the area the airport pulls in

# ---- assign counties to markets
assign = {}   # county -> market
for unit, g in at.groupby('unit'):
    if unit.startswith('county:'):
        counties = [unit[7:]]
    else:
        counties = co.loc[co.cbsa == unit, 'county'].tolist()
    by_mkt = g.groupby('analysis_key').est_pax.sum().sort_values(ascending=False)
    if len(by_mkt) == 1:
        assign.update({c: by_mkt.index[0] for c in counties})
        continue
    # contested CBSA: county with an airport -> busiest such airport's market; others -> busiest market
    own = g.sort_values('est_pax').groupby('county').analysis_key.last()
    print(f'split {g.cbsa_name.iloc[0]}: ' + ', '.join(f'{m} ({names[m]}) {", ".join(g[g.analysis_key == m].Code)}'
                                                         for m in by_mkt.index))
    assign.update({c: own.get(c, by_mkt.index[0]) for c in counties})
co['k'] = co.county.map(assign)
shapes = co[co.k.notna()].dissolve('k')
shapes['geometry'] = shapes.geometry.simplify(TOLERANCE, preserve_topology=True).make_valid()
assert set(shapes.index) == set(keys), set(keys) - set(shapes.index)

# areas listed in the popup: CBSA names, plus county names where a CBSA is split or there is no CBSA
areas = {}
for k, g in co[co.k.notna()].groupby('k'):
    out = []
    for cbsa, h in g.groupby(g.cbsa.fillna('')):
        if not cbsa:
            out += [f'{r.NAMELSAD}, {r.STUSPS}' for r in h.itertuples()]
        elif len(h) == (co.cbsa == cbsa).sum():
            out.append(h.cbsa_name.iloc[0] + ' CBSA')
        else:
            out.append(h.cbsa_name.iloc[0] + ' CBSA (' + '; '.join(h.NAMELSAD) + ' only)')
    areas[k] = out

# arc endpoint: the market's airports weighted by traffic (all airports kept above)
w = at.groupby('analysis_key').apply(lambda g: pd.Series({
    'lng': np.average(g.geometry.x, weights=g.est_pax), 'lat': np.average(g.geometry.y, weights=g.est_pax)}),
    include_groups=False)

# ---- the 100 x 100 matrix
m = pairs[pairs.market1_key.isin(keys) & pairs.market2_key.isin(keys)]
idx = {k: i for i, k in enumerate(keys)}
matrix = [[i1, i2, int(round(t)), round(c / t, 4)] for i1, i2, t, c in
          zip(m.market1_key.map(idx), m.market2_key.map(idx), m.total_traffic, m.connecting_traffic)]
print(f'{N_TOP * (N_TOP - 1) // 2 - len(matrix)} of {N_TOP * (N_TOP - 1) // 2} pairs have no sampled journeys (shown as 0)')


def ring(r):
    q = np.round(np.asarray(r)[:, :2] * 1e4).astype(np.int64)   # 1e-4 degree integers, delta-encoded
    q[1:] = np.diff(q, axis=0)
    return q.ravel().tolist()


def polygons(geo):
    if geo.geom_type == 'Polygon':
        return [geo]
    return [p for g in getattr(geo, 'geoms', []) for p in polygons(g)]


markets = []
for i, k in enumerate(keys):
    a = at[at.analysis_key == k].sort_values('est_pax', ascending=False)
    markets.append({
        'k': k, 'name': names[k], 'rank': i + 1, 'total': int(round(top[k])),
        'airports': a.Code.tolist(), 'areas': areas[k],
        'lng': round(w.loc[k, 'lng'], 4), 'lat': round(w.loc[k, 'lat'], 4),
        'g': [[ring(p.exterior.coords)] + [ring(r.coords) for r in p.interiors] for p in polygons(shapes.geometry[k])],
    })
OUT.mkdir(exist_ok=True)
data = {'period': TAG, 'all_total': int(round(pairs.total_traffic.sum())), 'markets': markets, 'pairs': matrix}
(OUT / 'markets.json').write_text(json.dumps(data, separators=(',', ':')), encoding='utf-8')
print(f'map/markets.json {(OUT / "markets.json").stat().st_size / 1e6:.2f} MB; {len(markets)} markets, {len(matrix)} pairs; '
      f'top-100 pairs carry {m.total_traffic.sum() / pairs.total_traffic.sum():.1%} of all journeys')
