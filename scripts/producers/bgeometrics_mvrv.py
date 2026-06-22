#!/usr/bin/env python3
"""
Fully automated on-chain metrics for BTC.
- MVRV, MVRV Z-score, SOPR, Puell Multiple: BGeometrics free API (real-time daily)
- Exchange netflow: GitHub crypto-market-data (free, daily updates)
Zero manual updates. Zero API costs.
Writes /tmp/btc_onchain_state.json for btc-market-analysis.
"""

import os
import json
import requests
from datetime import datetime, timezone

# ---- CONFIG ----
BGEOMETRICS_KEY = os.environ.get("BGEOMETRICS_API_KEY")
if not BGEOMETRICS_KEY:
    raise ValueError("Set BGEOMETRICS_API_KEY in ~/.hermes/.env")

BGEOMETRICS_BASE = "https://api.bgeometrics.com/v1"
NETFLOW_URL = (
    "https://raw.githubusercontent.com/ErcinDedeoglu/"
    "crypto-market-data/main/data/daily/btc_exchange_netflow.json"
)


def fetch_bg(endpoint):
    """Fetch from BGeometrics free API."""
    url = f"{BGEOMETRICS_BASE}/{endpoint}?token={BGEOMETRICS_KEY}"
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise ValueError(f"BGeometrics error: {data['error']}")
    return data


def get_mvrv():
    """MVRV ratio (current). <1 undervalued, >2.5 overvalued."""
    return float(fetch_bg("mvrv/1")["mvrv"])


def get_mvrv_zscore():
    """MVRV Z-score. <0 = undervalued, >2 = overvalued."""
    return float(fetch_bg("mvrv-zscore/1")["mvrvZscore"])


def get_sopr():
    """Spent Output Profit Ratio. >1 = selling at profit."""
    return float(fetch_bg("sopr/1")["sopr"])


def get_puell_multiple():
    """Puell Multiple. <0.5 = miner capitulation, >4 = overheated."""
    return float(fetch_bg("puell-multiple/1")["puellMultiple"])


def get_exchange_netflow_7d():
    """
    7-day sum of BTC exchange netflow from GitHub crypto-market-data.
    Positive = inflow (bearish), Negative = outflow (bullish).
    Updated daily. No API key needed.
    """
    try:
        resp = requests.get(NETFLOW_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("data", [])
        if len(entries) < 7:
            return None
        last_7 = [float(e["value"]) for e in entries[-7:]]
        total = sum(last_7)
        latest = last_7[-1] if last_7 else None
        return {
            "sum_7d_btc": round(total, 2),
            "latest_daily_btc": round(latest, 2) if latest else None,
            "source": "GitHub crypto-market-data (free, daily)",
        }
    except Exception as e:
        print(f"Warning: netflow fetch failed: {e}", flush=True)
        return None


def classify_regime(mvrv_z, netflow_data):
    """Classify on-chain regime from MVRV Z-score + 7-day exchange netflow."""
    if mvrv_z is None or netflow_data is None:
        return "unknown"
    netflow_sum = netflow_data.get("sum_7d_btc", 0)
    if mvrv_z < 0.5 and netflow_sum < 0:
        return "accumulation"
    elif mvrv_z > 2.0 and netflow_sum > 0:
        return "distribution"
    elif mvrv_z < 0:
        return "accumulation"
    elif mvrv_z > 2.0:
        return "distribution"
    else:
        return "neutral"


def main():
    errors = []
    mvrv = mvrv_z = sopr = puell = None
    netflow_data = None

    # BGeometrics metrics
    try:
        mvrv = get_mvrv()
        mvrv_z = get_mvrv_zscore()
        sopr = get_sopr()
        puell = get_puell_multiple()
    except Exception as e:
        errors.append(f"BGeometrics: {e}")

    # GitHub netflow
    netflow_data = get_exchange_netflow_7d()

    regime = classify_regime(mvrv_z, netflow_data)

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source_mvrv": "BGeometrics (real-time daily, free)",
        "source_netflow": "GitHub crypto-market-data (free, daily)",
        "source_sopr": "BGeometrics (free)",
        "source_puell": "BGeometrics (free)",
        "mvrv": mvrv,
        "mvrv_z_score": mvrv_z,
        "sopr": sopr,
        "puell_multiple": puell,
        "exchange_netflow_7d_btc": (
            netflow_data["sum_7d_btc"] if netflow_data else None
        ),
        "exchange_netflow_latest_daily_btc": (
            netflow_data["latest_daily_btc"] if netflow_data else None
        ),
        "onchain_regime": regime,
        "errors": errors if errors else None,
        "note": (
            "Fully automated. Zero manual updates. "
            "MVRV Z < 0 = undervalued. Netflow negative = outflow (bullish). "
            "7-day netflow from GitHub, daily updates."
        ),
    }

    with open("/tmp/btc_onchain_state.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
