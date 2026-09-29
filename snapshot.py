# @purpose: Archive every VOA pull as an immutable dated snapshot and flag restatements.
# Run after extract_all.py. Three steps:
#   1. gate    - fail closed (exit 1, nothing archived) on any structural problem: an unmatched
#                chart, a failed cross-check, an empty/non-numeric CSV, a chart that disappeared,
#                or a time series whose latest period went backwards vs the previous snapshot.
#   2. archive - if the CSV set differs from the latest snapshot, copy it + the manifest to
#                snapshots/<YYYY-MM-DD>/ (suffix -2, -3 on same-day repeats). Unchanged -> no-op.
#   3. revise  - diff each chart against the previous snapshot on SETTLED periods only (before
#                the month the previous pull was taken in, since that month was still partial).
#                Any settled value that moved is a restatement by VOA, recorded per cell in
#                snapshots/<id>/revisions.json and summarised in snapshots/index.json.
# The 29 base charts are extracted by identical code in every pipeline version, so a settled
# change is VOA's data changing, not ours. Writes changed=true|false to $GITHUB_OUTPUT.
import argparse, csv, datetime as dt, hashlib, json, os, re, shutil, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ART = os.path.join(HERE, "artifacts")
SNAP = os.path.join(HERE, "snapshots")
INDEX = os.path.join(SNAP, "index.json")
REL_TOL = 1e-6   # relative change below this is float noise, not a revision
MATERIAL = 0.01  # a revision is material when it moves >=1% of that period's chart total
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def read_csv(path):
    with open(path, newline="") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]

def num(v):
    try: return float(v)
    except (TypeError, ValueError): return None

def chart_files(manifest):
    return sorted(c["file"] for c in manifest if c.get("file"))

def content_hash(src, files):
    h = hashlib.sha256()
    for fn in files:
        h.update(fn.encode()); h.update(open(os.path.join(src, fn), "rb").read())
    return h.hexdigest()

def equivalent(dir_a, dir_b, files):
    """Same pull, numerically: same headers, same row keys, every cell within REL_TOL.
    Byte hashes can't be used for this because the SQL-replayed charts (server-side SUM)
    differ in the last float digits between otherwise identical pulls."""
    for fn in files:
        h0, r0 = read_csv(os.path.join(dir_a, fn)); h1, r1 = read_csv(os.path.join(dir_b, fn))
        if h0 != h1 or [r[0] for r in r0] != [r[0] for r in r1]: return False
        for x, y in zip(r0, r1):
            for a, b in zip(x[1:], y[1:]):
                a, b = num(a), num(b)
                if (a is None) != (b is None): return False
                if a is not None and abs(b - a) > REL_TOL * max(abs(a), abs(b)): return False
    return True

def load_index():
    if not os.path.exists(INDEX): return {"snapshots": []}
    return json.load(open(INDEX))

def save_index(idx):
    idx["snapshots"].sort(key=lambda s: s["id"])
    os.makedirs(SNAP, exist_ok=True)
    json.dump(idx, open(INDEX, "w"), indent=1)

def is_time(header, rows):
    return bool(rows) and all(DATE_RE.match(r[0] or "") for r in rows)

# ---------- 1. gate ----------
def gate(src, manifest, prev):
    problems = []
    if not manifest: return ["manifest is empty"]
    for c in manifest:
        if not c.get("file"): problems.append(f"unmatched chart: {c.get('page')} / {c.get('title')}")
        if "MISMATCH" in (c.get("note") or ""): problems.append(f"cross-check failed: {c.get('file')}: {c['note']}")
    for fn in chart_files(manifest):
        p = os.path.join(src, fn)
        if not os.path.exists(p): problems.append(f"missing file: {fn}"); continue
        header, rows = read_csv(p)
        if len(header) < 2 or not rows: problems.append(f"empty csv: {fn}"); continue
        bad = sum(1 for r in rows for v in r[1:] if v != "" and num(v) is None)
        if bad: problems.append(f"{bad} non-numeric cells: {fn}")
    if prev:
        pdir = os.path.join(SNAP, prev["id"])
        now = set(chart_files(manifest))
        for fn in prev["files"]:
            if fn not in now: problems.append(f"chart disappeared since {prev['id']}: {fn}"); continue
            h0, r0 = read_csv(os.path.join(pdir, fn)); h1, r1 = read_csv(os.path.join(src, fn))
            if is_time(h0, r0) and is_time(h1, r1) and max(r[0] for r in r1) < max(r[0] for r in r0):
                problems.append(f"latest period went backwards vs {prev['id']}: {fn}")
    return problems

# ---------- 3. revisions ----------
def diff_chart(old_path, new_path, cutoff):
    """Compare settled periods (key < cutoff) of one chart. Categorical charts (no date key)
    compare every row. Each changed cell is sized as a share of its period's chart total
    (sum of series, old or new, whichever is larger), so a tiny series swinging 500% does not
    read as a restatement but a 2% shift in the headline split does. Returns None when
    nothing settled changed beyond float noise."""
    h0, r0 = read_csv(old_path); h1, r1 = read_csv(new_path)
    timed = is_time(h0, r0) and is_time(h1, r1)
    daily = timed and any(not r[0].endswith("-01") for r in r0 + r1)
    settled = (lambda k: k < cutoff) if timed else (lambda k: True)
    old = {r[0]: r for r in r0 if settled(r[0])}
    new = {r[0]: r for r in r1}
    s0 = [c for c in h0[1:] if c != "total"]; s1 = [c for c in h1[1:] if c != "total"]
    cols = s0 + [c for c in s1 if c not in s0]   # union: a dropped/added series is 0 on the other side
    i0 = {c: h0.index(c) for c in s0}; i1 = {c: h1.index(c) for c in s1}
    def period_total(row, idx): return sum(abs(num(row[j]) or 0.0) for j in idx.values())
    cells = []   # [period, series, old, new, share_of_period_total]
    for k in sorted(old):
        if k not in new: continue
        tot = max(period_total(old[k], i0), period_total(new[k], i1)) or 1.0
        for c in cols:
            a = num(old[k][i0[c]]) if c in i0 else None
            b = num(new[k][i1[c]]) if c in i1 else None
            if a is None and b is None: continue
            a = a or 0.0; b = b or 0.0
            if abs(b - a) > REL_TOL * max(abs(a), abs(b)):
                cells.append([k, c, a, b, abs(b - a) / tot])
    removed = sorted(k for k in old if k not in new)
    if daily and removed:   # rolling-window charts drop their oldest days every pull
        removed = [k for k in removed if k >= min(new)]
    added_hist = sorted(k for k in new if timed and k < cutoff and k not in old
                        and old and min(old) < k < max(old))
    series_removed = [c for c in s0 if c not in s1]
    series_added = [c for c in s1 if c not in s0]
    if not (cells or removed or added_hist or series_removed or series_added):
        return None
    mat = [x for x in cells if x[4] >= MATERIAL]
    mat_periods = sorted({x[0] for x in mat})
    top = sorted(cells, key=lambda x: -x[4])[:3]
    return {
        "kind": "daily" if daily else ("monthly" if timed else "categorical"),
        "cutoff": cutoff if timed else None,
        "compared": len([k for k in old if k in new]),
        "material": bool(mat or removed),
        "material_periods": len(mat_periods),
        "material_cells": len(mat),
        "first_material": mat_periods[0] if mat_periods else None,
        "last_material": mat_periods[-1] if mat_periods else None,
        "minor_cells": len(cells) - len(mat),
        "removed_periods": removed,
        "added_history": added_hist,
        "series_removed": series_removed,
        "series_added": series_added,
        "largest": [{"period": k, "series": c, "old": a, "new": b,
                     "pct": (None if a == 0 else round((b - a) / abs(a) * 100, 2)),
                     "share_pct": round(sh * 100, 2)} for k, c, a, b, sh in top],
        "_cells": [[k, c, a, b, round(sh, 6)] for k, c, a, b, sh in cells],
    }

def month_start(date_str):
    return date_str[:7] + "-01"

# ---------- 2. archive ----------
def next_id(idx, day):
    taken = {s["id"] for s in idx["snapshots"]}
    if day not in taken: return day
    n = 2
    while f"{day}-{n}" in taken: n += 1
    return f"{day}-{n}"

def snapshot(src, pulled_at, trigger, note="", manifest_path=None, dry=False):
    """Gate, archive and diff one pull. Returns (status, entry). status in
    {'archived','unchanged','failed'}."""
    manifest = json.load(open(manifest_path or os.path.join(src, "charts_manifest.json")))
    idx = load_index()
    prev = max(idx["snapshots"], key=lambda s: s["id"]) if idx["snapshots"] else None
    problems = gate(src, manifest, prev)
    if problems:
        return "failed", {"problems": problems}
    files = chart_files(manifest)
    h = content_hash(src, files)
    if prev and set(files) == set(prev["files"]) and equivalent(os.path.join(SNAP, prev["id"]), src, files):
        return "unchanged", {"same_as": prev["id"]}
    sid = next_id(idx, pulled_at[:10])
    revisions = {}
    if prev:
        cutoff = month_start(prev["pulled_at"])
        for fn in files:
            if fn in prev["files"]:
                d = diff_chart(os.path.join(SNAP, prev["id"], fn), os.path.join(src, fn), cutoff)
                if d: revisions[fn] = d
    entry = {
        "id": sid, "pulled_at": pulled_at, "trigger": trigger, "note": note,
        "prev": prev["id"] if prev else None, "charts": len(files), "hash": h,
        "files": files, "checks": "passed",
        "new_charts": sorted(set(files) - set(prev["files"])) if prev else [],
        "revised": {fn: {k: v for k, v in d.items() if k != "_cells"} for fn, d in revisions.items()},
    }
    if dry:
        return "archived", entry
    out = os.path.join(SNAP, sid)
    os.makedirs(out, exist_ok=True)
    for fn in files:
        shutil.copyfile(os.path.join(src, fn), os.path.join(out, fn))
    json.dump(manifest, open(os.path.join(out, "charts_manifest.json"), "w"), indent=2)
    json.dump({"snapshot": sid, "prev": entry["prev"],
               "cutoff": month_start(prev["pulled_at"]) if prev else None,
               "charts": {fn: d["_cells"] for fn, d in revisions.items()}},
              open(os.path.join(out, "revisions.json"), "w"), separators=(",", ":"))
    idx["snapshots"].append(entry)
    save_index(idx)
    return "archived", entry

def summarize(entry, material_only=True):
    lines = []
    for fn, d in entry["revised"].items():
        if material_only and not d["material"]: continue
        bits = []
        if d["material_periods"]:
            l = d["largest"][0]
            pct = f"{l['pct']:+.1f}%" if l["pct"] is not None else "from 0"
            bits.append(f"{d['material_periods']} settled periods materially revised "
                        f"({d['first_material']}..{d['last_material']}; largest {l['period']} {l['series']} "
                        f"{pct} = {l['share_pct']:.1f}% of period total)")
        if d["removed_periods"]:
            bits.append(f"{len(d['removed_periods'])} periods removed ({d['removed_periods'][0]}..{d['removed_periods'][-1]})")
        if d["added_history"]: bits.append(f"{len(d['added_history'])} historical periods added")
        if d["series_removed"]: bits.append(f"series removed: {', '.join(d['series_removed'])}")
        if d["series_added"]: bits.append(f"series added: {', '.join(d['series_added'])}")
        lines.append(f"  {fn}: " + "; ".join(bits))
    return lines

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", default="manual", choices=["manual", "scheduled", "button", "backfill"])
    ap.add_argument("--src", default=ART)
    ap.add_argument("--pulled-at", help="default: finished_at from the extractor's pull_complete.json")
    ap.add_argument("--note", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    done = os.path.join(a.src, "pull_complete.json")
    if not a.pulled_at:
        # extract_all.py deletes this marker when it starts and writes it only after every chart
        # is written, so its absence means the CSVs in src may be a mix of two pulls.
        if not os.path.exists(done):
            sys.exit(f"GATE FAILED - {done} missing: the last extract_all.py run did not finish")
        a.pulled_at = json.load(open(done))["finished_at"]
    status, entry = snapshot(a.src, a.pulled_at, a.trigger, a.note, dry=a.dry_run)
    gh = os.environ.get("GITHUB_OUTPUT")
    if gh:
        with open(gh, "a") as f:
            f.write(f"changed={'true' if status == 'archived' else 'false'}\n")
            if status == "archived": f.write(f"snapshot={entry['id']}\n")
    if status == "failed":
        lines = ["GATE FAILED - nothing archived:"] + ["  " + p for p in entry["problems"]]
    elif status == "unchanged":
        lines = [f"unchanged: same data as snapshot {entry['same_as']} (within float noise); nothing archived"]
    else:
        lines = [f"{'would archive' if a.dry_run else 'archived'} snapshot {entry['id']} "
                 f"({entry['charts']} charts, prev={entry['prev']}, "
                 f"materially revised={sum(1 for d in entry['revised'].values() if d['material'])})"]
        lines += summarize(entry)
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a") as f:
            f.write("### VOA pull\n```\n" + "\n".join(lines) + "\n```\n")
    if status == "failed":
        sys.exit(1)

if __name__ == "__main__":
    main()
