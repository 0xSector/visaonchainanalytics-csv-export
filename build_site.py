# @purpose: Build the GitHub Pages landing page for this repo: a self-contained HTML viewer
# (all 29 chart datasets embedded -> search + sidebar + inline table preview + per-chart and
# download-all). Writes index.html at the repo root (served by Pages) plus a
# voa-charts-bundle.zip for one-click "download everything". Run after extract_all.py.
import csv, json, os, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")
SNAPSHOT = "2026-06-04"
SITE = "https://visaonchainanalytics.com"

def load():
    manifest = {c["file"]: c for c in json.load(open(os.path.join(ART, "charts_manifest.json")))}
    charts = []
    for fn in sorted(f for f in os.listdir(ART) if f.endswith(".csv")):
        rows = list(csv.reader(open(os.path.join(ART, fn))))
        m = manifest.get(fn, {})
        charts.append({
            "file": fn, "page": m.get("page", fn.split("__")[0]),
            "title": m.get("title", fn), "description": m.get("description", ""),
            "metric": m.get("metric"), "groupBy": m.get("groupBy"), "aggregate": m.get("aggregate"),
            "series": m.get("series", []), "source": f'{m.get("shareId","")}.{m.get("queryId","")}',
            "columns": rows[0], "data": rows[1:],
        })
    order = {p: i for i, p in enumerate(["home", "addresses", "supply", "transactions", "lending", "insights"])}
    charts.sort(key=lambda c: (order.get(c["page"], 9), c["title"]))
    return charts

CSS = """
:root{--ink:#1a1a2e;--muted:#6b6b80;--line:#e6e6f0;--accent:#5b3df5;--bg:#faf9ff}
*{box-sizing:border-box} body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:var(--ink);background:#fff}
header{padding:16px 24px;border-bottom:1px solid var(--line);background:var(--bg);display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap}
header h1{margin:0;font-size:19px} header .sub{color:var(--muted);font-size:13px;margin-top:3px}
header a.all{background:var(--accent);color:#fff;text-decoration:none;border-radius:8px;padding:9px 15px;font-size:13px;white-space:nowrap}
header a.all:hover{opacity:.9}
.wrap{display:flex;height:calc(100vh - 84px)}
aside{width:340px;min-width:300px;border-right:1px solid var(--line);overflow:auto;padding:12px}
#q{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:8px;font-size:13px;margin-bottom:10px}
.tab{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:14px 6px 5px}
.item{padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px}
.item:hover{background:var(--bg)} .item.on{background:#efeaff;color:var(--accent);font-weight:600}
.item .meta{color:var(--muted);font-size:11px;font-weight:400}
main{flex:1;overflow:auto;padding:22px 26px}
.h2{font-size:18px;margin:0 0 2px} .desc{color:var(--muted);margin-bottom:12px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.chip{font-size:12px;background:var(--bg);border:1px solid var(--line);border-radius:20px;padding:3px 11px}
.chip b{color:var(--accent)}
button.dl{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;margin-bottom:14px}
button.dl:hover{opacity:.9}
.tablewrap{border:1px solid var(--line);border-radius:10px;overflow:auto;max-height:64vh}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:6px 11px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:right}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#fff}
thead th{position:sticky;top:0;background:#f4f2ff;z-index:1}
tbody tr:hover td{background:#fcfbff}
.empty{color:var(--muted);padding:40px;text-align:center}
"""

JS = r"""
const CHARTS = JSON.parse(document.getElementById('data').textContent);
const fmt = v => { if(v===''||v==null) return ''; const n=Number(v);
  return (isFinite(n)&&/^-?\d*\.?\d+$/.test(String(v).trim())) ? n.toLocaleString(undefined,{maximumFractionDigits:2}) : v; };
const aside=document.getElementById('list'), main=document.getElementById('main'), q=document.getElementById('q');
let cur=null;
function render(){
  const term=q.value.toLowerCase().trim(), groups={};
  CHARTS.forEach((c,i)=>{ const hay=(c.title+' '+c.page+' '+(c.series||[]).join(' ')+' '+c.metric).toLowerCase();
    if(term&&!hay.includes(term)) return; (groups[c.page]=groups[c.page]||[]).push(i); });
  aside.innerHTML='';
  Object.keys(groups).forEach(pg=>{
    const h=document.createElement('div');h.className='tab';h.textContent=pg;aside.appendChild(h);
    groups[pg].forEach(i=>{const c=CHARTS[i];const d=document.createElement('div');
      d.className='item'+(i===cur?' on':'');d.onclick=()=>show(i);
      d.innerHTML=`${c.title}<div class="meta">${c.data.length} rows · ${(c.series||[]).length} series</div>`;
      aside.appendChild(d);});
  });
  if(!Object.keys(groups).length) aside.innerHTML='<div class="empty">No charts match.</div>';
}
function show(i){cur=i;const c=CHARTS[i];render();
  const chips=[`<span class="chip"><b>${c.aggregate||''}</b> ${c.metric}</span>`,
    c.groupBy?`<span class="chip">group: <b>${c.groupBy}</b></span>`:'',
    `<span class="chip">${c.data.length} rows × ${c.columns.length} cols</span>`,
    `<span class="chip">source: ${c.source}</span>`].join('');
  const thead='<tr>'+c.columns.map(h=>`<th>${h}</th>`).join('')+'</tr>';
  const tbody=c.data.map(r=>'<tr>'+r.map((v,j)=>`<td>${j===0?v:fmt(v)}</td>`).join('')+'</tr>').join('');
  main.innerHTML=`<div class="h2">${c.title}</div><div class="desc">${c.description||''}</div>
    <div class="chips">${chips}</div>
    <button class="dl" onclick="dl(${i})">⤓ Download ${c.file}</button>
    <div class="tablewrap"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`;
}
function dl(i){const c=CHARTS[i];
  const csv=[c.columns.join(',')].concat(c.data.map(r=>r.map(x=>/[,"\n]/.test(x)?'"'+x.replace(/"/g,'""')+'"':x).join(','))).join('\n');
  const b=new Blob([csv],{type:'text/csv'});const a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download=c.file;a.click();}
q.oninput=render; render(); if(CHARTS.length) show(0);
"""

def build_html(charts):
    payload = json.dumps(charts, separators=(",", ":")).replace("</", "<\\/")
    ntabs = len(set(c["page"] for c in charts))
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Visa Onchain Analytics — chart data</title><link rel="icon" href="data:,"><style>{CSS}</style></head><body>
<header><div><h1>Visa Onchain Analytics — every chart as data</h1>
<div class=sub>{len(charts)} charts across {ntabs} tabs · snapshot {SNAPSHOT} · source: <a href="{SITE}">visaonchainanalytics.com</a> (Allium)</div></div>
<a class=all href="voa-charts-bundle.zip" download>⤓ Download all (zip)</a></header>
<div class=wrap><aside><input id=q placeholder="Search charts, metrics, series…" autofocus><div id=list></div></aside>
<main id=main></main></div>
<script type="application/json" id="data">{payload}</script>
<script>{JS}</script></body></html>"""

def main():
    charts = load()
    html = build_html(charts)
    open(os.path.join(HERE, "index.html"), "w").write(html)
    open(os.path.join(HERE, ".nojekyll"), "w").write("")  # serve files as-is, no Jekyll
    # one-click "download all" bundle, served alongside the page
    with zipfile.ZipFile(os.path.join(HERE, "voa-charts-bundle.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for c in charts:
            z.writestr(f"voa-charts/csv/{c['file']}", open(os.path.join(ART, c["file"])).read())
        z.writestr("voa-charts/index.html", html)
    print(f"wrote index.html ({len(html)//1024} KB), .nojekyll, voa-charts-bundle.zip; {len(charts)} charts")

if __name__ == "__main__":
    main()
