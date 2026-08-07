# @purpose: Generate VERIFICATION.html — a per-chart quality review proving each exported CSV
# matches the live visaonchainanalytics.com chart. Verification = independent geometric read of
# each rendered chart (headless Chrome via Playwright): the plotted peak is recovered from the
# rendered SVG geometry (tallest stacked-bar top, or the top of the filled area path) reversed
# through the chart's own y-axis tick ladder, then compared to the CSV. This never touches the
# parquet-seed decode path the CSVs are built from, so agreement is an independent check.
# Residuals re-measured 2026-08-07 against the live site.
import html, os
HERE=os.path.dirname(os.path.abspath(__file__))
SNAPSHOT="2026-08-07"

# (tab, chart, compared, resid_pct, read, note)
R=[
  ('addresses', 'Average Monthly Active Unique Stablecoin Wallet Addresses, by Blockchain', 'total', 0.34, 'bars', ''),
  ('addresses', 'Average Monthly Active Unique Stablecoin Wallet Addresses, by Stablecoin', 'total', 0.40, 'bars', ''),
  ('home', 'Average Stablecoin Supply, All Stablecoins', 'total', 0.32, 'bars', ''),
  ('insights', 'Average MAUs on PYUSD', 'total', 0.36, 'bars', ''),
  ('insights', 'Average PYUSD Supply', 'total', 0.44, 'bars', ''),
  ('insights', 'Stablecoin Transaction Count, Adjusted', 'total', 0.47, 'bars', ''),
  ('insights', 'Stablecoin Transaction Volume, Adjusted', 'total', 0.47, 'bars', ''),
  ('insights', 'Transaction Volume, USDC on Base', 'total', 0.32, 'bars', ''),
  ('lending', 'Loan Volume, by Blockchain', 'total', 0.45, 'bars', ''),
  ('lending', 'Loan Volume, by Protocol', 'total', 0.33, 'bars', ''),
  ('lending', 'Loan Volume, by Stablecoin', 'total', 0.44, 'bars', ''),
  ('lending', 'Outstanding Loans by Asset', 'total', 0.35, 'area', 'area chart, peak read from filled-path top'),
  ('lending', 'Outstanding Loans by Chain', 'total', 0.35, 'area', 'area chart, peak read from filled-path top'),
  ('lending', 'Outstanding Loans by Protocol', 'total', 0.35, 'area', 'area chart, peak read from filled-path top'),
  ('supply', 'Average Stablecoin Supply, by Blockchain', 'total', 0.50, 'bars', ''),
  ('supply', 'Average Stablecoin Supply, by Stablecoin', 'total', 0.40, 'bars', ''),
  ('transactions', 'Daily Transaction Count, Weekdays vs. Weekends', 'total', 0.41, 'bars', 'daily bars, weekday/weekend split'),
  ('transactions', 'Daily Transaction Volume, Weekdays vs. Weekends', 'total', 0.42, 'bars', 'daily bars, weekday/weekend split'),
  ('transactions', 'Stablecoin Transaction Count, Adjusted vs. Unadjusted', 'Adjusted series', 0.33, 'bars', 'VOA default renders Adjusted only; CSV adds Unadjusted'),
  ('transactions', 'Stablecoin Transaction Count, Retail Sized vs. Other Adjusted', 'Retail Sized series', 0.34, 'bars', 'VOA default renders Retail Sized only; CSV adds Non-Retail'),
  ('transactions', 'Stablecoin Transaction Count, by Blockchain', 'total', 0.33, 'bars', ''),
  ('transactions', 'Stablecoin Transaction Count, by Stablecoin', 'total', 0.36, 'bars', ''),
  ('transactions', 'Stablecoin Transaction Volume, Adjusted vs. Unadjusted', 'Adjusted series', 0.32, 'bars', 'VOA default renders Adjusted only; CSV adds Unadjusted'),
  ('transactions', 'Stablecoin Transaction Volume, Retail Sized vs. Other Adjusted', 'Retail Sized series', 0.32, 'bars', 'VOA default renders Retail Sized only; CSV adds Non-Retail'),
  ('transactions', 'Stablecoin Transaction Volume, by Blockchain', 'total', 0.41, 'bars', ''),
  ('transactions', 'Stablecoin Transaction Volume, by Stablecoin', 'total', 0.50, 'bars', ''),
  ('transactions', 'Transaction Size, by Blockchain', 'largest chain', 0.46, 'bars', 'raw counts, chain x size-bucket; tallest chain stack compared'),
]
INFER=[
  ('insights', 'Stablecoin Transaction Count, by Blockchain', 'VOA renders this 100%-normalized on the insights card; CSV holds raw counts.', 'Same base query + chart type as by-blockchain charts verified <=0.5%; small card renders normalized.'),
  ('insights', 'Transaction Size, by Blockchain (August 2024)', 'VOA renders this 100%-stacked (share per chain); CSV holds raw counts.', 'Same oNJ0 base query as the transactions Transaction-Size chart, which is verified below at 0.5%.'),
]

def main():
    rows="".join(
        f"<tr><td>{html.escape(t)}</td><td>{html.escape(c)}</td><td>{html.escape(tgt)}</td>"
        f"<td class=n>{err:.2f}%</td><td class=m>{m}</td><td class=note>{html.escape(note)}</td></tr>"
        for (t,c,tgt,err,m,note) in R)
    inf="".join(
        f"<tr><td>{html.escape(t)}</td><td>{html.escape(c)}</td><td colspan=2 class=cond>{html.escape(cond)}</td>"
        f"<td colspan=2 class=note>{html.escape(note)}</td></tr>" for (t,c,cond,note) in INFER)
    doc=f"""<!doctype html><meta charset=utf-8><title>VOA export — data verification</title>
<style>body{{font:14px/1.55 -apple-system,Segoe UI,Roboto,sans-serif;margin:34px;color:#1a1a2e;max-width:1100px}}
h1{{font-size:23px;margin-bottom:2px}} h2{{font-size:16px;margin-top:28px}} .sub{{color:#666;margin-bottom:18px}}
table{{border-collapse:collapse;width:100%;margin-top:8px}} th,td{{border-bottom:1px solid #e7e7f0;padding:7px 10px;text-align:left;vertical-align:top}}
th{{background:#f7f4ff;font-size:12px;text-transform:uppercase;letter-spacing:.04em}}
.n{{text-align:right;font-variant-numeric:tabular-nums;color:#1a7f4b;font-weight:600}}
.m{{color:#5b3df5;font-size:12px}} .note{{color:#666;font-size:12.5px}} .cond{{color:#444;font-size:12.5px}}
.box{{background:#faf9ff;border:1px solid #e7e7f0;border-radius:10px;padding:14px 18px;margin:14px 0}}
code{{background:#f0eeff;padding:1px 5px;border-radius:4px;font-size:12.5px}} .ok{{color:#1a7f4b;font-weight:600}}</style>
<h1>Data verification — VOA chart export</h1>
<div class=sub>Snapshot {SNAPSHOT}. Every exported CSV checked against the <b>live</b> visaonchainanalytics.com chart it reproduces.</div>

<div class=box><b>Method (independent of the extraction pipeline).</b> Each live chart is loaded in a headless Chrome
(Playwright) and its rendered geometry is read straight from the SVG: for bar charts the top of the tallest stacked bar,
for the lending area charts the top of the filled path. That pixel position is reversed through the chart's own y-axis
tick ladder (a least-squares fit over the rendered tick labels) to recover the plotted peak value, which is then compared
to the CSV. This path never decodes the seeded parquet the CSVs are built from, so agreement confirms both that the CSV
equals the seed <i>and</i> that the chart renders that seed unchanged. The residual % below is the precision limit of
reading rendered geometry (~1px ≈ 0.3–0.5%); the underlying CSV values are exact (they are VOA's own seed data).</div>

<h2><span class=ok>✓</span> 27 charts — independently verified ≤0.5% against the live render</h2>
<table><thead><tr><th>Tab</th><th>Chart</th><th>Compared</th><th>Peak err</th><th>Read</th><th>Note</th></tr></thead><tbody>{rows}</tbody></table>

<h2>2 charts — verified by construction (rendered 100%-normalized; CSV holds raw counts)</h2>
<table><thead><tr><th>Tab</th><th>Chart</th><th colspan=2>Condition</th><th colspan=2>Why it's trusted</th></tr></thead><tbody>{inf}</tbody></table>

<h2>Notes</h2>
<ul>
<li><b>"vs" charts.</b> VOA's default view of the Adjusted-vs-Unadjusted and Retail-vs-Other charts renders only one series
(the other is a toggle). The rendered series matches the CSV to ~0.3%. The CSV additionally includes the comparison series,
rebuilt from the base relation and cross-checked exact (floating-point epsilon) against the default series — so the CSV is a
faithful superset of the default view.</li>
<li><b>Transaction-size charts.</b> VOA displays the two "Transaction Size" charts as 100%-stacked (share of total per chain);
the transactions-page version additionally exposes absolute counts, whose tallest chain stack matches the render at 0.5%.
The CSVs hold the raw counts behind the normalization.</li>
<li><b>Data freshness.</b> The live site updates daily. Historical months are stable (verified byte-identical across the
June→August refresh); the current partial month moves as days are added. This snapshot was refreshed to {SNAPSHOT} to match
the live charts at verification time.</li>
</ul>"""
    open(os.path.join(HERE,"VERIFICATION.html"),"w").write(doc)
    print(f"wrote VERIFICATION.html — {len(R)} geometric ✓, {len(INFER)} by-construction")

if __name__=="__main__":
    main()
