# test — Morning Oil Brief dashboard prototype

Static HTML dashboard that displays market data from the `MorningOilBrief`
Microsoft Fabric Lakehouse, refreshed on a daily schedule via GitHub Actions
and served with GitHub Pages.

Live: https://tx2modern.github.io/test/

## Status

**Currently running on mock data.** The Entra ID service principal for the
Fabric SQL analytics endpoint hasn't been provisioned yet, so
`scripts/export_lakehouse_data.py` generates sample data matching the real
table schemas instead. The dashboard shows a "Sample data" badge whenever
it's reading mock data. See [handoff.md](#) (original planning doc) for the
full architecture.

## How it works

1. `.github/workflows/refresh-dashboard-data.yml` runs daily (cron, plus
   manual `workflow_dispatch`).
2. It runs `scripts/export_lakehouse_data.py`, which:
   - queries `yf_daily_close` and `yf_futures_curve` from the Fabric SQL
     analytics endpoint if `FABRIC_*` secrets are configured, or
   - generates mock data with the same schema otherwise.
3. Output goes to `data/yf_daily_close.json` and `data/yf_futures_curve.json`.
4. The workflow stages `index.html` + `assets/` + `data/` and deploys them to
   GitHub Pages — no data is committed back to the repo.

## Switching to live Fabric data

Once the Entra ID service principal exists (see manual prerequisites below),
add these as encrypted repo secrets (Settings → Secrets and variables →
Actions) and the next run switches to LIVE mode automatically:

- `FABRIC_SQL_ENDPOINT` — the Lakehouse's SQL analytics endpoint hostname
- `FABRIC_DATABASE` — the Lakehouse database name (e.g. `lh_morningoilbrief`)
- `FABRIC_TENANT_ID`
- `FABRIC_CLIENT_ID`
- `FABRIC_CLIENT_SECRET`

### Manual prerequisites (Azure/Fabric admin access required)

- [ ] Register an Entra ID app / service principal.
- [ ] Grant it Viewer access to the `MorningOilBrief` Fabric workspace (or
      the `lh_morningoilbrief` Lakehouse specifically).
- [ ] Retrieve the SQL analytics endpoint connection string from the
      Lakehouse's Settings in the Fabric UI.
- [ ] Add the five secrets above to this repo.

## Local development

```bash
python3 scripts/export_lakehouse_data.py   # writes data/*.json (mock mode without FABRIC_* env vars)
python3 -m http.server 8000                # serve the repo root
open http://localhost:8000
```
