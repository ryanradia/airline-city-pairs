"""Render four social-media PNGs (ranks 1-25, 26-50, 51-75, 76-100) from results/.

Usage (from the repo root): python scripts/build_social.py
Each image is 1125x1625 CSS px rendered at 1.6x = 1800x2600. Needs Microsoft Edge or Google Chrome for
headless rendering. Table rows stretch to fill the height left after the header and footer.
"""
import html, shutil, subprocess, tempfile
from pathlib import Path

import build_page  # shared wording, columns, and rows, so the images match index.html

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
W, H, SCALE, PER = 1125, 1625, 1.6, 25
BROWSERS = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            "msedge", "google-chrome", "chromium", "chrome"]

CSS = """
* { box-sizing: border-box; margin: 0; }
html, body { width: 1125px; background: #fff; overflow: hidden; }
body { font-family: Roboto, "Helvetica Neue", Arial, sans-serif; color: #333; -webkit-font-smoothing: antialiased;
  padding: 34px 28px 26px; font-variant-numeric: tabular-nums; }
h1 { font-size: 37px; line-height: 1.15; font-weight: 700; color: #181818; letter-spacing: -0.01em; text-wrap: balance; }
.period { font-size: 26px; font-weight: 500; color: #1d81a2; margin-top: 8px; }
.sub { font-size: 20px; color: #6a6a6a; margin-top: 12px; line-height: 1.4; }
.sub b { color: #333; font-weight: 500; }
table { width: 100%; border-collapse: collapse; margin-top: 24px; table-layout: fixed; }
th { font-size: 17px; font-weight: 700; color: #181818; text-align: left; padding: 0 10px 10px; border-bottom: 2.5px solid #333;
  vertical-align: bottom; line-height: 1.2; white-space: nowrap; }
th.city { font-size: 17px; }
td { font-size: 23px; padding: 0 10px; height: 40px; border-bottom: 1px solid #ececec; white-space: nowrap;
  overflow: hidden; text-overflow: ellipsis; }
tbody tr:nth-child(even) td { background: #f4f4f4; }
.rk { width: 66px; color: #6a6a6a; text-align: right; padding-right: 14px; text-overflow: clip; }
.city { width: 270px; font-size: 21px; font-weight: 500; color: #181818; }
.num { text-align: right; color: #181818; }
.day { width: 150px; text-align: right; color: #181818; }
.pct { width: 120px; text-align: right; }
.foot { margin-top: 16px; font-size: 14.5px; line-height: 1.5; color: #6a6a6a; }
.foot p + p { margin-top: 5px; }
.pg { margin-top: 10px; padding-top: 10px; border-top: 1px solid #d9d9d9; text-align: right; font-size: 16px; color: #6a6a6a; }
"""


def page(rows, part, info):
    e = html.escape
    t = build_page.texts(info)
    body = "".join(
        f'<tr><td class="rk">{rk}</td><td class="city">{e(a)}</td><td class="city">{e(b)}</td>'
        f'<td class="num">{tot:,}</td><td class="day">{day:,}</td><td class="pct">{pct:.1f}%</td></tr>'
        for rk, a, b, tot, day, pct in rows)
    heads = "".join(f'<th class="{c}">{e(lab).replace(", ", ",<br>").replace("% with ", "% with<br>")}</th>'
                    for c, lab in zip(["rk", "city", "city", "num", "day", "pct"], build_page.COLUMNS))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body>
<h1>{e(t['title'])}</h1>
<div class="period">{e(t['period'])}</div>
<p class="sub">{e(t['sub'])}</p>
<table><thead><tr>{heads}</tr></thead>
<tbody>{body}</tbody></table>
<div class="foot">{"".join(f"<p>{e(n)}</p>" for n in t['notes'])}<p>{e(t['source'])}</p></div>
<div class="pg">{part} / 4</div>
<script>
// stretch the 25 rows so the page fills the image height exactly, with no empty band above the footer
document.fonts.ready.then(() => {{
  const rows = document.querySelectorAll("tbody tr");
  const extra = {H} - document.body.scrollHeight;
  const h = rows[0].getBoundingClientRect().height + extra / rows.length;
  rows.forEach(r => r.style.height = h + "px");
}});
</script>
</body></html>"""


def find_browser():
    for b in BROWSERS:
        p = shutil.which(b) or (b if Path(b).exists() else None)
        if p:
            return p
    raise SystemExit("Edge or Chrome is needed to render the PNGs.")


def main(results_dir=ROOT / "results", out_dir=ROOT / "social"):
    info, rows = build_page.table_rows(results_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)
    browser = find_browser()
    with tempfile.TemporaryDirectory() as tmp:
        for part in range(1, 5):
            chunk = rows[(part - 1) * PER: part * PER]
            src = Path(tmp) / f"p{part}.html"
            src.write_text(page(chunk, part, info), encoding="utf-8")
            png = out_dir / f"top100_city_pairs_{part}of4_ranks_{chunk[0][0]}-{chunk[-1][0]}.png"
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--hide-scrollbars",
                            f"--window-size={W},{H}", f"--force-device-scale-factor={SCALE}",
                            "--virtual-time-budget=8000", f"--screenshot={png}", src.as_uri()],
                           check=True, capture_output=True)
            print(f"wrote {png}")


if __name__ == "__main__":
    main()
