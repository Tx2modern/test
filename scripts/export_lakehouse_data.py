#!/usr/bin/env python3
"""
Exports yf_daily_close and yf_futures_curve from the MorningOilBrief Fabric
Lakehouse SQL analytics endpoint to data/*.json for the static dashboard.

Mode is chosen automatically:
  - LIVE mode  if FABRIC_SQL_ENDPOINT, FABRIC_DATABASE, FABRIC_TENANT_ID,
               FABRIC_CLIENT_ID and FABRIC_CLIENT_CERTIFICATE are all set.
               FABRIC_CLIENT_CERTIFICATE holds a PEM containing both the
               service principal's private key and its certificate (the
               tenant blocks client secrets, so auth is certificate-based).
  - MOCK mode  otherwise. Generates data matching the real table schemas so
               the dashboard can be built and demoed before the Entra ID
               service principal exists (see handoff doc's manual prerequisites).

Once the service principal is registered, set the five FABRIC_* variables as
GitHub Actions secrets and this script switches to LIVE mode with no code
changes.
"""
import datetime
import json
import os
import random
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(REPO_ROOT, "data")

FABRIC_ENV_VARS = [
    "FABRIC_SQL_ENDPOINT",
    "FABRIC_DATABASE",
    "FABRIC_TENANT_ID",
    "FABRIC_CLIENT_ID",
    "FABRIC_CLIENT_CERTIFICATE",
]

DAILY_CLOSE_TICKERS = [
    ("CL=F", "front_month", "WTI front month"),
    ("BZ=F", "front_month", "Brent front month"),
    ("RB=F", "front_month", "RBOB front month"),
    ("HO=F", "front_month", "ULSD front month"),
    ("USO", "curve_proxy", "WTI curve proxy (USO)"),
    ("USL", "curve_proxy", "WTI 12-month curve proxy (USL)"),
    ("FRO", "tanker_crude", "Frontline (crude tankers)"),
    ("INSW", "tanker_crude", "International Seaways (crude tankers)"),
    ("DHT", "tanker_crude", "DHT Holdings (crude tankers)"),
    ("STNG", "tanker_product", "Scorpio Tankers (product tankers)"),
    ("TRMD", "tanker_product", "TORM (product tankers)"),
    ("ASC", "tanker_product", "Ardmore Shipping (product tankers)"),
    ("BWET", "freight", "Breakwave Tanker Shipping ETF"),
]

CURVE_COMMODITIES = [
    ("wti", "WTI Crude (NYMEX)", "$/bbl", "CLH27.NYM", 68.0),
    ("brent", "Brent Crude (ICE)", "$/bbl", "BZH27.NYM", 72.0),
    ("rbob", "RBOB Gasoline (NYMEX)", "$/gal", "RBH27.NYM", 2.05),
    ("ulsd", "ULSD (NYMEX)", "$/gal", "HOH27.NYM", 2.35),
]


def _seeded_random(seed_key):
    return random.Random(seed_key)


def fabric_env_present():
    return all(os.environ.get(v) for v in FABRIC_ENV_VARS)


def fetch_live(table_name):
    """Query a table from the Fabric Lakehouse SQL analytics endpoint."""
    import pyodbc
    from azure.identity import CertificateCredential

    endpoint = os.environ["FABRIC_SQL_ENDPOINT"]
    database = os.environ["FABRIC_DATABASE"]
    tenant_id = os.environ["FABRIC_TENANT_ID"]
    client_id = os.environ["FABRIC_CLIENT_ID"]
    certificate_pem = os.environ["FABRIC_CLIENT_CERTIFICATE"].encode()

    credential = CertificateCredential(
        tenant_id, client_id, certificate_data=certificate_pem
    )
    token = credential.get_token("https://database.windows.net/.default")
    token_bytes = token.token.encode("utf-16-le")
    token_struct = len(token_bytes).to_bytes(4, "little") + token_bytes

    SQL_COPT_SS_ACCESS_TOKEN = 1256
    conn_str = (
        f"Driver={{ODBC Driver 18 for SQL Server}};"
        f"Server={endpoint};Database={database};Encrypt=yes;"
    )
    conn = pyodbc.connect(
        conn_str, attrs_before={SQL_COPT_SS_ACCESS_TOKEN: token_struct}
    )
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table_name}")
    columns = [c[0] for c in cursor.description]
    rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
    conn.close()
    return rows


def generate_mock_daily_close(as_of):
    rows = []
    for ticker, series_group, label in DAILY_CLOSE_TICKERS:
        rng = _seeded_random(f"{ticker}-{as_of.isoformat()[:7]}")
        base = {
            "front_month": 68.0,
            "curve_proxy": 75.0,
            "tanker_crude": 30.0,
            "tanker_product": 40.0,
            "freight": 15.0,
        }[series_group]
        price = base
        for i in range(60, 0, -1):
            price_date = as_of - datetime.timedelta(days=i)
            if price_date.weekday() >= 5:
                continue
            price += rng.uniform(-0.03, 0.03) * price
            rows.append(
                {
                    "ticker": ticker,
                    "series_group": series_group,
                    "label": label,
                    "price_date": price_date.isoformat(),
                    "close": round(price, 2),
                    "ingested_at": datetime.datetime.combine(
                        as_of, datetime.time(6, 0)
                    ).isoformat(),
                }
            )
    return rows


def generate_mock_futures_curve(as_of):
    rows = []
    for commodity, name, units, ticker_prefix, base_price in CURVE_COMMODITIES:
        rng = _seeded_random(f"{commodity}-{as_of.isoformat()[:7]}")
        for tenor in range(1, 13):
            contract_date = as_of.replace(day=1) + datetime.timedelta(days=32 * tenor)
            contract = contract_date.strftime("%Y-%m")
            price = round(base_price * (1 + rng.uniform(-0.03, 0.03) - tenor * 0.002), 4)
            rows.append(
                {
                    "as_of_date": as_of.isoformat(),
                    "commodity": commodity,
                    "name": name,
                    "units": units,
                    "tenor": tenor,
                    "contract": contract,
                    "ticker": f"{ticker_prefix[:3]}{tenor:02d}",
                    "price": price,
                    "price_1d": round(price * (1 + rng.uniform(-0.01, 0.01)), 4),
                    "price_1w": round(price * (1 + rng.uniform(-0.03, 0.03)), 4),
                    "price_1m": round(price * (1 + rng.uniform(-0.06, 0.06)), 4),
                    "price_1y": round(price * (1 + rng.uniform(-0.15, 0.15)), 4),
                    "ingested_at": datetime.datetime.combine(
                        as_of, datetime.time(6, 0)
                    ).isoformat(),
                }
            )
    return rows


def write_json(filename, mode, rows):
    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "mode": mode,
        "row_count": len(rows),
        "rows": rows,
    }
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    print(f"Wrote {len(rows)} rows to {path} ({mode} mode)")


def main():
    as_of = datetime.date.today()

    if fabric_env_present():
        try:
            daily_close = fetch_live("yf_daily_close")
            futures_curve = fetch_live("yf_futures_curve")
            write_json("yf_daily_close.json", "live", daily_close)
            write_json("yf_futures_curve.json", "live", futures_curve)
            return
        except Exception as exc:
            print(f"LIVE fetch failed ({exc}); falling back to MOCK mode", file=sys.stderr)

    print("FABRIC_* secrets not fully configured — generating MOCK data", file=sys.stderr)
    write_json("yf_daily_close.json", "mock", generate_mock_daily_close(as_of))
    write_json("yf_futures_curve.json", "mock", generate_mock_futures_curve(as_of))


if __name__ == "__main__":
    main()
