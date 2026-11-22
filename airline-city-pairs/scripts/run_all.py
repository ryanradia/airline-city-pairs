"""Top 100 U.S. domestic airline city-market pairs from BTS DB1C Market, July 2025-June 2026.

Usage (from the repo root):
    python scripts/run_all.py --data-dir data --output-dir results

Reads the parquet member of each monthly DB1C.MARKET ZIP (or loose .parquet files), aggregates one month
at a time with pyarrow, writes the results CSVs and diagnostics, then rebuilds index.html.
If any of the 12 months is missing, every output is labelled as a PREVIEW of the months present.
"""
import argparse, hashlib, json, shutil, sys, zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

import airport_traffic
import build_page

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PERIOD = [(2025, m) for m in range(7, 13)] + [(2026, m) for m in range(1, 7)]
FACTOR = 2.5  # DB1C is a 40% sample of unexpanded records: 1 / 0.40
DOMESTIC_GEO = {1, 2}  # DB1C: 1 = non-contiguous domestic (AK/HI/territories), 2 = contiguous domestic
REF_GROUPS = build_page.REF_GROUPS
FORCE_SEPARATE = {"PBI": "Reference table keeps West Palm Beach separate from Miami - Fort Lauderdale"}
MONTH_NAMES = "January February March April May June July August September October November December".split()

KEYS = ["RpYear", "RpMonth", "OriginAirportID", "OriginCityMarketID", "DestAirportID", "DestCityMarketID",
        "MktCoupons", "MktGeoType", "ItinGeoType", "OriginCountry", "DestCountry", "Nonstop", "Passengers"]
APT = ["AirportID", "Code", "CityMarketID", "State", "Country"]
READ_COLS = sorted(set(KEYS) | {"ItinID", "MktID", "Origin", "Dest", "OriginState", "DestState"})


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 24), b""):
            h.update(b)
    return h.hexdigest()


def find_sources(data_dir):
    """Every parquet source: members of ZIPs plus loose files. Other ZIP members are logged, not read."""
    sources, other = [], []
    for zp in sorted(data_dir.glob("*.zip")):
        with zipfile.ZipFile(zp) as z:
            for i in z.infolist():
                rec = dict(container=zp.name, member=i.filename, member_bytes=i.file_size, member_crc=f"{i.CRC:08x}")
                (sources if i.filename.lower().endswith(".parquet") else other).append(rec)
    for p in sorted(data_dir.glob("*.parquet")):
        sources.append(dict(container=p.name, member="", member_bytes=p.stat().st_size, member_crc=""))
    return sources, other


def process_parquet(path):
    """Aggregate one parquet file. Returns (agg table, airport lookup, per-month id checks, schema, rows)."""
    pf = pq.ParquetFile(path)
    names = {n.lower(): n for n in pf.schema_arrow.names}  # explicit case normalization
    missing = [c for c in READ_COLS if c.lower() not in names]
    if missing:
        sys.exit(f"{path.name}: missing columns {missing}")
    aggs, apts, ids = [], [], []
    for b in pf.iter_batches(batch_size=2_000_000, columns=[names[c.lower()] for c in READ_COLS]):
        t = pa.Table.from_batches([b]).rename_columns(READ_COLS)
        aggs.append(t.group_by(KEYS).aggregate([("ItinID", "count")]))
        for side in ("Origin", "Dest"):
            a = t.select([f"{side}AirportID", side, f"{side}CityMarketID", f"{side}State", f"{side}Country"])
            apts.append(a.rename_columns(APT).group_by(APT).aggregate([]))
        ym = pc.add(pc.multiply(pc.cast(t["RpYear"], pa.int64()), 100), pc.cast(t["RpMonth"], pa.int64()))
        ids.append(pa.table({
            "ym": ym, "MktID": t["MktID"],
            # ItinID starts with YYYYMM (15 digits through Feb 2026, 14 digits from Mar 2026)
            "itin_bad": pc.not_equal(pc.cast(pc.utf8_slice_codeunits(pc.cast(t["ItinID"], pa.string()), 0, 6), pa.int64()), ym)}))
    agg = pa.concat_tables(aggs).group_by(KEYS).aggregate([("ItinID_count", "sum")]).to_pandas()
    agg = agg.rename(columns={"ItinID_count_sum": "records"})
    apt = pa.concat_tables(apts).group_by(APT).aggregate([]).to_pandas()
    checks = pa.concat_tables(ids).group_by("ym").aggregate(
        [("MktID", "count"), ("MktID", "count_distinct"), ("itin_bad", "sum")]).to_pandas()
    return agg, apt, checks, {n.lower(): str(pf.schema_arrow.field(n).type) for n in pf.schema_arrow.names}, pf.metadata.num_rows


def build_crosswalk(apt, names):
    bad = apt[apt[["AirportID", "CityMarketID"]].isna().any(axis=1)]
    if len(bad):
        print("WARNING: airport codes with missing ID/city market (excluded):", sorted(bad.Code.dropna().unique()))
    cw = apt.drop_duplicates("AirportID").dropna(subset=["AirportID", "CityMarketID"])
    cw = cw.astype({"AirportID": int, "CityMarketID": int})
    dup = cw.groupby("AirportID").CityMarketID.nunique()
    if (dup > 1).any():
        sys.exit(f"Airports with more than one city-market ID: {list(dup[dup > 1].index)}")
    ref_code = {c: g for g, cs in REF_GROUPS.items() for c in cs.split()}
    # reference group -> the BTS city market most of its listed airports belong to
    grp_main = (cw[cw.Code.isin(ref_code)].assign(grp=lambda d: d.Code.map(ref_code))
                .groupby("grp").CityMarketID.agg(lambda s: s.mode().iloc[0]))
    cm_grp = {cm: g for g, cm in grp_main.items()}
    missing_ref = sorted(set(ref_code) - set(cw.Code))
    keys, disp, reason = [], [], []
    for r in cw.itertuples():
        if r.Code in FORCE_SEPARATE and r.CityMarketID in cm_grp:
            k, n, why = f"AP{r.AirportID}", None, FORCE_SEPARATE[r.Code]
        elif r.Code in ref_code:
            g = ref_code[r.Code]
            k, n = f"CM{grp_main[g]}", g
            why = "" if r.CityMarketID == grp_main[g] else f"Moved from BTS city market {r.CityMarketID} to match reference group"
        elif r.CityMarketID in cm_grp:
            k, n = f"CM{r.CityMarketID}", cm_grp[r.CityMarketID]
            why = "BTS city-market member not listed in the airport-group note; retained per BTS definition"
        else:
            k, n, why = f"CM{r.CityMarketID}", None, ""
        keys.append(k); disp.append(n); reason.append(why)
    cw["analysis_key"], cw["display_name"], cw["override_reason"] = keys, disp, reason
    cw["in_airport_group_note"] = cw.Code.isin(ref_code)
    # names for other markets: curated file, else "AAA/BBB (ST)"
    fallback = cw.groupby("analysis_key").apply(
        lambda d: "/".join(sorted(d.Code)) + f" ({'/'.join(sorted(set(d.State.dropna())))})", include_groups=False)
    cw["display_name"] = cw.display_name.fillna(cw.analysis_key.map(names)).fillna(cw.analysis_key.map(fallback))
    return cw.sort_values(["analysis_key", "Code"]), missing_ref


def label(months):
    """(file tag, short period, long period, final?)"""
    if months == PERIOD:
        return "2025-07_to_2026-06", "July 2025–June 2026", "July 1, 2025–June 30, 2026", True
    (y0, m0), (y1, m1) = months[0], months[-1]
    contiguous = PERIOD[PERIOD.index(months[0]):PERIOD.index(months[-1]) + 1] == months
    tag = f"PREVIEW_{y0}-{m0:02d}_to_{y1}-{m1:02d}" + ("" if contiguous else "_gaps")
    nice = (f"{MONTH_NAMES[m0-1]}–{MONTH_NAMES[m1-1]} {y0}" if y0 == y1 else
            f"{MONTH_NAMES[m0-1]} {y0}–{MONTH_NAMES[m1-1]} {y1}")
    if not contiguous:
        nice = ", ".join(f"{MONTH_NAMES[m-1][:3]} {y}" for y, m in months)
    return tag, nice, nice, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--output-dir", default=str(ROOT / "results"))
    args = ap.parse_args()
    data_dir, out = Path(args.data_dir), Path(args.output_dir)
    work = data_dir / "_work"
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    # ---- 1. inventory and read -------------------------------------------------------------
    sources, other = find_sources(data_dir)
    if not sources:
        sys.exit(f"No parquet sources in {data_dir}")
    manifest, monthly, apts, checks, schemas, used = [], [], [], [], {}, {}
    for s in sources:
        container = data_dir / s["container"]
        print(f"reading {s['container']} {s['member']}", flush=True)
        s["container_sha256"] = sha256(container)
        if s["member"]:
            with zipfile.ZipFile(container) as z:
                z.extract(s["member"], work)
            path = work / s["member"]
        else:
            path = container
        agg, apt, chk, schema, nrows = process_parquet(path)
        if s["member"]:
            path.unlink()
        s["rows"] = nrows
        s["schema_sha"] = hashlib.sha1(json.dumps(schema, sort_keys=True).encode()).hexdigest()[:12]
        schemas[s["schema_sha"]] = schema
        for (y, m), g in agg.groupby(["RpYear", "RpMonth"]):
            ym, recs = (int(y), int(m)), int(g.records.sum())
            entry = dict(s, rp_year=ym[0], rp_month=ym[1], month_records=recs)
            if ym not in PERIOD:
                entry["status"] = "excluded: outside requested period"
            elif ym in used:
                prev = used[ym]
                same = prev["month_records"] == recs
                entry["status"] = f"duplicate of {prev['container']} ({'identical' if same else 'DIFFERENT'} record count); not used"
            else:
                entry["status"] = "used"
                used[ym] = entry
                monthly.append(g.assign(source=s["container"]))
                checks.append(chk[chk.ym == ym[0] * 100 + ym[1]].assign(source=s["container"]))
            manifest.append(entry)
        apts.append(apt)
    shutil.rmtree(work, ignore_errors=True)

    months = [p for p in PERIOD if p in used]
    missing = [f"{y}-{m:02d}" for y, m in PERIOD if (y, m) not in used]
    tag, period_short, period_long, final = label(months)
    print(f"\nCoverage: {len(months)} of 12 months. Missing: {missing or 'none'}. Output label: {tag}")

    pd.DataFrame(manifest).assign(dataset="BTS DB1C Market (40% sample)").to_csv(
        out / f"input_manifest_{tag}.csv", index=False)
    pd.DataFrame(other).to_csv(out / f"input_alternate_formats_not_read_{tag}.csv", index=False)
    if len(schemas) > 1:
        print("WARNING: schema differs across files:", list(schemas))

    df = pd.concat(monthly, ignore_index=True)
    chk = pd.concat(checks, ignore_index=True)
    names = pd.read_csv(HERE / "market_names.csv", dtype=str, encoding="utf-8-sig").set_index("analysis_key").display_name.to_dict()
    cw, missing_ref = build_crosswalk(pd.concat(apts).drop_duplicates(), names)
    cw.to_csv(out / f"airport_crosswalk_{tag}.csv", index=False)

    # ---- 2. filter, classify, aggregate ------------------------------------------------------
    df["sample_pax"] = df.Passengers.astype(float) * df.records
    key = cw.set_index("AirportID").analysis_key
    df["okey"], df["dkey"] = df.OriginAirportID.map(key), df.DestAirportID.map(key)
    df["stage"] = "retained"
    bad_pax = df.Passengers.isna() | (df.Passengers <= 0)
    bad_end = df[["OriginAirportID", "DestAirportID", "okey", "dkey"]].isna().any(axis=1)
    nondom = ~df.MktGeoType.isin(DOMESTIC_GEO) | (df.OriginCountry.fillna("US") != "US") | (df.DestCountry.fillna("US") != "US")
    same = df.okey == df.dkey
    bad_cpn = df.MktCoupons.isna() | (df.MktCoupons < 1)
    for mask, name in [(bad_cpn, "unclassifiable coupon count"), (same, "same analysis market"),
                       (nondom, "non-domestic geography/country"), (bad_end, "invalid endpoint"),
                       (bad_pax, "non-positive/missing passengers")]:
        df.loc[mask, "stage"] = name  # later assignment = earlier filter stage
    df["est_pax"] = df.sample_pax * FACTOR
    df["cls"] = (df.MktCoupons >= 2).map({True: "connecting", False: "single"})

    stages = df.groupby("stage")[["records", "sample_pax", "est_pax"]].sum()
    diag = df.pivot_table(index=["RpYear", "RpMonth"], columns="stage", values="est_pax", aggfunc="sum", fill_value=0)
    base = df.groupby(["RpYear", "RpMonth"]).agg(source=("source", "first"), records=("records", "sum"),
                                                  sample_pax=("sample_pax", "sum"), est_pax=("est_pax", "sum"))
    ret = df[df.stage == "retained"]
    split = ret.pivot_table(index=["RpYear", "RpMonth"], columns="cls", values="est_pax", aggfunc="sum")
    thru = ret[(ret.MktCoupons == 1) & (ret.Nonstop == 0)].groupby(["RpYear", "RpMonth"]).est_pax.sum()
    geo = ret.pivot_table(index=["RpYear", "RpMonth"], columns="MktGeoType", values="est_pax", aggfunc="sum")
    geo.columns = [f"retained_geo{int(c)}_est" for c in geo.columns]
    md = base.join(diag.add_prefix("est_pax_")).join(split.add_prefix("retained_").add_suffix("_est")).join(geo)
    md["single_coupon_with_stop_est"] = thru
    md = md.join(chk.assign(RpYear=chk.ym // 100, RpMonth=chk.ym % 100).set_index(["RpYear", "RpMonth"])
                 [["MktID_count", "MktID_count_distinct", "itin_bad_sum"]])
    md["expansion_factor"] = FACTOR
    md.reset_index().to_csv(out / f"monthly_diagnostics_{tag}.csv", index=False)

    lo = ret.okey < ret.dkey
    ret = ret.assign(k1=ret.okey.where(lo, ret.dkey), k2=ret.dkey.where(lo, ret.okey))
    pairs = ret.pivot_table(index=["k1", "k2"], columns="cls", values="est_pax", aggfunc="sum", fill_value=0)
    pairs = pairs.rename(columns={"connecting": "connecting_traffic", "single": "single_coupon_traffic"})
    pairs["total_traffic"] = pairs.connecting_traffic + pairs.single_coupon_traffic
    pairs["single_coupon_with_intermediate_stop"] = ret[(ret.MktCoupons == 1) & (ret.Nonstop == 0)].groupby(
        ["k1", "k2"]).est_pax.sum().reindex(pairs.index, fill_value=0)
    pairs["sample_records"] = ret.groupby(["k1", "k2"]).records.sum()
    pairs["percent_connecting"] = 100 * pairs.connecting_traffic / pairs.total_traffic
    pairs = pairs.reset_index()
    mkt_total = pd.concat([pairs.set_index("k1").total_traffic, pairs.set_index("k2").total_traffic]).groupby(level=0).sum()
    mname = cw.drop_duplicates("analysis_key").set_index("analysis_key").display_name
    # display convention: the endpoint with more total retained O&D traffic is "City market 1"
    swap = mkt_total.reindex(pairs.k2).values > mkt_total.reindex(pairs.k1).values
    pairs["market1_key"] = pairs.k1.where(~swap, pairs.k2)
    pairs["market2_key"] = pairs.k2.where(~swap, pairs.k1)
    pairs["city_market_1"], pairs["city_market_2"] = pairs.market1_key.map(mname), pairs.market2_key.map(mname)
    pairs = pairs.sort_values(["total_traffic", "k1", "k2"], ascending=[False, True, True], kind="mergesort")
    pairs.insert(0, "rank", range(1, len(pairs) + 1))
    cols = ["rank", "city_market_1", "city_market_2", "total_traffic", "connecting_traffic", "single_coupon_traffic",
            "percent_connecting", "single_coupon_with_intermediate_stop", "sample_records", "market1_key", "market2_key",
            "k1", "k2"]
    pairs = pairs[cols]
    pairs.to_csv(out / f"all_city_pairs_{tag}.csv", index=False)
    top = pairs.head(100).copy()
    top.to_csv(out / f"top100_analytical_{tag}.csv", index=False)

    # display rounding: round total & connecting half-up; single-coupon = total - connecting
    def r(x): return (x + 0.5).apply(int)  # values are multiples of 0.5, all positive
    disp = pd.DataFrame({"Rank": top["rank"], "City market 1": top.city_market_1, "City market 2": top.city_market_2})
    disp["Annual traffic, both ways"] = r(top.total_traffic)
    disp["Connecting O&D traffic"] = r(top.connecting_traffic)
    disp["Nonstop O&D traffic*"] = disp["Annual traffic, both ways"] - disp["Connecting O&D traffic"]
    adjusted = int((disp["Nonstop O&D traffic*"] != r(top.single_coupon_traffic)).sum())
    disp["Percent connecting"] = top.percent_connecting.map(lambda v: f"{v:.1f}%")
    disp_fmt = disp.copy()
    for c in ["Annual traffic, both ways", "Connecting O&D traffic", "Nonstop O&D traffic*"]:
        disp_fmt[c] = disp[c].map("{:,}".format)
    disp_fmt.to_csv(out / f"top100_display_{tag}.csv", index=False, encoding="utf-8-sig")
    disp.to_csv(out / f"top100_table_{tag}.csv", index=False, encoding="utf-8-sig")  # unformatted, feeds index.html

    # ---- 3. validation ---------------------------------------------------------------------
    pk = pairs[["k1", "k2"]]
    v = {
        "months_used": [f"{y}-{m:02d}" for y, m in months], "months_missing": missing, "final": final,
        "expansion_factor": FACTOR, "passengers_values_seen": sorted(df.Passengers.dropna().unique().tolist()),
        "each_month_once": len(months) == len(set(months)),
        "no_reversed_duplicate_pairs": bool((pk.k1 < pk.k2).all() and not pk.duplicated().any()),
        "no_same_market_pairs": bool((pk.k1 != pk.k2).all()),
        "total_equals_components_max_abs_err": float((pairs.total_traffic - pairs.connecting_traffic - pairs.single_coupon_traffic).abs().max()),
        "percent_in_0_100": bool(pairs.percent_connecting.between(0, 100).all()),
        "top100_pct_recompute_max_err": float((100 * top.connecting_traffic / top.total_traffic - top.percent_connecting).abs().max()),
        "retained_est_equals_pair_sum": bool(abs(ret.est_pax.sum() - pairs.total_traffic.sum()) < 1e-6),
        "stages_reconcile_to_raw": bool(abs(stages.est_pax.sum() - df.sample_pax.sum() * FACTOR) < 1e-6),
        "crosswalk_one_row_per_airport": bool(cw.AirportID.is_unique),
        "mktid_unique_within_month": bool((chk.MktID_count == chk.MktID_count_distinct).all()),
        "itinid_period_prefix_mismatch_rows": int(chk.itin_bad_sum.sum()),
        "reference_airports_absent_from_data": missing_ref,
        "display_rows_with_rounding_reconciliation": adjusted,
        "schema_variants": len(schemas),
        "stage_totals": stages.reset_index().to_dict("records"),
        "top100_markets_using_fallback_names": sorted(set(top.city_market_1[top.city_market_1.str.contains(r"\(")]) |
                                                      set(top.city_market_2[top.city_market_2.str.contains(r"\(")])),
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    (out / f"validation_{tag}.json").write_text(json.dumps(v, indent=2, default=str))
    run_info = dict(tag=tag, period_short=period_short, period_long=period_long, final=final, missing=missing)
    (out / "run_info.json").write_text(json.dumps(run_info, indent=2))
    airport_traffic.count(data_dir, out)  # per-airport counts; build_page lists only airports with traffic
    build_page.build(out, ROOT / "index.html")
    print(json.dumps({k: v[k] for k in v if k != "stage_totals"}, indent=1, default=str))
    print(top.head(15)[["rank", "city_market_1", "city_market_2", "total_traffic", "percent_connecting"]].to_string(index=False))


if __name__ == "__main__":
    main()
