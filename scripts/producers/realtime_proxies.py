#!/usr/bin/env python3
"""
Real-time BTC market proxies — fully free, no API keys needed.
Sources: alternative.me (Fear & Greed), blockchain.info/stats (hashrate, n_tx).
"""

import requests
import json
from datetime import datetime


def get_fear_greed():
    """Fear & Greed Index from alternative.me."""
    url = "https://api.alternative.me/fng/?limit=1"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return int(data["data"][0]["value"])


def get_stats():
    """Fetch blockchain.info stats — hashrate, tx count, etc."""
    url = "https://api.blockchain.info/stats"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()


def main():
    fg = get_fear_greed()
    stats = get_stats()

    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "fear_and_greed": fg,
        "fng_classification": get_fng_label(fg),
        "hashrate_hps": stats.get("hash_rate"),
        "transactions_24h": stats.get("n_tx"),
        "btc_sent_24h": stats.get("estimated_btc_sent"),
        "btc_mined_24h_satoshis": stats.get("n_btc_mined"),
        "difficulty": stats.get("difficulty"),
        "market_price_usd": stats.get("market_price_usd"),
        "note": "F&G <= 25 fear, >= 75 greed; n_tx proxies network activity; hashrate uptrend = miner confidence."
    }

    with open("/tmp/btc_realtime_state.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


def get_fng_label(value):
    if value <= 25:
        return "extreme_fear"
    elif value <= 45:
        return "fear"
    elif value <= 55:
        return "neutral"
    elif value <= 75:
        return "greed"
    else:
        return "extreme_greed"


if __name__ == "__main__":
    main()
