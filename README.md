# visaonchainanalytics-csv-export

CSV exports of **every chart** on [visaonchainanalytics.com](https://visaonchainanalytics.com) —
31 charts across all 6 tabs (home, addresses, insights, lending, supply, transactions) —
plus a one-command pipeline to regenerate them.

**🔎 Live, browsable viewer: https://0xsector.github.io/visaonchainanalytics-csv-export/**
**✓ Data verification (each chart vs live VOA): [VERIFICATION.html](https://0xsector.github.io/visaonchainanalytics-csv-export/VERIFICATION.html)**
(search any chart, preview its table, download the CSV — or grab everything as a zip)

> Data is sourced from the public charts on visaonchainanalytics.com (powered by
> [Allium](https://allium.so)). This is an independent export utility; the underlying
> data belongs to its respective owners.

## The data (`artifacts/`)

One CSV per chart, named `<tab>__<chart-title>.csv`, in wide format
(`time` or category rows × one column per series + `total`). Highlights:

| File | What |
|---|---|
| `supply__average_stablecoin_supply_by_stablecoin.csv` | Monthly avg stablecoin supply, by stablecoin (USDT, USDC, …) |
| `supply__average_stablecoin_supply_by_blockchain.csv` | …by blockchain (Ethereum, Tron, Solana, …) |
| `addresses__*` | Monthly active unique wallet addresses, by stablecoin / blockchain |
| `transactions__*` | Stablecoin transfer volume & count, by stablecoin / chain / day-type / adjusted-vs-unadjusted / retail-vs-other |
| `transactions__stablecoin_transaction_volume_adjusted_by_category.csv` | **New** — Adjusted volume split by transfer category (infra, store-of-value, payments, DeFi, …), the site's *Show Categories* toggle |
| `transactions__stablecoin_transaction_count_adjusted_by_category.csv` | **New** — same split for transaction count |
| `lending__*` | Onchain loan volume & outstanding loans, by chain / stablecoin / protocol / asset |
| `insights__*` | Curated insight snapshots (USDC on Base, PYUSD, transaction-size mix, …) |

- **`index.html`** — browsable catalog of all charts → CSV links.
- **`charts_manifest.json`** — per-chart metadata (metric, group-by, series, row counts, source query id).

`artifacts/` always holds the most recent extract. **Every pull is also archived, unchanged, under
`snapshots/<YYYY-MM-DD>/`**, so any number taken from this export can be traced to the exact pull it came from.

## Pull history (`snapshots/`)

VOA revises its own history: later pulls change values for months that were already complete
(for example, June 2025 Adjusted volume was $824B in the 2026-07-08 pull and $204B in the
2026-09-11 pull). So every pull is kept:

- `snapshots/<id>/*.csv` + `charts_manifest.json`: the pull exactly as extracted.
- `snapshots/<id>/revisions.json`: every settled cell that differs from the previous pull
  (`[period, series, old, new, share_of_period_total]`).
- `snapshots/index.json`: one entry per pull (pull time, trigger, checks, and a per-chart
  restatement summary).

A **settled** period is anything before the month the previous pull was taken in (that month
was still partial). A revision is **material** when it moves at least 1% of that period's chart
total, or when periods are dropped. The viewer marks those charts **REVISED**, highlights the
changed cells, and has a picker to view or download any earlier pull.

Pulls from 2026-06-04 to 2026-09-22 were reconstructed from git history (pull date = commit
date). From 2026-09-29 on, each pull is recorded with its exact extraction time.

## Refresh

`.github/workflows/refresh.yml` runs `extract_all.py` → `snapshot.py` → `build_site.py` and
commits the result. It runs:

- **weekly**, Mondays 14:00 UTC;
- from the **↻ Refresh** button on the site, which calls a small Vercel function
  (`refresh-api/`) that starts the workflow at most once an hour;
- from **Run workflow** in the Actions tab.

`snapshot.py` publishes nothing unless the pull passes its checks: every chart matched to its
data, every cross-check exact, no chart missing, no time series ending earlier than the
previous pull, and `extract_all.py` finished (it writes `artifacts/pull_complete.json` last).
If the data equals the latest snapshot (within float noise), nothing is committed.

## How it works

The site is a Next.js SPA + DuckDB-wasm. Each chart's server-pre-aggregated data is
**seeded as a base64 parquet inside the page HTML** and plotted directly — so the seed
*is* the exact plotted data, with all filters / asset-&-chain curation / aggregation
already baked in. `extract_all.py`:

1. fetches each page and decodes the `__next_f` payload to read every chart's spec
   (title, axes, metric + aggregate, group-by);
2. decodes the seeded parquets (`PAR1` magic) and maps each seed → chart by in-order
   column-set match (auxiliary seeds excluded automatically);
3. pivots each seed to a wide CSV and writes `index.html` + `charts_manifest.json`.

No pixel-scraping and no metric reconstruction — the export equals what the charts plot.
The only exception: the two "vs" comparison charts seed only their default-visible series,
so the comparison series is rebuilt from the published query relation (a `SUM`, verified
exact against the seed).

## Run it

```bash
pip install -r requirements.txt   # duckdb
python3 extract_all.py            # writes artifacts/
python3 snapshot.py               # checks + archives the pull to snapshots/ (exit 1 if a check fails)
python3 build_site.py             # rebuilds index.html + the zip from the latest snapshot
```

Raw per-element parquets are cached under `artifacts/_seeds/` (gitignored). The "vs" charts
and the category split are replayed against the site's public data endpoint
(`app-server.allium.so`).

### Refresh button setup (`refresh-api/`)

One Node function on Vercel, with no dependencies. It needs `GH_TOKEN`: a fine-grained GitHub
token limited to this repository with **Actions: read and write**. Set
`site_config.json → refresh_api` to the deployed `/api/refresh` URL and rebuild the site.
Optional env: `COOLDOWN_MIN` (default 60), `ALLOWED_ORIGINS` (default the Pages origin).

## License

MIT — see [LICENSE](LICENSE). Applies to the code in this repo, not to the exported data.
