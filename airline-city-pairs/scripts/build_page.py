"""Build index.html (the GitHub Pages table) from results/.

Usage (from the repo root): python scripts/build_page.py
run_all.py calls this automatically, so it only needs to be run alone after editing the template or text.
texts() and table_rows() are shared with build_social.py so the page and the social images always match.
"""
import html, json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DAYS = 365  # July 1, 2025-June 30, 2026
# Display names for multi-airport BTS city markets (all match current BTS city-market IDs; see METHODS.md)
REF_GROUPS = {
    "New York City": "JFK EWR LGA HPN ISP SWF",
    "Los Angeles": "LAX SNA BUR ONT LGB",
    "Chicago": "ORD MDW",
    "Washington - Baltimore": "BWI DCA IAD",
    "Dallas": "DFW DAL",
    "Houston": "IAH HOU",
    "Greater Boston": "BOS PVD MHT",
    "San Francisco Bay Area": "SFO OAK SJC",
    "Phoenix": "PHX AZA",
    "Miami - Fort Lauderdale": "MIA FLL",
    "Tampa Bay": "TPA PIE LAL",
    "Cleveland - Akron/Canton": "CLE CAK",
    "Norfolk - Newport News": "ORF PHF",
    "Columbus": "CMH LCK",
    "Denver": "DEN APA",
    "Seattle": "SEA BFI KEH LKE",
    "Las Vegas": "LAS HSH",
    "San Juan": "SJU SIG",
}


def airport_groups(info, results_dir=ROOT / "results"):
    """Every multi-airport city market in the top 100, listing only airports with retained passengers
    (from airport_traffic.py's output)."""
    traffic = pd.read_csv(Path(results_dir) / f"airport_traffic_{info['tag']}.csv")
    top = pd.read_csv(Path(results_dir) / f"top100_analytical_{info['tag']}.csv")
    cw = traffic[traffic.analysis_key.isin(set(top.k1) | set(top.k2)) & (traffic.sample_pax > 0)]
    order = {c: i for cs in REF_GROUPS.values() for i, c in enumerate(cs.split())}
    groups = {name: sorted(d.Code, key=lambda c: (order.get(c, 99), c))
              for name, d in cw.groupby("display_name") if len(d) > 1}
    rank = {g: i for i, g in enumerate(REF_GROUPS)}
    return "; ".join(f"{n}: {', '.join(groups[n])}" for n in sorted(groups, key=lambda n: rank.get(n, 99)))
COLUMNS = ["#", "City market 1", "City market 2", "12-month journeys, both ways",
           "Avg. daily journeys, each way", "% with stops"]


def texts(info):
    """All wording shared by the page and the social images."""
    t = dict(
        title="100 most traveled airline city pairs, United States",
        period=info["period_short"].replace("–", " to "),
        sub="Passenger origin–destination journeys between city markets, both directions combined, "
            "including trips with stops.",
        notes=[
            "A roundtrip journey counts as two journeys (one each way). Average daily journeys each way are total "
            "journeys over the 12-month period divided by 365 divided by 2. “With stops” are trips with a change of "
            "flight (two or more flight coupons).",
            f"Nearby airports grouped per BTS city markets ({airport_groups(info)})",
            "Domestic tickets only. Trips on international tickets, including domestic flights, excluded from data set",
        ],
        source=f"Source: Bureau of Transportation Statistics, DB1C Market, "
               f"{info['period_long']} (40% sample times 2.5)",
    )
    if not info["final"]:
        t["title"] += " (PREVIEW – partial period)"
        t["sub"] += f" Incomplete preview: missing {', '.join(info['missing'])}; not a 12-month total."
    return t


def table_rows(results_dir=ROOT / "results"):
    """[rank, city market 1, city market 2, 12-month journeys, avg daily each way, % with stops]"""
    info = json.loads((Path(results_dir) / "run_info.json").read_text())
    df = pd.read_csv(Path(results_dir) / f"top100_table_{info['tag']}.csv", encoding="utf-8-sig")
    rows = [[int(r[0]), r[1], r[2], int(r[3]), round(int(r[3]) / DAYS / 2), float(r[6].rstrip("%"))]
            for r in df.itertuples(index=False)]
    return info, rows


def build(results_dir=ROOT / "results", out_path=ROOT / "index.html"):
    info, rows = table_rows(results_dir)
    t = texts(info)
    e = html.escape
    page = (HERE / "page_template.html").read_text(encoding="utf-8")
    for k, v in {
        "__TITLE__": e(t["title"]),
        "__PERIOD__": e(t["period"]),
        "__SUBTITLE__": e(t["sub"]),
        "__WARNING__": "" if info["final"] else
            f'<p class="warn">Preview: covers {e(info["period_long"])} only. Missing {e(", ".join(info["missing"]))}.</p>',
        "__NOTES__": "".join(f"<p>{e(n)}</p>" for n in t["notes"]),
        "__SOURCE__": e(t["source"]),
        "__CSV__": f"results/top100_display_{info['tag']}.csv",
        "__COLUMNS__": json.dumps(COLUMNS, ensure_ascii=False),
        "__DATA__": json.dumps(rows, ensure_ascii=False),
    }.items():
        page = page.replace(k, v)
    Path(out_path).write_text(page, encoding="utf-8")
    print(f"wrote {out_path}")


if __name__ == "__main__":
    build()
