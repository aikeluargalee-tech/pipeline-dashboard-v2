#!/usr/bin/env python3
"""Market Cycle Metrics — pulls composite cycle indicators for the dashboard.

Fetches from public API. Writes /tmp/btc_cycle_state.json.
"""

import json
import sys
from datetime import datetime, timezone
from urllib.request import urlopen, Request

OUTPUT = "/tmp/btc_cycle_state.json"
DATA_URL = "https://colintalkscrypto.com/cbbi/data/latest.json"
USER_AGENT = "Mozilla/5.0 BTC Dashboard/1.0"

UTC = timezone.utc

# Human-friendly labels and descriptions for each metric
METRIC_META = {
    "PiCycle": {
        "label": "Pi Cycle Top",
        "desc": "111DMA vs 350DMA(×2) crossover — historically signals cycle tops when it crosses",
        "green_below": 40,
        "red_above": 80,
    },
    "RUPL": {
        "label": "NUPL",
        "desc": "Net Unrealized Profit/Loss — measures whether market is in profit or loss overall",
        "green_below": 30,
        "red_above": 70,
    },
    "RHODL": {
        "label": "RHODL Ratio",
        "desc": "Realized HODL Ratio — compares young coins (6m-2y) vs old coins (7y+)",
        "green_below": 40,
        "red_above": 70,
    },
    "Puell": {
        "label": "Puell Multiple",
        "desc": "Miner revenue vs 365DMA — <0.5 capitulation, >4 overheated",
        "green_below": 30,
        "red_above": 70,
    },
    "2YMA": {
        "label": "2-Year MA",
        "desc": "BTC price vs 2-year moving average — above = bullish, below = bearish",
        "green_below": 40,
        "red_above": 80,
    },
    "Trolololo": {
        "label": "Log Trend Line",
        "desc": "Long-term logarithmic trend line — price relative to historical regression",
        "green_below": 40,
        "red_above": 80,
    },
    "MVRV": {
        "label": "MVRV Z-Score",
        "desc": "Market Value to Realized Value Z-score — <0 undervalued, >2 overvalued",
        "green_below": 30,
        "red_above": 70,
    },
    "ReserveRisk": {
        "label": "Reserve Risk",
        "desc": "Long-term holder confidence vs price — low = high confidence (buy zone)",
        "green_below": 40,
        "red_above": 70,
    },
    "Woobull": {
        "label": "Woobull Cycles",
        "desc": "Top Cap vs CVDD — upper and lower bounds of market cycles",
        "green_below": 30,
        "red_above": 70,
    },
}


def classify_pct(pct):
    """Classify a percentage value as low/medium/high."""
    if pct < 25:
        return "low"
    elif pct > 75:
        return "high"
    return "medium"


def main():
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== Market Cycle Pipeline {now} ===")

    try:
        req = Request(DATA_URL, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=30) as f:
            raw = json.load(f)
    except Exception as e:
        print(f"  ⚠️ Failed to fetch data: {e}", file=sys.stderr)
        fallback = {"timestamp": now, "error": str(e)}
        with open(OUTPUT, "w") as f:
            json.dump(fallback, f)
        return False

    # Extract latest values from each time series
    skip_keys = {"Price", "Confidence"}
    metrics = {}
    for key, series in raw.items():
        if key in skip_keys or not isinstance(series, dict):
            continue
        timestamps = sorted(series.keys())
        if timestamps:
            latest_ts = timestamps[-1]
            raw_val = series[latest_ts]
            pct = round(raw_val * 100, 1)
            meta = METRIC_META.get(key, {})
            metrics[key] = {
                "pct": pct,
                "raw": raw_val,
                "label": meta.get("label", key),
                "desc": meta.get("desc", ""),
                "class": classify_pct(pct),
            }

    # Compute overall composite (average of all 9 metrics)
    vals = [m["pct"] for m in metrics.values()]
    composite = round(sum(vals) / len(vals), 1) if vals else None
    composite_class = classify_pct(composite) if composite else "medium"

    state = {
        "timestamp": now,
        "composite": composite,
        "composite_class": composite_class,
        "metrics": metrics,
        "metric_count": len(metrics),
    }

    with open(OUTPUT, "w") as f:
        json.dump(state, f, indent=2)

    print(f"  📊 Composite: {composite}% ({composite_class})")
    print(f"  📈 {len(metrics)} metrics loaded")
    for k, m in sorted(metrics.items()):
        print(f"     {m['label']:20s} {m['pct']:5.1f}%  ({m['class']})")
    print(f"  ✅ Written to {OUTPUT}")
    return True


if __name__ == "__main__":
    main()
