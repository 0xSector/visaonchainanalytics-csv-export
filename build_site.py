# @purpose: Build the GitHub Pages landing page for this repo: a self-contained HTML viewer
# (latest pull's chart datasets embedded -> search + sidebar + a stacked-bar chart that mirrors
# the live visaonchainanalytics.com chart + inline table preview + per-chart and download-all),
# plus the pull history: a snapshot picker (older pulls fetched on demand from snapshots/),
# per-chart restatement flags and highlighted revised cells, and a Refresh button wired to the
# refresh-api function (hidden when site_config.json has no refresh_api). Data comes from the
# latest archived snapshot, never straight from artifacts/, so everything shown is archived.
# Writes index.html + voa-charts-bundle.zip. Run after snapshot.py. No external libs.
import csv, json, os, zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")
SNAP = os.path.join(HERE, "snapshots")
SITE = "https://visaonchainanalytics.com"
REPO_URL = "https://github.com/0xSector/visaonchainanalytics-csv-export"

def load_history():
    idx = json.load(open(os.path.join(SNAP, "index.json")))
    snaps = sorted(idx["snapshots"], key=lambda s: s["id"])
    for s in snaps:   # the viewer only needs the summaries
        s.pop("hash", None)
    return snaps

def chart_record(fn, path, m, bonus=False):
    rows = list(csv.reader(open(path)))
    return {
        "file": fn, "page": m.get("page", fn.split("__")[0]),
        "title": m.get("title", fn), "description": m.get("description", ""),
        "metric": m.get("metric"), "groupBy": m.get("groupBy"), "aggregate": m.get("aggregate"),
        "series": m.get("series", []), "source": f'{m.get("shareId","")}.{m.get("queryId","")}',
        "new": fn.endswith("_by_category.csv"), "bonus": bonus,
        "columns": rows[0], "data": rows[1:],
    }

def load(latest):
    sdir = os.path.join(SNAP, latest)
    manifest = json.load(open(os.path.join(sdir, "charts_manifest.json")))
    charts = [chart_record(c["file"], os.path.join(sdir, c["file"]), c) for c in manifest if c.get("file")]
    bpath = os.path.join(ART, "bonus_manifest.json")
    if os.path.exists(bpath):
        for c in json.load(open(bpath)):
            charts.append(chart_record(c["file"], os.path.join(ART, c["file"]), c, bonus=True))
    # every file in the snapshot must be listed in the manifest the viewer is built from
    listed = {c["file"] for c in charts}
    stray = [f for f in os.listdir(sdir) if f.endswith(".csv") and f not in listed]
    assert not stray, f"csv in {sdir} missing from its manifest: {stray}"
    order = {p: i for i, p in enumerate(["home", "addresses", "supply", "transactions", "lending", "insights"])}
    # new (category-toggle) charts float to the top of their tab section
    charts.sort(key=lambda c: (order.get(c["page"], 9), 0 if c["new"] else 1,
                               0 if "volume" in c["file"] else 1, c["title"]))
    return charts

CSS = """
:root{--ink:#1a1a2e;--muted:#6b6b80;--line:#e6e6f0;--accent:#5b3df5;--bg:#faf9ff;--rv:#fff1cc;--rvline:#f0c36d;--rvink:#7a4b00}
*{box-sizing:border-box} body{margin:0;font:14px/1.5 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif;color:var(--ink);background:#fff}
header{padding:14px 24px;border-bottom:1px solid var(--line);background:var(--bg);display:flex;justify-content:space-between;align-items:center;gap:12px 16px;flex-wrap:wrap}
header h1{margin:0;font-size:19px} header .sub{color:var(--muted);font-size:13px;margin-top:3px}
header a.all{background:var(--accent);color:#fff;text-decoration:none;border-radius:8px;padding:9px 15px;font-size:13px;white-space:nowrap}
header a.all:hover{opacity:.9}
.wrap{display:flex;height:calc(100vh - var(--hh,84px))}
aside{width:340px;min-width:300px;border-right:1px solid var(--line);overflow:auto;padding:12px}
#q{width:100%;padding:9px 11px;border:1px solid var(--line);border-radius:8px;font-size:13px;margin-bottom:10px}
.tab{font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:14px 6px 5px}
.item{padding:8px 10px;border-radius:8px;cursor:pointer;font-size:13px}
.item:hover{background:var(--bg)} .item.on{background:#efeaff;color:var(--accent);font-weight:600}
.item.absent{opacity:.45}
.item .meta{color:var(--muted);font-size:11px;font-weight:400}
main{flex:1;overflow:auto;padding:22px 26px}
.h2{font-size:18px;margin:0 0 2px} .desc{color:var(--muted);margin-bottom:12px}
.chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px}
.chip{font-size:12px;background:var(--bg);border:1px solid var(--line);border-radius:20px;padding:3px 11px}
.chip b{color:var(--accent)}
.chartbox{border:1px solid var(--line);border-radius:10px;padding:10px 8px 2px;margin-bottom:8px;background:#fff}
.chart{width:100%;height:auto;display:block} .ax{font-size:10px;fill:#9aa1b5}
.legend{display:flex;flex-wrap:wrap;gap:9px 14px;margin:2px 2px 16px;font-size:12px;color:#555}
.legend .sw{display:inline-flex;align-items:center;gap:5px} .legend .sw i{width:11px;height:11px;border-radius:3px;display:inline-block}
.hint{color:var(--muted);font-size:12px;margin:-2px 0 14px}
button.dl{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:8px 14px;font-size:13px;cursor:pointer;margin-bottom:14px}
button.dl:hover{opacity:.9}
.tablewrap{border:1px solid var(--line);border-radius:10px;overflow:auto;max-height:48vh}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:6px 11px;border-bottom:1px solid var(--line);white-space:nowrap;text-align:right}
th:first-child,td:first-child{text-align:left;position:sticky;left:0;background:#fff}
thead th{position:sticky;top:0;background:#f4f2ff;z-index:1}
tbody tr:hover td{background:#fcfbff}
td.rv{background:var(--rv);box-shadow:inset 0 0 0 1px var(--rvline);color:var(--rvink)} td.rvm{background:#fffaf0}
.empty{color:var(--muted);padding:40px;text-align:center}
.item.isnew{background:#fff5fb} .item.isnew.on{background:#ffe3f1;color:#b0106b}
.newpill,.rvpill{display:inline-block;margin-left:6px;font-size:9px;font-weight:700;letter-spacing:.04em;color:#fff;background:#e6007a;border-radius:5px;padding:1px 5px;vertical-align:middle}
.rvpill{background:#c77700}
.hactions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.callout{display:inline-flex;align-items:center;gap:7px;background:#fff0f7;border:1px solid #f3bcdd;color:#b0106b;border-radius:8px;padding:8px 13px;font-size:13px;cursor:pointer;text-decoration:none;white-space:nowrap}
.callout:hover{background:#ffe3f1} .callout b{font-weight:700}
select#snap{padding:8px 10px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff;color:var(--ink)}
button#refresh{background:#fff;color:var(--accent);border:1px solid var(--accent);border-radius:8px;padding:8px 13px;font-size:13px;cursor:pointer;white-space:nowrap}
button#refresh:disabled{opacity:.5;cursor:default}
#rstatus{font-size:12px;color:var(--muted);max-width:360px}
.notice{padding:8px 24px;font-size:13px;border-bottom:1px solid var(--line)}
.notice.old{background:#eef3ff;color:#23407a} .notice.rv{background:var(--rv);color:var(--rvink)}
.notice a{color:inherit;font-weight:600;cursor:pointer}
details.how{font-size:12px;color:var(--muted);margin-top:4px} details.how summary{cursor:pointer}
details.how div{max-width:760px;margin-top:4px;line-height:1.5}
.hist{border:1px solid var(--line);border-radius:10px;margin:0 0 14px;overflow:hidden}
.hist .hh{background:var(--bg);padding:7px 12px;font-size:12px;font-weight:600;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}
.hist .row{display:flex;gap:12px;padding:6px 12px;border-top:1px solid var(--line);font-size:12.5px;align-items:baseline}
.hist .row.on{background:#f4f2ff} .hist .row .d{font-weight:600;min-width:86px;cursor:pointer;color:var(--accent)}
.hist .row.mat .s{color:var(--rvink)} .hist .row .s{color:#444}
"""

JS = r"""
const CHARTS = JSON.parse(document.getElementById('data').textContent);
const H = JSON.parse(document.getElementById('hist').textContent);
const SNAPS = H.snapshots, LATEST = SNAPS[SNAPS.length-1].id, BYID = Object.fromEntries(SNAPS.map(s=>[s.id,s]));
const ONLINE = location.protocol !== 'file:';
let VIEW = LATEST;
const csvCache = {}, revCache = {};
// palette seeded with USDT-green / USDC-blue so by-stablecoin charts line up with VOA
const PALETTE=['#26a17b','#2775ca','#f0b90b','#7b3fe4','#ff6b6b','#00b8d9','#36b37e','#ff8b00',
 '#6554c0','#e84393','#0984e3','#a3cb38','#fdcb6e','#9b59b6','#1abc9c','#e17055','#74b9ff',
 '#55efc4','#fab1a0','#636e72','#b2bec3','#fd79a8','#00cec9','#ffeaa7'];
const colorOf=i=>PALETTE[i%PALETTE.length];
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const fmt = v => { if(v===''||v==null) return ''; const n=Number(v);
  return (isFinite(n)&&/^-?\d*\.?\d+(e[+-]?\d+)?$/i.test(String(v).trim())) ? n.toLocaleString(undefined,{maximumFractionDigits:2}) : v; };
const short = v => { const a=Math.abs(+v||0);
  if(a>=1e9) return (v/1e9).toFixed(a>=1e10?0:1)+'B'; if(a>=1e6) return (v/1e6).toFixed(0)+'M';
  if(a>=1e3) return (v/1e3).toFixed(0)+'K'; return ''+Math.round(v); };
const big = v => { const a=Math.abs(v); const s=a>=1e12?(a/1e12).toFixed(2)+'T':a>=1e9?(a/1e9).toFixed(1)+'B':a>=1e6?(a/1e6).toFixed(1)+'M':a>=1e3?(a/1e3).toFixed(1)+'K':a.toFixed(2); return (v<0?'-':'')+s; };
const pct = p => p==null ? 'from 0' : (p>0?'+':'')+p.toFixed(1)+'%';
const sleep = ms => new Promise(r=>setTimeout(r,ms));

function parseCSV(t){ const rows=[]; let row=[], f='', q=false;
  for(let i=0;i<t.length;i++){ const c=t[i];
    if(q){ if(c=='"'){ if(t[i+1]=='"'){f+='"';i++;} else q=false; } else f+=c; }
    else if(c=='"') q=true; else if(c==','){ row.push(f); f=''; }
    else if(c=='\n'){ row.push(f.replace(/\r$/,'')); rows.push(row); row=[]; f=''; } else f+=c; }
  if(f!==''||row.length){ row.push(f); rows.push(row); } return rows; }

async function dataFor(c){   // {columns,data} for chart c in the viewed pull, or null if absent
  if(VIEW===LATEST || c.bonus) return c;
  if(!BYID[VIEW].files.includes(c.file)) return null;
  const k=VIEW+'/'+c.file;
  if(!csvCache[k]){ const r=await fetch('snapshots/'+k); if(!r.ok) throw new Error(r.status);
    const rows=parseCSV(await r.text()); csvCache[k]={columns:rows[0],data:rows.slice(1)}; }
  return csvCache[k];
}
async function revsFor(id){
  if(!ONLINE || !BYID[id].prev) return {};
  if(!revCache[id]){ try{ const r=await fetch('snapshots/'+id+'/revisions.json'); revCache[id]=r.ok?(await r.json()).charts:{}; }catch(e){ revCache[id]={}; } }
  return revCache[id];
}
const revised = (id,file) => { const d=BYID[id]?.revised?.[file]; return d && d.material ? d : null; };

function chartSVG(c,d){
  const W=880,H=320,padL=56,padR=10,padT=10,padB=34;
  const series=d.columns.slice(1).filter(s=>s!=='total'), ci=series.map(s=>d.columns.indexOf(s));
  const rows=d.data, n=rows.length;
  if(!n||!series.length) return '<div class="empty">No series to plot.</div>';
  const isTime=/^\d{4}-\d{2}-\d{2}/.test(rows[0][0]);
  const vals=rows.map(r=>ci.map(k=>parseFloat(r[k])||0));
  const tot=vals.map(rv=>rv.reduce((a,b)=>a+Math.max(0,b),0));
  const yMax=Math.max(1,...tot);
  const plotW=W-padL-padR, plotH=H-padT-padB, slot=plotW/Math.max(1,n), bw=Math.max(1,slot*0.86);
  const Y=v=>padT+plotH-(v/yMax)*plotH;
  let bars='';
  vals.forEach((rv,ri)=>{ let cum=0; const x=padL+ri*slot+(slot-bw)/2;
    rv.forEach((v,si)=>{ if(v<=0) return; const y1=Y(cum+v), y0=Y(cum);
      bars+=`<rect x="${x.toFixed(1)}" y="${y1.toFixed(1)}" width="${bw.toFixed(1)}" height="${Math.max(0,y0-y1).toFixed(1)}" fill="${colorOf(si)}"><title>${esc(rows[ri][0])} — ${esc(series[si])}: ${fmt(v)}</title></rect>`;
      cum+=v; }); });
  let grid='';
  for(let t=0;t<=4;t++){ const v=yMax*t/4, yy=Y(v);
    grid+=`<line x1="${padL}" x2="${W-padR}" y1="${yy.toFixed(1)}" y2="${yy.toFixed(1)}" stroke="#eef"/><text x="${padL-6}" y="${(yy+3).toFixed(1)}" text-anchor="end" class="ax">${short(v)}</text>`; }
  let xlab='';
  if(isTime){ let last=''; rows.forEach((r,ri)=>{ const yr=String(r[0]).slice(0,4);
      if(yr!==last){ last=yr; const x=padL+ri*slot+slot/2; xlab+=`<text x="${x.toFixed(1)}" y="${H-10}" text-anchor="middle" class="ax">${yr}</text>`; } }); }
  else{ const step=Math.ceil(n/26); rows.forEach((r,ri)=>{ if(ri%step) return; const x=padL+ri*slot+slot/2;
      xlab+=`<text x="${x.toFixed(1)}" y="${H-11}" text-anchor="end" class="ax" transform="rotate(-35 ${x.toFixed(1)} ${H-11})">${esc(String(r[0]).slice(0,16))}</text>`; }); }
  return `<svg viewBox="0 0 ${W} ${H}" class="chart" preserveAspectRatio="xMidYMid meet">${grid}${bars}${xlab}</svg>`;
}
const legendHTML=d=>d.columns.slice(1).filter(s=>s!=='total').map((s,i)=>`<span class="sw"><i style="background:${colorOf(i)}"></i>${esc(s)}</span>`).join('');

function revLine(d){
  const b=[];
  if(d.material_periods){ const l=d.largest[0];
    b.push(`${d.material_periods} settled period${d.material_periods>1?'s':''} restated (${d.first_material}${d.last_material!==d.first_material?' to '+d.last_material:''}); largest: ${esc(l.period)} ${esc(l.series)} ${big(l.old)} → ${big(l.new)} (${pct(l.pct)}, ${l.share_pct.toFixed(1)}% of that period's total)`); }
  if(d.removed_periods.length) b.push(`${d.removed_periods.length} periods dropped (${d.removed_periods[0]} to ${d.removed_periods[d.removed_periods.length-1]})`);
  if(d.series_removed.length) b.push(`series dropped: ${d.series_removed.map(esc).join(', ')}`);
  if(d.series_added.length) b.push(`series added: ${d.series_added.map(esc).join(', ')}`);
  return b.join(' · ');
}
function historyHTML(c){
  if(c.bonus) return '';
  const rows=SNAPS.filter(s=>s.files.includes(c.file)).slice().reverse().map(s=>{
    const d=s.revised?.[c.file]; let txt, mat=false;
    if(!s.prev) txt='first archived pull';
    else if(!BYID[s.prev].files.includes(c.file)) txt='chart first appears in this pull';
    else if(d && d.material){ txt=revLine(d); mat=true; }
    else if(d) txt='only small changes to settled history (each under 1% of its period total)';
    else txt='settled history unchanged';
    return `<div class="row${s.id===VIEW?' on':''}${mat?' mat':''}"><span class="d" onclick="setView('${s.id}')">${s.id}</span><span class="s">${txt}</span></div>`; }).join('');
  return `<div class="hist"><div class="hh">Pull history for this chart · newest first</div>${rows}</div>`;
}

const aside=document.getElementById('list'), main=document.getElementById('main'), q=document.getElementById('q');
let cur=null;
function render(){
  const term=q.value.toLowerCase().trim(), groups={}, snap=BYID[VIEW];
  CHARTS.forEach((c,i)=>{ const hay=(c.title+' '+c.page+' '+(c.series||[]).join(' ')+' '+c.metric).toLowerCase();
    if(term&&!hay.includes(term)) return; (groups[c.page]=groups[c.page]||[]).push(i); });
  aside.innerHTML='';
  Object.keys(groups).forEach(pg=>{
    const h=document.createElement('div');h.className='tab';h.textContent=pg;aside.appendChild(h);
    groups[pg].forEach(i=>{const c=CHARTS[i];const d=document.createElement('div');
      const absent=!c.bonus && !snap.files.includes(c.file), rv=!c.bonus && revised(VIEW,c.file);
      d.className='item'+(c.new?' isnew':'')+(absent?' absent':'')+(i===cur?' on':'');d.onclick=()=>show(i);
      d.innerHTML=`${esc(c.title)}${c.new?' <span class="newpill">NEW</span>':''}${rv?' <span class="rvpill" title="This pull restated settled history">REVISED</span>':''}<div class="meta">${absent?'not in this pull':(VIEW===LATEST||c.bonus?c.data.length+' rows · '+(c.series||[]).length+' series':'archived pull')}</div>`;
      aside.appendChild(d);});
  });
  if(!Object.keys(groups).length) aside.innerHTML='<div class="empty">No charts match.</div>';
}
async function show(i){ cur=i; const c=CHARTS[i]; render(); const view=VIEW;
  let d; try{ d=await dataFor(c); }catch(e){ main.innerHTML=`<div class="empty">Could not load ${esc(c.file)} from the ${view} pull.</div>`; return; }
  if(cur!==i||VIEW!==view) return;
  const head=`<div class="h2">${esc(c.title)}</div><div class="desc">${esc(c.description||'')}</div>`;
  if(!d){ main.innerHTML=head+`<div class="empty">This chart was not part of the ${view} pull.</div>`+historyHTML(c); return; }
  const revs=(await revsFor(view))[c.file]||[];
  if(cur!==i||VIEW!==view) return;
  const rmap={}; revs.forEach(([k,s,a,b,sh])=>{ rmap[k+'\u0000'+s]={a,b,sh}; });
  const prev=BYID[view].prev;
  const chips=[`<span class="chip"><b>${esc(c.aggregate||'')}</b> ${esc(c.metric)}</span>`,
    c.groupBy?`<span class="chip">group: <b>${esc(c.groupBy)}</b></span>`:'',
    `<span class="chip">${d.data.length} rows × ${d.columns.length} cols</span>`,
    `<span class="chip">source: ${esc(c.source)}</span>`,
    c.bonus?'<span class="chip">bonus analysis · not a VOA pull</span>':`<span class="chip">pull: <b>${view}</b></span>`].join('');
  const thead='<tr>'+d.columns.map(h=>`<th>${esc(h)}</th>`).join('')+'</tr>';
  const tbody=d.data.map(r=>'<tr>'+r.map((v,j)=>{ if(j===0) return `<td>${esc(v)}</td>`;
      const x=rmap[r[0]+'\u0000'+d.columns[j]];
      if(!x) return `<td>${fmt(v)}</td>`;
      const p=x.a?((x.b-x.a)/Math.abs(x.a)*100):null;
      return `<td class="${x.sh>=0.01?'rv':'rvm'}" title="${prev} pull: ${fmt(x.a)} → this pull: ${fmt(x.b)} (${pct(p)}; ${(x.sh*100).toFixed(2)}% of the period total)">${fmt(v)}</td>`; }).join('')+'</tr>').join('');
  const rv=!c.bonus && revised(view,c.file);
  const note=rv?`<div class="notice rv" style="border:1px solid var(--rvline);border-radius:8px;margin-bottom:12px">This pull restated settled history vs the ${prev} pull: ${revLine(rv)}. Restated cells are highlighted in the table; hover one to see the earlier value.</div>`:'';
  const dlname=(view===LATEST||c.bonus)?c.file:view+'__'+c.file;
  main.innerHTML=head+`<div class="chips">${chips}</div>${note}
    <div class="chartbox">${chartSVG(c,d)}</div>
    <div class="legend">${legendHTML(d)}</div>
    <div class="hint">Stacked to mirror the live visaonchainanalytics.com chart (largest series on the bottom). Hover a bar for exact values.</div>
    ${historyHTML(c)}
    <button class="dl" onclick="dl()">⤓ Download ${esc(dlname)}</button>
    <div class="tablewrap"><table><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>`;
  window._dl={d,dlname};
}
function dl(){ const {d,dlname}=window._dl;
  const csv=[d.columns.join(',')].concat(d.data.map(r=>r.map(x=>/[,"\n]/.test(x)?'"'+x.replace(/"/g,'""')+'"':x).join(','))).join('\n');
  const b=new Blob([csv],{type:'text/csv'});const a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download=dlname;a.click();}
function jumpNew(){let i=CHARTS.findIndex(c=>c.new&&/volume/i.test(c.file));
  if(i<0)i=CHARTS.findIndex(c=>c.new); if(i>=0){q.value='';show(i);main.scrollTop=0;}}

// ----- pull history: picker + notices -----
const sel=document.getElementById('snap'), notice=document.getElementById('notice');
sel.innerHTML=SNAPS.slice().reverse().map(s=>`<option value="${s.id}">${s.id===LATEST?'Latest pull · '+s.id:'Pull · '+s.id}</option>`).join('');
if(!ONLINE){ sel.disabled=true; sel.title='Open the live site to browse earlier pulls'; }
sel.onchange=()=>setView(sel.value);
function setView(id){ VIEW=id; sel.value=id; paintNotice(); render(); if(cur!=null) show(cur); main.scrollTop=0; }
function paintNotice(){
  const s=BYID[VIEW], n=Object.values(s.revised||{}).filter(d=>d.material).length;
  const folder=`<a href="${H.repo_url}/tree/main/snapshots/${VIEW}" target="_blank" rel="noopener">browse its files</a>`;
  if(VIEW!==LATEST){ notice.className='notice old';
    notice.innerHTML=`Viewing the ${VIEW} pull (archived${s.trigger==='backfill'?', reconstructed from git history':''}). VOA may have restated some of these values since. ${folder} · <a onclick="setView('${LATEST}')">back to latest</a>`; }
  else if(n){ notice.className='notice rv';
    notice.innerHTML=`The latest pull (${VIEW}) restated settled history in ${n} chart${n>1?'s':''} vs the ${s.prev} pull. They are marked <span class="rvpill">REVISED</span>.`; }
  else { notice.className=''; notice.innerHTML=''; }
  document.documentElement.style.setProperty('--hh',(document.querySelector('header').offsetHeight+notice.offsetHeight)+'px');
}
window.setView=setView; window.jumpNew=jumpNew; window.dl=dl;

// ----- refresh button -----
const btn=document.getElementById('refresh'), st=document.getElementById('rstatus');
const ago=t=>{ const m=Math.round((Date.now()-Date.parse(t))/60000); return m<1?'just now':m<60?m+' min ago':m<2880?Math.round(m/60)+' h ago':Math.round(m/1440)+' days ago'; };
const clock=t=>new Date(t).toLocaleTimeString([], {hour:'numeric',minute:'2-digit'});
async function getStatus(){ const r=await fetch(H.refresh_api,{cache:'no-store'}); if(!r.ok) throw new Error(r.status); return r.json(); }
function paintIdle(s){
  const r=s.last_run; if(!r){ st.textContent=''; return; }
  if(r.status!=='completed'){ st.textContent='A refresh is running now…'; btn.disabled=true; poll(Date.parse(r.created_at)); return; }
  st.textContent=`Last checked ${ago(r.created_at)}${r.conclusion==='success'?'':' (the check failed; nothing was published)'}.`;
  if(Date.now()<Date.parse(s.next_allowed_at)){ btn.disabled=true; btn.title=`Refresh runs at most once an hour. Next available at ${clock(s.next_allowed_at)}.`; }
}
async function poll(t0){
  for(let i=0;i<60;i++){ await sleep(i?10000:4000); let s; try{ s=await getStatus(); }catch(e){ continue; }
    const r=s.last_run; if(!r || Date.parse(r.created_at)<t0-60000) continue;
    if(r.status!=='completed'){ st.textContent='Refresh running (about 2 to 4 minutes)…'; continue; }
    if(r.conclusion!=='success'){ st.innerHTML=`The new pull failed an automated check, so nothing was published. <a href="${r.url}" target="_blank" rel="noopener">Details</a>`; return; }
    const hc=s.head_commit, made=hc && /^data: snapshot /.test(hc.message) && Date.parse(hc.date)>=Date.parse(r.created_at);
    if(!made){ st.textContent=`Checked just now: VOA has nothing new since the ${LATEST} pull.`; return; }
    const id=hc.message.replace('data: snapshot ','').trim(); st.textContent=`New pull ${id} archived. Publishing the site…`;
    for(let j=0;j<30;j++){ try{ const x=await (await fetch('snapshots/index.json?t='+Date.now(),{cache:'no-store'})).json();
        if(x.snapshots.some(s=>s.id===id)){ st.innerHTML=`New pull ${id} is live. <a href="?">Reload</a>`; return; } }catch(e){}
      await sleep(10000); }
    st.innerHTML=`New pull ${id} archived; the site is still publishing. <a href="?">Reload</a> in a minute.`; return; }
  st.textContent='Still running. Check back in a few minutes.';
}
btn.onclick=async()=>{ btn.disabled=true; st.textContent='Starting…'; let r,s;
  try{ r=await fetch(H.refresh_api,{method:'POST'}); s=await r.json(); }catch(e){ st.textContent='Could not reach the refresh service.'; btn.disabled=false; return; }
  if(r.status===429){ st.textContent=`Last refresh was ${ago(s.last_run.created_at)}. Refresh runs at most once an hour; next available at ${clock(s.next_allowed_at)}.`; return; }
  if(r.status===409){ st.textContent='A refresh is already running…'; poll(Date.parse(s.last_run.created_at)); return; }
  if(r.status!==202){ st.textContent='Could not start a refresh.'; btn.disabled=false; return; }
  st.textContent='Refresh started (about 2 to 4 minutes)…'; poll(Date.now()); };
if(!H.refresh_api || !ONLINE){ btn.remove(); } else { getStatus().then(paintIdle).catch(()=>{}); }

q.oninput=render; window.addEventListener('resize',paintNotice); paintNotice(); render(); if(CHARTS.length) show(0);
"""

def build_html(charts, snaps, refresh_api):
    payload = json.dumps(charts, separators=(",", ":")).replace("</", "<\\/")
    hist = json.dumps({"snapshots": snaps, "refresh_api": refresh_api, "repo_url": REPO_URL},
                      separators=(",", ":")).replace("</", "<\\/")
    latest = snaps[-1]["id"]
    ntabs = len(set(c["page"] for c in charts))
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>Visa Onchain Analytics — chart data</title><link rel="icon" href="data:,"><style>{CSS}</style></head><body>
<header><div><h1>Visa Onchain Analytics — every chart as data</h1>
<div class=sub>{len(charts)} charts across {ntabs} tabs · latest pull {latest} · {len(snaps)} pulls archived since {snaps[0]['id']} · source: <a href="{SITE}">visaonchainanalytics.com</a> (Allium) · <a href="VERIFICATION.html">method verification</a></div>
<details class=how><summary>How the pull history works</summary><div>
Every refresh pulls all charts from visaonchainanalytics.com and archives them unchanged under
<a href="{REPO_URL}/tree/main/snapshots">snapshots/&lt;date&gt;/</a>. A pull is published only if automated checks pass: every chart
matched, every cross-check exact, no chart missing, no series ending earlier than before. VOA revises its own history, so each pull is compared with the one before it on
<b>settled</b> periods (anything before the month the previous pull was taken in, which was still partial).
A change is flagged <span class="rvpill">REVISED</span> when it moves at least 1% of that period's chart total, or when periods are dropped.
Pulls before 2026-09-29 were reconstructed from git history, so their dates are commit dates.
Refreshes run weekly (Mondays) and on demand, at most once an hour.</div></details></div>
<div class=hactions><a class=callout onclick="jumpNew()" title="Jump to the new category breakdown">🆕 New: <b>adjusted volume &amp; count, by category</b></a>
<select id=snap aria-label="Pull to view"></select>
<button id=refresh title="Pull the latest data from visaonchainanalytics.com now">↻ Refresh</button>
<a class=all href="voa-charts-bundle.zip" download>⤓ Download all (zip)</a>
<div id=rstatus aria-live=polite></div></div></header>
<div id=notice></div>
<div class=wrap><aside><input id=q placeholder="Search charts, metrics, series…" autofocus><div id=list></div></aside>
<main id=main></main></div>
<script type="application/json" id="data">{payload}</script>
<script type="application/json" id="hist">{hist}</script>
<script>{JS}</script></body></html>"""

def main():
    snaps = load_history()
    latest = snaps[-1]["id"]
    charts = load(latest)
    cfg_path = os.path.join(HERE, "site_config.json")
    cfg = json.load(open(cfg_path)) if os.path.exists(cfg_path) else {}
    html = build_html(charts, snaps, cfg.get("refresh_api", ""))
    open(os.path.join(HERE, "index.html"), "w").write(html)
    open(os.path.join(HERE, ".nojekyll"), "w").write("")
    with zipfile.ZipFile(os.path.join(HERE, "voa-charts-bundle.zip"), "w", zipfile.ZIP_DEFLATED) as z:
        for c in charts:
            src = os.path.join(ART if c["bonus"] else os.path.join(SNAP, latest), c["file"])
            z.writestr(f"voa-charts/csv/{c['file']}", open(src).read())
        z.writestr("voa-charts/index.html", html)
    print(f"wrote index.html ({len(html)//1024} KB), .nojekyll, voa-charts-bundle.zip; "
          f"{len(charts)} charts from snapshot {latest}; {len(snaps)} snapshots in history")

if __name__ == "__main__":
    main()
