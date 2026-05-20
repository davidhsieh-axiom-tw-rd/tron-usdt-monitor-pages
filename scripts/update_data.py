#!/usr/bin/env python3
"""Fetch TRON USDT transfers from TronGrid API and generate static JSON for GitHub Pages."""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError

ADDRESS = "TPCvYFgNJbi1pTMAghNv7moLkq4kS77jbk"
USDT_CONTRACT = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
TRONGRID_URL = "https://api.trongrid.io"
DATA_DIR = Path(__file__).parent.parent / "data"
TZ_TPE = timezone(timedelta(hours=8))


def fetch_all_transfers():
    url = f"{TRONGRID_URL}/v1/accounts/{ADDRESS}/transactions/trc20?limit=200&contract_address={USDT_CONTRACT}"
    all_transfers = []

    for _ in range(20):
        req = Request(url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())
        except URLError as e:
            print(f"[ERROR] API request failed: {e}", file=sys.stderr)
            break

        if not data.get("success"):
            print(f"[ERROR] API returned error", file=sys.stderr)
            break

        transfers = data.get("data", [])
        if not transfers:
            break

        all_transfers.extend(transfers)
        next_url = data.get("meta", {}).get("links", {}).get("next")
        if not next_url:
            break
        url = next_url

    return all_transfers


def process_transfers(raw_transfers):
    results = []
    for tx in raw_transfers:
        value_raw = tx["value"]
        decimals = tx.get("token_info", {}).get("decimals", 6)
        value_usdt = int(value_raw) / (10 ** decimals)

        if tx["to"].upper() == ADDRESS.upper():
            direction = "IN"
        elif tx["from"].upper() == ADDRESS.upper():
            direction = "OUT"
        else:
            direction = "UNKNOWN"

        ts = tx["block_timestamp"]
        dt = datetime.fromtimestamp(ts / 1000, tz=TZ_TPE)

        results.append({
            "tx_id": tx["transaction_id"],
            "timestamp": ts,
            "datetime": dt.strftime("%Y-%m-%d %H:%M:%S"),
            "date": dt.strftime("%Y-%m-%d"),
            "from": tx["from"],
            "to": tx["to"],
            "value_usdt": value_usdt,
            "direction": direction,
        })

    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results


def generate_daily_summary(transfers):
    daily = {}
    for tx in transfers:
        date = tx["date"]
        if date not in daily:
            daily[date] = {"date": date, "in": 0.0, "out": 0.0, "net": 0.0, "count": 0}
        if tx["direction"] == "IN":
            daily[date]["in"] += tx["value_usdt"]
        else:
            daily[date]["out"] += tx["value_usdt"]
        daily[date]["net"] = daily[date]["in"] - daily[date]["out"]
        daily[date]["count"] += 1

    return sorted(daily.values(), key=lambda x: x["date"])


def generate_stats(transfers):
    if not transfers:
        return {"total_in": 0, "total_out": 0, "net": 0, "total_tx": 0, "first_tx": "N/A", "last_tx": "N/A"}

    total_in = sum(t["value_usdt"] for t in transfers if t["direction"] == "IN")
    total_out = sum(t["value_usdt"] for t in transfers if t["direction"] == "OUT")
    sorted_by_time = sorted(transfers, key=lambda x: x["timestamp"])

    return {
        "total_in": total_in,
        "total_out": total_out,
        "net": total_in - total_out,
        "total_tx": len(transfers),
        "first_tx": sorted_by_time[0]["datetime"][:16] if sorted_by_time else "N/A",
        "last_tx": sorted_by_time[-1]["datetime"][:16] if sorted_by_time else "N/A",
        "updated_at": datetime.now(tz=TZ_TPE).strftime("%Y-%m-%d %H:%M:%S"),
    }


def main():
    print(f"Fetching transfers for {ADDRESS}...")
    raw = fetch_all_transfers()
    print(f"  Fetched {len(raw)} raw transfers")

    transfers = process_transfers(raw)
    print(f"  Processed {len(transfers)} transfers")

    daily = generate_daily_summary(transfers)
    stats = generate_stats(transfers)

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(DATA_DIR / "transfers.json", "w") as f:
        json.dump(transfers, f, ensure_ascii=False)

    with open(DATA_DIR / "daily.json", "w") as f:
        json.dump(daily, f, ensure_ascii=False)

    with open(DATA_DIR / "stats.json", "w") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    print(f"  Stats: IN={stats['total_in']:,.2f} OUT={stats['total_out']:,.2f} NET={stats['net']:,.2f}")
    print(f"  Data written to {DATA_DIR}/")


if __name__ == "__main__":
    main()
