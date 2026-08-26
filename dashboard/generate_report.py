"""
generate_report.py
-------------------
Builds a single self-contained HTML report summarizing the latest pipeline
run: an executive summary, validation pass/fail, flagged anomalies broken
down by sector, and two SVG charts (VIX history + P/E ratio distribution)
with custom hover tooltips. Run `python src/pipeline.py` first, then
`python dashboard/generate_report.py`.
"""

import json
import sys
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
sys.path.insert(0, str(ROOT / "src"))

PALETTE_CSS = """
:root {
  color-scheme: light;
  --surface-1:      #fcfcfb;
  --page:           #f9f9f7;
  --header-bg:      #f2f1ed;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --grid:           #e1e0d9;
  --baseline:       #c3c2b7;
  --border:         rgba(11,11,11,0.10);
  --series-blue:    #2a78d6;
  --series-blue-fill: rgba(42,120,214,0.12);
  --seq-100:        #cde2fb;
  --seq-400:        #3987e5;
  --status-good:    #0ca30c;
  --status-good-bg: #e9f7e9;
  --status-critical:    #d03b3b;
  --status-critical-bg: #fbeceb;
  --tooltip-bg: #0b0b0b;
  --tooltip-fg: #ffffff;
}
"""


def esc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return str(v)


# ---------------------------------------------------------------------------
# Chart 1: VIX history, monthly average line with a soft area fill,
# + flagged spike markers, as inline SVG with custom hover tooltips.
# ---------------------------------------------------------------------------
def chart_vix_svg() -> str:
    df = pd.read_csv(PROCESSED_DIR / "fact_market_volatility.csv", parse_dates=["date"])
    spikes = pd.read_csv(PROCESSED_DIR / "anomalies_vix_volatility_spikes.csv", parse_dates=["date"])

    monthly = df.set_index("date")["close"].resample("MS").mean().dropna()

    W, H = 860, 260
    PAD_L, PAD_R, PAD_T, PAD_B = 40, 16, 16, 28
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B

    x_min, x_max = monthly.index.min().toordinal(), monthly.index.max().toordinal()
    y_min, y_max = 0, max(monthly.max(), spikes["close"].max() if len(spikes) else 0) * 1.08

    def xs(d):
        return PAD_L + (d.toordinal() - x_min) / (x_max - x_min) * plot_w

    def ys(v):
        return PAD_T + plot_h - (v - y_min) / (y_max - y_min) * plot_h

    line_points = [(xs(d), ys(v)) for d, v in monthly.items()]
    points_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in line_points)
    baseline_y = PAD_T + plot_h
    area_points = f"{line_points[0][0]:.1f},{baseline_y:.1f} " + points_str + f" {line_points[-1][0]:.1f},{baseline_y:.1f}"

    grid_svg = []
    for i in range(5):
        v = y_min + (y_max - y_min) * i / 4
        y = ys(v)
        grid_svg.append(f'<line x1="{PAD_L}" y1="{y:.1f}" x2="{W-PAD_R}" y2="{y:.1f}" class="gridline"/>')
        grid_svg.append(f'<text x="{PAD_L-8}" y="{y+3:.1f}" class="axis-label" text-anchor="end">{v:.0f}</text>')

    x_labels = []
    for year in range(1990, 2027, 5):
        d = date(year, 1, 1)
        x = PAD_L + (d.toordinal() - x_min) / (x_max - x_min) * plot_w
        x_labels.append(f'<text x="{x:.1f}" y="{H-8}" class="axis-label" text-anchor="middle">{year}</text>')

    markers = []
    for _, row in spikes.iterrows():
        cx, cy = xs(row["date"]), ys(row["close"])
        tip = (f"{row['date'].date()} — VIX {row['close']:.1f} "
               f"({row['pct_change']*100:+.1f}% day change, z={row['change_zscore']:.1f})")
        markers.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4.5" class="mark-critical" '
            f'data-tip="{tip}"/>'
        )

    return f"""
<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" aria-label="VIX daily volatility index, monthly average, 1990 to present, with flagged spike days highlighted">
  {''.join(grid_svg)}
  <polygon points="{area_points}" class="area-fill"/>
  <polyline points="{points_str}" class="line-series"/>
  {''.join(markers)}
  {''.join(x_labels)}
</svg>
"""


# ---------------------------------------------------------------------------
# Chart 2: P/E ratio distribution, histogram bars with hover tooltips,
# flagged-outlier bins in the status-critical color.
# ---------------------------------------------------------------------------
def chart_pe_svg() -> str:
    df = pd.read_csv(PROCESSED_DIR / "fact_company_financials.csv")
    outliers = pd.read_csv(PROCESSED_DIR / "anomalies_pe_ratio_outliers.csv")
    values = df["pe_ratio"].dropna()

    n_bins = 36
    v_min, v_max = 0, values.quantile(0.995)
    bin_width = (v_max - v_min) / n_bins
    counts = [0] * n_bins
    bin_has_outlier = [False] * n_bins
    for v in values:
        idx = min(int((v - v_min) / bin_width), n_bins - 1) if v_min <= v else None
        if idx is not None and 0 <= idx < n_bins:
            counts[idx] += 1
    for v in outliers["pe_ratio"]:
        idx = int((v - v_min) / bin_width)
        idx = max(0, min(idx, n_bins - 1))
        bin_has_outlier[idx] = True

    W, H = 860, 220
    PAD_L, PAD_R, PAD_T, PAD_B = 36, 16, 16, 28
    plot_w, plot_h = W - PAD_L - PAD_R, H - PAD_T - PAD_B
    max_count = max(counts) or 1
    bar_w = plot_w / n_bins

    bars = []
    for i, c in enumerate(counts):
        bh = (c / max_count) * plot_h
        x = PAD_L + i * bar_w
        y = PAD_T + plot_h - bh
        cls = "bar-critical" if bin_has_outlier[i] else "bar-series"
        lo, hi = v_min + i * bin_width, v_min + (i + 1) * bin_width
        tip = f"P/E {lo:.0f}–{hi:.0f}: {c} compan{'y' if c == 1 else 'ies'}" + (" (contains a flagged outlier)" if bin_has_outlier[i] else "")
        bars.append(
            f'<rect x="{x+0.6:.1f}" y="{y:.1f}" width="{bar_w-1.2:.1f}" height="{max(bh,1):.1f}" '
            f'class="{cls}" data-tip="{tip}"/>'
        )

    x_labels = []
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        v = v_min + (v_max - v_min) * frac
        x = PAD_L + frac * plot_w
        x_labels.append(f'<text x="{x:.1f}" y="{H-8}" class="axis-label" text-anchor="middle">{v:.0f}</text>')

    return f"""
<svg viewBox="0 0 {W} {H}" class="chart-svg" role="img" aria-label="Distribution of price to earnings ratios across S&amp;P 500 companies, with statistical outlier bins highlighted">
  {''.join(bars)}
  <line x1="{PAD_L}" y1="{PAD_T+plot_h}" x2="{W-PAD_R}" y2="{PAD_T+plot_h}" class="baseline"/>
  {''.join(x_labels)}
</svg>
"""


# ---------------------------------------------------------------------------
# Sector breakdown: which GICS sectors the flagged (outlier) companies
# cluster in. Rendered as plain HTML/CSS bars, not SVG -- much simpler
# and more reliable for a labeled horizontal list like this.
# ---------------------------------------------------------------------------
def sector_breakdown_html() -> str:
    companies = pd.read_csv(PROCESSED_DIR / "dim_company.csv")
    pe_outliers = pd.read_csv(PROCESSED_DIR / "anomalies_pe_ratio_outliers.csv")
    pb_outliers = pd.read_csv(PROCESSED_DIR / "anomalies_price_to_book_outliers.csv")

    flagged_symbols = set(pe_outliers["symbol"]) | set(pb_outliers["symbol"])
    if not flagged_symbols:
        return '<p class="section-note">No companies were flagged this run.</p>'

    flagged = companies[companies["symbol"].isin(flagged_symbols)]
    counts = flagged.groupby("gics_sector").size().sort_values(ascending=False)
    max_count = counts.max()

    rows = []
    for sector, count in counts.items():
        pct = count / max_count * 100
        rows.append(f"""
        <div class="bar-row">
          <span class="bar-label">{esc(sector)}</span>
          <div class="bar-track"><div class="bar-fill" style="width:{pct:.1f}%"></div></div>
          <span class="bar-value">{count}</span>
        </div>""")
    return "\n".join(rows)


def build_html() -> str:
    with open(PROCESSED_DIR / "run_report.json") as f:
        report = json.load(f)
    validation_df = pd.read_csv(PROCESSED_DIR / "validation_report.csv")
    pe_outliers = pd.read_csv(PROCESSED_DIR / "anomalies_pe_ratio_outliers.csv")
    pb_outliers = pd.read_csv(PROCESSED_DIR / "anomalies_price_to_book_outliers.csv")
    vix_spikes = pd.read_csv(PROCESSED_DIR / "anomalies_vix_volatility_spikes.csv")

    n_passed = report["validation"]["passed"]
    n_total = report["validation"]["total_checks"]
    n_failed = n_total - n_passed
    n_anom = sum(report["anomalies"].values())

    # Executive summary, generated from the actual numbers in this run.
    if n_failed == 0:
        summary = f"This run passed all {n_total} data quality checks and flagged {n_anom} statistical anomalies worth a second look."
    else:
        summary = (
            f"This run found {n_failed} of {n_total} data quality checks failing — real issues in the "
            f"source data, not test artifacts (see below) — and flagged {n_anom} statistical anomalies "
            f"across company valuations and market volatility."
        )

    def status_pill(passed: bool) -> str:
        if passed:
            return '<span class="pill pill-good">&#10003; pass</span>'
        return '<span class="pill pill-critical">&#10007; fail</span>'

    validation_rows = "\n".join(
        f"""<tr class="{'row-fail' if not row.passed else ''}">
              <td>{esc(row.table)}</td><td>{esc(row.check)}</td><td>{esc(row.column)}</td>
              <td>{status_pill(row.passed)}</td><td class="detail">{esc(row.detail)}</td>
            </tr>"""
        for row in validation_df.itertuples()
    )

    def rows(df, cols, fmt=None, limit=12):
        fmt = fmt or {}
        out = []
        for _, row in df.head(limit).iterrows():
            cells = "".join(f"<td>{fmt.get(c, '{}').format(row[c])}</td>" for c in cols)
            out.append(f"<tr>{cells}</tr>")
        return "\n".join(out) if out else '<tr><td colspan="10" class="empty">None flagged</td></tr>'

    pe_rows = rows(pe_outliers, ["symbol", "pe_ratio", "zscore"], {"pe_ratio": "{:.1f}", "zscore": "{:.2f}"})
    pb_rows = rows(pb_outliers, ["symbol", "price_to_book", "zscore"], {"price_to_book": "{:.1f}", "zscore": "{:.2f}"})
    vix_rows = rows(vix_spikes.sort_values("date", ascending=False),
                     ["date", "close", "pct_change", "change_zscore"],
                     {"close": "{:.2f}", "pct_change": "{:+.1%}", "change_zscore": "{:.2f}"})

    vix_svg = chart_vix_svg()
    pe_svg = chart_pe_svg()
    sector_html = sector_breakdown_html()

    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>Financial Data Pipeline — Run Report</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
{PALETTE_CSS}
* {{ box-sizing: border-box; }}
body {{
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page); color: var(--text-primary);
  margin: 0; padding: 0 0 80px;
}}
.wrap {{ max-width: 960px; margin: 0 auto; padding: 0 20px; }}
header.hero {{
  background: var(--header-bg); border-bottom: 1px solid var(--border);
  padding: 40px 0 32px; margin-bottom: 40px;
}}
h1 {{ font-size: 25px; font-weight: 650; margin: 0 0 6px; letter-spacing: -0.01em; }}
.meta {{ color: var(--text-secondary); font-size: 13px; margin-bottom: 16px; }}
.summary {{ font-size: 15px; color: var(--text-primary); line-height: 1.5; max-width: 720px; }}
.stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 24px; }}
.stat {{
  background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px;
  padding: 18px 20px;
}}
.stat .n {{ font-size: 30px; font-weight: 650; font-variant-numeric: proportional-nums; line-height: 1.1; }}
.stat .n.warn {{ color: var(--status-critical); }}
.stat .label {{ font-size: 11px; color: var(--text-muted); text-transform: uppercase; letter-spacing: .04em; margin-top: 6px; }}
section {{ margin-top: 44px; }}
h2 {{ font-size: 15px; font-weight: 650; margin: 0 0 4px; }}
.section-note {{ font-size: 13px; color: var(--text-secondary); margin: 0 0 14px; }}
.card {{ background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }}
.chart-svg {{ width: 100%; height: auto; display: block; }}
.gridline {{ stroke: var(--grid); stroke-width: 1; }}
.baseline {{ stroke: var(--baseline); stroke-width: 1; }}
.axis-label {{ fill: var(--text-muted); font-size: 10px; font-family: system-ui, sans-serif; }}
.area-fill {{ fill: var(--series-blue-fill); stroke: none; }}
.line-series {{ fill: none; stroke: var(--series-blue); stroke-width: 1.6; stroke-linejoin: round; }}
.bar-series {{ fill: var(--seq-400); cursor: default; }}
.bar-critical {{ fill: var(--status-critical); cursor: default; }}
.mark-critical {{ fill: var(--status-critical); stroke: var(--surface-1); stroke-width: 1.5; cursor: default; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 4px; }}
th {{
  text-align: left; color: var(--text-muted); font-weight: 500; font-size: 10.5px;
  text-transform: uppercase; letter-spacing: .04em; padding: 7px 10px; border-bottom: 1px solid var(--border);
}}
td {{ padding: 7px 10px; border-bottom: 1px solid var(--grid); font-variant-numeric: tabular-nums; }}
td.detail {{ font-variant-numeric: normal; color: var(--text-secondary); }}
tr.row-fail {{ background: var(--status-critical-bg); }}
tr:last-child td {{ border-bottom: none; }}
td.empty {{ color: var(--text-muted); text-align: center; padding: 16px; font-variant-numeric: normal; }}
.pill {{
  display: inline-flex; align-items: center; gap: 4px; font-size: 11.5px; font-weight: 600;
  padding: 2px 9px; border-radius: 100px;
}}
.pill-good {{ color: var(--status-good); background: var(--status-good-bg); }}
.pill-critical {{ color: var(--status-critical); background: var(--status-critical-bg); }}
.legend {{ display: flex; gap: 18px; font-size: 12px; color: var(--text-secondary); margin-top: 10px; }}
.legend span {{ display: inline-flex; align-items: center; gap: 6px; }}
.swatch {{ width: 10px; height: 10px; border-radius: 3px; display: inline-block; }}
.two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-top: 14px; }}
.bar-row {{ display: flex; align-items: center; gap: 12px; padding: 6px 0; }}
.bar-label {{ width: 220px; flex-shrink: 0; font-size: 12.5px; color: var(--text-secondary); }}
.bar-track {{ flex: 1; height: 10px; background: var(--grid); border-radius: 5px; overflow: hidden; }}
.bar-fill {{ height: 100%; background: var(--seq-400); border-radius: 5px; }}
.bar-value {{ width: 24px; text-align: right; font-size: 12.5px; font-variant-numeric: tabular-nums; color: var(--text-primary); }}
@media (max-width: 720px) {{ .stats {{ grid-template-columns: 1fr; }} .two-col {{ grid-template-columns: 1fr; }} .bar-label {{ width: 130px; }} }}
footer {{ margin-top: 56px; font-size: 12px; color: var(--text-muted); border-top: 1px solid var(--border); padding-top: 16px; }}
.viz-tooltip {{
  position: fixed; pointer-events: none; z-index: 1000; opacity: 0;
  background: var(--tooltip-bg); color: var(--tooltip-fg); font-size: 12px;
  padding: 6px 10px; border-radius: 6px; max-width: 260px; line-height: 1.4;
  transition: opacity .08s ease; box-shadow: 0 4px 14px rgba(0,0,0,0.18);
}}
</style></head>
<body>
<header class="hero"><div class="wrap">
  <h1>Financial Data Pipeline — Run Report</h1>
  <div class="meta">Run at {report['run_at_utc']}</div>
  <p class="summary">{summary}</p>

  <div class="stats">
    <div class="stat">
      <div class="n {'warn' if n_passed < n_total else ''}">{n_passed}/{n_total}</div>
      <div class="label">Validation checks passed</div>
    </div>
    <div class="stat">
      <div class="n {'warn' if n_anom else ''}">{n_anom}</div>
      <div class="label">Anomalies flagged</div>
    </div>
    <div class="stat">
      <div class="n">3</div>
      <div class="label">Tables in warehouse</div>
    </div>
  </div>
</div></header>

<div class="wrap">
  <section>
    <h2>Data quality checks</h2>
    <p class="section-note">Every row is a rule the pipeline enforces before data reaches the warehouse. Failures point at real issues in the source data — see docs/DATA_CATALOG.md for what each one means.</p>
    <div class="card">
      <table>
        <tr><th>Table</th><th>Check</th><th>Column</th><th>Result</th><th>Detail</th></tr>
        {validation_rows}
      </table>
    </div>
  </section>

  <section>
    <h2>Market volatility (VIX) — anomaly detection</h2>
    <p class="section-note">Monthly average VIX level, 1990–present. Hover a marker for the exact day and how far it deviated from the trailing pattern.</p>
    <div class="card">
      {vix_svg}
      <div class="legend"><span><span class="swatch" style="background:var(--series-blue)"></span>Monthly average</span><span><span class="swatch" style="background:var(--status-critical); border-radius:50%"></span>Flagged spike day</span></div>
    </div>
    <div class="card" style="margin-top:14px;">
      <table>
        <tr><th>Date</th><th>Close</th><th>Day change</th><th>Z-score</th></tr>
        {vix_rows}
      </table>
    </div>
  </section>

  <section>
    <h2>Company valuation outliers</h2>
    <p class="section-note">Statistical outliers in P/E and price-to-book ratios across S&amp;P 500 constituents. Hover any bar for its range and count.</p>
    <div class="card">
      {pe_svg}
      <div class="legend"><span><span class="swatch" style="background:var(--seq-400)"></span>P/E distribution</span><span><span class="swatch" style="background:var(--status-critical)"></span>Bin containing a flagged outlier</span></div>
    </div>
    <div class="two-col">
      <div class="card">
        <table>
          <tr><th>Symbol</th><th>P/E ratio</th><th>Z-score</th></tr>
          {pe_rows}
        </table>
      </div>
      <div class="card">
        <table>
          <tr><th>Symbol</th><th>Price/Book</th><th>Z-score</th></tr>
          {pb_rows}
        </table>
      </div>
    </div>
  </section>

  <section>
    <h2>Flagged companies by sector</h2>
    <p class="section-note">Which GICS sectors the outlier companies above actually belong to.</p>
    <div class="card">
      {sector_html}
    </div>
  </section>

  <footer>Generated by dashboard/generate_report.py from data/processed/. Re-run <code>python src/pipeline.py</code> to refresh the underlying numbers.</footer>
</div>

<script>
(function () {{
  var tip = document.createElement('div');
  tip.className = 'viz-tooltip';
  document.body.appendChild(tip);
  document.addEventListener('mouseover', function (e) {{
    var el = e.target.closest('[data-tip]');
    if (!el) return;
    tip.textContent = el.getAttribute('data-tip');
    tip.style.opacity = '1';
  }});
  document.addEventListener('mousemove', function (e) {{
    if (tip.style.opacity !== '1') return;
    var x = e.clientX + 14, y = e.clientY + 14;
    if (x + 270 > window.innerWidth) x = e.clientX - 270;
    tip.style.left = x + 'px';
    tip.style.top = y + 'px';
  }});
  document.addEventListener('mouseout', function (e) {{
    var el = e.target.closest('[data-tip]');
    if (!el) return;
    tip.style.opacity = '0';
  }});
}})();
</script>
</body></html>"""
    return html


if __name__ == "__main__":
    out_path = PROCESSED_DIR / "report.html"
    out_path.write_text(build_html())
    print(f"Wrote {out_path}")
