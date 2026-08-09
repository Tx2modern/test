# test — Morning Oil Brief dashboard prototype

Static HTML dashboard that displays market data from the `MorningOilBrief`
Microsoft Fabric Lakehouse, refreshed on a daily schedule via GitHub Actions
and served with GitHub Pages.

Live: https://tx2modern.github.io/test/

## Status

The Entra ID service principal (`morning-oil-brief-dashboard`) is registered
and has Viewer access to the `MorningOilBrief` workspace. Authentication is
**certificate-based**, not a client secret — this tenant has a policy
blocking client secret creation, so the service principal authenticates with
a self-signed certificate instead (which Microsoft recommends anyway).

Until the five `FABRIC_*` secrets are all present,
`scripts/export_lakehouse_data.py` generates mock data matching the real
table schemas. The dashboard shows a "Sample data" badge whenever it's
reading mock data. See [handoff.md](#) (original planning doc) for the full
architecture.

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

These five encrypted repo secrets (Settings → Secrets and variables →
Actions) switch the export script to LIVE mode automatically once all are
present:

- `FABRIC_SQL_ENDPOINT` — the Lakehouse's SQL analytics endpoint hostname
- `FABRIC_DATABASE` — the Lakehouse database name (e.g. `lh_morningoilbrief`)
- `FABRIC_TENANT_ID`
- `FABRIC_CLIENT_ID`
- `FABRIC_CLIENT_CERTIFICATE` — a PEM containing both the service
  principal's private key and its certificate (not a client secret — this
  tenant blocks those)

### Rotating the certificate

The self-signed cert (`CN=morning-oil-brief-dashboard`) is valid 2 years from
issuance. To rotate: generate a new one, upload the public half to the app
registration's **Certificates & secrets → Certificates** tab, then update
the `FABRIC_CLIENT_CERTIFICATE` secret with the new combined private
key + certificate PEM.

```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 730 -nodes -subj "/CN=morning-oil-brief-dashboard"
cat key.pem cert.pem > combined.pem
gh secret set FABRIC_CLIENT_CERTIFICATE --repo Tx2modern/test < combined.pem
shred -u key.pem combined.pem   # or `rm` if shred isn't available
```

## Local development

```bash
python3 scripts/export_lakehouse_data.py   # writes data/*.json (mock mode without FABRIC_* env vars)
python3 -m http.server 8000                # serve the repo root
open http://localhost:8000
```
