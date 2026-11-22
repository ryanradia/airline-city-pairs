"""Count retained sampled and estimated passengers per airport, writing results/airport_traffic_<tag>.csv.

Usage (from the repo root): python scripts/airport_traffic.py --data-dir data
Retained = the same records the table uses: positive passengers, valid endpoints in different city markets
(per the crosswalk), and domestic geography. Each record counts once at its origin and once at its destination.
build_page.py uses this file to list only airports with retained traffic in the airport-group note.
"""
import argparse, json, zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
COLS = ["RpYear", "RpMonth", "OriginAirportID", "DestAirportID", "Passengers", "MktGeoType"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", default=str(ROOT / "data"))
    ap.add_argument("--results-dir", default=str(ROOT / "results"))
    args = ap.parse_args()
    count(Path(args.data_dir), Path(args.results_dir))


def count(data, res):
    """Called by run_all.py after the main results are written."""
    info = json.loads((res / "run_info.json").read_text())
    man = pd.read_csv(res / f"input_manifest_{info['tag']}.csv")
    used = man[man.status == "used"]
    cw = pd.read_csv(res / f"airport_crosswalk_{info['tag']}.csv")
    key = pa.array(cw.analysis_key)
    ids = pa.array(cw.AirportID, pa.int32())
    work = data / "_work"
    counts = []
    for r in used.itertuples():
        print("reading", r.container, flush=True)
        with zipfile.ZipFile(data / r.container) as z:
            z.extract(r.member, work)
        pf = pq.ParquetFile(work / r.member)
        for b in pf.iter_batches(batch_size=2_000_000, columns=COLS):
            t = pa.Table.from_batches([b])
            t = t.filter(pc.and_(pc.equal(t["RpYear"], r.rp_year), pc.equal(t["RpMonth"], r.rp_month)))
            ok = pc.and_(pc.greater(t["Passengers"], 0), pc.is_in(t["MktGeoType"], pa.array([1, 2], pa.int8())))
            ok_ = pc.fill_null(ok, False)
            ok_ = pc.and_(ok_, pc.not_equal(pc.take(key, pc.index_in(t["OriginAirportID"], ids)),
                                            pc.take(key, pc.index_in(t["DestAirportID"], ids))))
            t = t.filter(pc.fill_null(ok_, False))
            for side in ("OriginAirportID", "DestAirportID"):
                counts.append(t.group_by(side).aggregate([("Passengers", "sum")])
                              .rename_columns(["AirportID", "sample_pax"]).to_pandas())
        pf.close()  # Windows cannot delete a file that is still open
        (work / r.member).unlink()
    work.rmdir()
    out = pd.concat(counts).groupby("AirportID").sample_pax.sum().reset_index()
    out = cw[["AirportID", "Code", "CityMarketID", "analysis_key", "display_name"]].merge(out, how="left").fillna({"sample_pax": 0})
    out["est_pax"] = out.sample_pax * 2.5
    out.sort_values("est_pax", ascending=False).to_csv(res / f"airport_traffic_{info['tag']}.csv", index=False)
    print(out[out.sample_pax == 0].Code.tolist())


if __name__ == "__main__":
    main()
