# @purpose: Extract one CSV per chart for EVERY chart across all tabs of
# visaonchainanalytics.com. The site (Next.js + DuckDB-wasm) seeds each chart's
# server-pre-aggregated data as a base64 parquet inside the page HTML and plots it
# directly, so the seed IS the exact plotted data (all filters/aggregation baked in).
# We parse each page's chart specs from the RSC payload, decode the seeded parquets,
# map seed -> chart by in-order column-set signature (aux/raw seeds excluded), and
# write one wide CSV per chart plus an index.html.
#
# No SQL reconstruction, no toggle/filter resolution, no Allium auth — pure ground truth.
# Deps: stdlib + duckdb (parquet read/pivot). Reproducible: re-run to refresh.
import base64, csv, html as htmllib, json, os, re, urllib.request
import duckdb

API = "https://app-server-dp-xjpv5b26pq-uw.a.run.app/api/v1/explorer/results/data"
BASE = "https://visaonchainanalytics.com"
PAGES = ["/", "/addresses", "/insights", "/lending", "/supply", "/transactions"]
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "artifacts")
SEEDDIR = os.path.join(OUT, "_seeds")
con = duckdb.connect(); con.execute("SET TimeZone='UTC'")

# ----- helpers to parse the RSC payload -----
def _match(s, start, oc, cc):
    depth = 0; i = start; instr = False; esc = False; q = ""
    while i < len(s):
        c = s[i]
        if instr:
            if esc: esc = False
            elif c == "\\": esc = True
            elif c == q: instr = False
        else:
            if c in '"\'': instr = True; q = c
            elif c == oc: depth += 1
            elif c == cc:
                depth -= 1
                if depth == 0: return s[start:i+1], i+1
        i += 1
    return None, len(s)

def decode_rsc(page_html):
    out = []
    for m in re.finditer(r"self\.__next_f\.push\(", page_html):
        if m.end() >= len(page_html) or page_html[m.end()] != "[": continue
        arr, _ = _match(page_html, m.end(), "[", "]")
        if not arr: continue
        try: val = json.loads(arr)
        except Exception: continue
        if isinstance(val, list) and len(val) > 1 and isinstance(val[1], str):
            out.append(val[1])
    return "".join(out)

def resolve_group(cfg_groupby, bindings):
    g = cfg_groupby
    if g and "get_adjusted_group_field" in g:
        return "category" if bindings.get("show_categories") else "tag"
    return g

def parse_charts(rsc):
    """Return chart specs in DOM/RSC order."""
    shareids = sorted(set(re.findall(r'"shareId":"([A-Za-z0-9_-]+)"', rsc)))
    shareid = next((x for x in shareids if x), "")
    charts = []
    for m in re.finditer(r'\{"elementId":', rsc):
        obj, _ = _match(rsc, m.start(), "{", "}")
        if not obj: continue
        try: el = json.loads(obj)
        except Exception: continue
        if el.get("type") != "chart": continue
        cfg = el.get("config") or {}
        binds = {b["id"]: b.get("value") for b in (el.get("bindings") or [])}
        x = cfg.get("xAxisSpec") or {}; ys = cfg.get("yAxisSpecs") or []; gb = cfg.get("groupBySpec") or {}
        charts.append({
            "shareId": shareid, "queryId": el.get("queryId"),
            "title": cfg.get("title"), "description": cfg.get("description"),
            "x_field": x.get("field"), "metric": (ys[0].get("field") if ys else None),
            "aggregate": (ys[0].get("aggregate") if ys else None),
            "groupBy": resolve_group(gb.get("field"), binds),
            "appearance": cfg.get("appearance") or {},
        })
    return charts

# ----- seed extraction -----
def extract_seeds(page_html, tag):
    """Return list of {cols, path, pos} for every base64 parquet seed, in appearance order."""
    seeds = []
    for m in re.finditer(r"[A-Za-z0-9+/]{300,}={0,2}", page_html):
        b = m.group(0)
        try: raw = base64.b64decode(b, validate=True)
        except Exception: continue
        if not (raw[:4] == b"PAR1" and raw[-4:] == b"PAR1"): continue
        path = os.path.join(SEEDDIR, f"{tag}_{len(seeds)}.parquet")
        open(path, "wb").write(raw)
        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{path}')").fetchall()]
        seeds.append({"cols": cols, "lc": [c.lower() for c in cols], "path": path, "pos": m.start()})
    return seeds

def server_query(sql):
    req = urllib.request.Request(API + "?format=json", data=json.dumps({"sql": sql}).encode(),
                                 headers={"content-type": "application/json", "accept": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=180))

def rebuild_tag_chart(chart, seed):
    """The 'vs' charts (groupBy=tag) seed only the default-visible tag; the comparison
    tag is fetched on toggle. Rebuild the full both-series view from the base relation
    (monthly SUM, exact for sum metrics), cross-checking the visible tag against the seed."""
    s, q = chart["shareId"], chart["queryId"]; metric = chart["metric"]
    rows = server_query(
        f'SELECT strftime(date_trunc(\'month\',"day"::TIMESTAMP),\'%Y-%m-01\') m, "tag" g, '
        f'SUM("{metric}") v FROM share."{s}"."{q}" GROUP BY 1,2')
    grid = {}; tags_total = {}
    for r in rows:
        grid.setdefault(r["m"], {})[r["g"]] = r["v"]
        tags_total[r["g"]] = tags_total.get(r["g"], 0) + (r["v"] or 0)
    order = sorted(tags_total, key=lambda t: -tags_total[t])
    # guardrail: visible tag (in seed) must match reconstruction within epsilon
    seedvis = {r[0]: r[1] for r in con.execute(
        f'SELECT strftime(day AT TIME ZONE \'UTC\',\'%Y-%m-01\'), SUM("{metric}") '
        f'FROM read_parquet(\'{seed["path"]}\') GROUP BY 1').fetchall()}
    vis_tag = con.execute(f'SELECT DISTINCT tag FROM read_parquet(\'{seed["path"]}\')').fetchone()[0]
    bad = [m for m, v in seedvis.items() if v and abs(v - grid.get(m, {}).get(vis_tag, 0)) / v > 1e-6]
    ok = not bad
    fname = f"{chart['page']}__{slug(chart['title'])}.csv"
    with open(os.path.join(OUT, fname), "w", newline="") as f:
        w = csv.writer(f); w.writerow([chart["x_field"]] + order + ["total"])
        for m in sorted(grid):
            vals = [grid[m].get(t, 0) or 0 for t in order]
            w.writerow([m] + [f"{v:.6f}" for v in vals] + [f"{sum(vals):.6f}"])
    return {"file": fname, "rows": len(grid), "x": chart["x_field"], "group": "tag",
            "metric": metric, "series": order,
            "note": f"both series from base relation (seed default view = '{vis_tag}'); cross-check {'OK' if ok else 'MISMATCH:'+str(bad[:3])}"}

def slug(s):
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:70]

TIME_COLS = {"day", "date"}

def time_col(cols):
    for c in cols:
        if c.lower() in TIME_COLS: return c
    return None

def write_chart_csv(chart, seed, page_name):
    cols = seed["cols"]; lc = seed["lc"]; p = seed["path"]
    metric = chart["metric"]; group = chart["groupBy"]; x = chart["x_field"]
    tcol = time_col(cols)
    # resolve real column names (case-insensitive) from seed
    def real(name):
        if name is None: return None
        for c in cols:
            if c.lower() == name.lower(): return c
        return None
    mcol = real(metric); gcol = real(group); xcol = real(x) or tcol
    fname = f"{page_name}__{slug(chart['title'])}.csv"
    fpath = os.path.join(OUT, fname)
    info = {"file": fname, "rows": 0, "x": xcol, "group": gcol, "metric": mcol, "series": []}

    if tcol:  # time series -> wide: time rows x group cols (+ total)
        xexpr = f"strftime(\"{tcol}\" AT TIME ZONE 'UTC', '%Y-%m-%d')"
        if gcol:
            # order series by total magnitude (legend order)
            order = [r[0] for r in con.execute(
                f'SELECT "{gcol}", SUM("{mcol}") s FROM read_parquet(\'{p}\') GROUP BY 1 ORDER BY 2 DESC NULLS LAST').fetchall()]
            order = [o for o in order if o is not None]
            rows = con.execute(
                f'SELECT {xexpr} t, "{gcol}" g, SUM("{mcol}") v FROM read_parquet(\'{p}\') GROUP BY 1,2').fetchall()
            grid = {}
            for t, g, v in rows: grid.setdefault(t, {})[g] = v
            times = sorted(grid)
            with open(fpath, "w", newline="") as f:
                w = csv.writer(f); w.writerow([xcol] + [str(o) for o in order] + ["total"])
                for t in times:
                    vals = [grid[t].get(o, 0) or 0 for o in order]
                    w.writerow([t] + [f"{v:.6f}" if isinstance(v, float) else v for v in vals]
                               + [f"{sum(vals):.6f}"])
            info.update(rows=len(times), series=[str(o) for o in order])
        else:  # single series
            rows = con.execute(
                f'SELECT {xexpr} t, SUM("{mcol}") v FROM read_parquet(\'{p}\') GROUP BY 1 ORDER BY 1').fetchall()
            with open(fpath, "w", newline="") as f:
                w = csv.writer(f); w.writerow([xcol, metric])
                for t, v in rows: w.writerow([t, f"{v:.6f}" if isinstance(v, float) else v])
            info.update(rows=len(rows), series=[metric])
    else:  # categorical (e.g. txn_size): x rows x group cols
        order = [r[0] for r in con.execute(
            f'SELECT "{gcol}", SUM("{mcol}") s FROM read_parquet(\'{p}\') GROUP BY 1 ORDER BY 1').fetchall()]
        rows = con.execute(
            f'SELECT "{xcol}" xx, "{gcol}" g, SUM("{mcol}") v FROM read_parquet(\'{p}\') GROUP BY 1,2').fetchall()
        grid = {}
        for xx, g, v in rows: grid.setdefault(xx, {})[g] = v
        xs = sorted(grid, key=lambda k: -sum(v or 0 for v in grid[k].values()))
        with open(fpath, "w", newline="") as f:
            w = csv.writer(f); w.writerow([xcol] + [str(o) for o in order] + ["total"])
            for xx in xs:
                vals = [grid[xx].get(o, 0) or 0 for o in order]
                w.writerow([xx] + [f"{v:.6f}" if isinstance(v, float) else v for v in vals] + [f"{sum(vals):.6f}"])
        info.update(rows=len(xs), series=[str(o) for o in order])
    return info

def main():
    os.makedirs(OUT, exist_ok=True); os.makedirs(SEEDDIR, exist_ok=True)
    catalog = []
    for route in PAGES:
        page_name = route.strip("/") or "home"
        req = urllib.request.Request(BASE + route, headers={"user-agent": "Mozilla/5.0"})
        page_html = urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")
        rsc = decode_rsc(page_html)
        charts = parse_charts(rsc)
        seeds = extract_seeds(page_html, page_name)
        used = [False] * len(seeds)
        for ch in charts:
            ch["page"] = page_name
            want = set()
            for nm in (ch["x_field"], ch["groupBy"], ch["metric"]):
                if nm: want.add(nm.lower())
            # greedy in-order: first unused seed whose column set == want
            idx = next((i for i, s in enumerate(seeds)
                        if not used[i] and set(s["lc"]) == want), None)
            if idx is None:  # fallback: superset containing all wanted cols, fewest extras
                cand = [(len(set(s["lc"]) - want), i) for i, s in enumerate(seeds)
                        if not used[i] and want <= set(s["lc"])]
                idx = min(cand)[1] if cand else None
            if idx is None:
                catalog.append({**{k: ch[k] for k in ("title", "queryId", "shareId", "metric", "groupBy", "x_field", "aggregate", "description")},
                                "page": page_name, "file": None, "rows": 0, "series": [], "note": "NO SEED MATCH"})
                continue
            used[idx] = True
            # 'vs' charts (groupBy=tag) seed only the default tag; rebuild both series from base relation
            if ch["groupBy"] == "tag" and ch["aggregate"] == "sum":
                info = rebuild_tag_chart(ch, seeds[idx])
            else:
                info = write_chart_csv(ch, seeds[idx], page_name)
            catalog.append({**{k: ch[k] for k in ("title", "queryId", "shareId", "metric", "groupBy", "x_field", "aggregate", "description")},
                            "page": page_name, **info})
        print(f"{route:14s} charts={len(charts)} seeds={len(seeds)} matched={sum(used)}")
    json.dump(catalog, open(os.path.join(OUT, "charts_manifest.json"), "w"), indent=2)
    write_index(catalog)
    matched = sum(1 for c in catalog if c.get("file"))
    print(f"\nTOTAL charts={len(catalog)} csv_written={matched}")
    miss = [c for c in catalog if not c.get("file")]
    if miss:
        print("UNMATCHED:")
        for c in miss: print("  ", c["page"], c["title"])

def write_index(catalog):
    rows = []
    for c in catalog:
        link = f'<a href="{c["file"]}">{c["file"]}</a>' if c.get("file") else '<span style="color:#b00">— unmatched —</span>'
        series = ", ".join(map(str, c.get("series", [])[:14])) + (" …" if len(c.get("series", [])) > 14 else "")
        rows.append(f"""<tr><td>{htmllib.escape(c['page'])}</td>
          <td><b>{htmllib.escape(c['title'] or '')}</b><br><span class=d>{htmllib.escape(c.get('description') or '')}</span></td>
          <td>{c.get('aggregate') or ''}({htmllib.escape(str(c.get('metric')))})</td>
          <td>{htmllib.escape(str(c.get('groupBy')))}</td>
          <td class=n>{c.get('rows',0)}</td>
          <td class=s>{htmllib.escape(series)}</td>
          <td>{link}</td>
          <td class=q>{htmllib.escape(c.get('shareId',''))}.{htmllib.escape(c.get('queryId',''))}</td></tr>""")
    doc = f"""<!doctype html><meta charset=utf-8><title>VOA charts — CSV export</title>
<style>body{{font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:32px;color:#1a1a2e}}
h1{{font-size:22px}} .sub{{color:#555;margin-bottom:18px}}
table{{border-collapse:collapse;width:100%}} th,td{{border-bottom:1px solid #e3e3ec;padding:7px 10px;vertical-align:top;text-align:left}}
th{{background:#faf7ff;position:sticky;top:0}} .d{{color:#777;font-size:12px}} .n{{text-align:right;font-variant-numeric:tabular-nums}}
.s{{color:#444;font-size:12px;max-width:340px}} .q{{color:#999;font-size:11px;font-family:ui-monospace,monospace}}
tr:hover td{{background:#fcfbff}}</style>
<h1>Visa Onchain Analytics — every chart as CSV</h1>
<div class=sub>{sum(1 for c in catalog if c.get('file'))} charts across {len(set(c['page'] for c in catalog))} tabs.
Data extracted from each chart's seeded parquet (exact plotted values, all filters/aggregation baked in). Source: Allium.</div>
<table><thead><tr><th>Tab</th><th>Chart</th><th>Metric</th><th>Group&nbsp;by</th><th>Rows</th><th>Series</th><th>CSV</th><th>share.query</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>"""
    open(os.path.join(OUT, "index.html"), "w").write(doc)

if __name__ == "__main__":
    main()
