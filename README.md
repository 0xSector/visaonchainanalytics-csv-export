# visaonchainanalytics-csv-export

CSV exports of **every chart** on [visaonchainanalytics.com](https://visaonchainanalytics.com) —
29 charts across all 6 tabs (home, addresses, insights, lending, supply, transactions) —
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
| `lending__*` | Onchain loan volume & outstanding loans, by chain / stablecoin / protocol / asset |
| `insights__*` | Curated insight snapshots (USDC on Base, PYUSD, transaction-size mix, …) |

- **`index.html`** — browsable catalog of all charts → CSV links.
- **`charts_manifest.json`** — per-chart metadata (metric, group-by, series, row counts, source query id).

Snapshot generated **2026-06-08**. Re-run the pipeline to refresh.

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
```

Raw per-element parquets are cached under `artifacts/_seeds/` (gitignored).

## License

MIT — see [LICENSE](LICENSE). Applies to the code in this repo, not to the exported data.
