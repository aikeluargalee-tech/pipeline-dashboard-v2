#!/usr/bin/env python3
"""
Macro snapshot for BTC: DXY, 10Y yield, M2 money supply.
Uses yfinance (free, no key) for DXY and TNX.
For M2: tries FRED API if key present, else uses manual weekly update.
"""

import os
import json
from datetime import datetime

import yfinance as yf

# ---------- CONFIG ----------
FRED_API_KEY = os.environ.get("FRED_API_KEY")  # Optional, free from fred.stlouisfed.org


# ---------- FETCHERS ----------
def get_dxy():
    """DXY index (DX-Y.NYB). Down = bullish for BTC."""
    ticker = yf.Ticker("DX-Y.NYB")
    hist = ticker.history(period="1d")
    if hist.empty:
        return None
    return round(hist["Close"].iloc[-1], 2)


def get_10y_yield():
    """US 10Y Treasury yield (^TNX). Yield down = bullish for BTC."""
    ticker = yf.Ticker("^TNX")
    hist = ticker.history(period="1d")
    if hist.empty:
        return None
    # TNX reports in percentage points (e.g., 4.21 = 4.21%)
    return round(hist["Close"].iloc[-1], 2)


def get_m2():
    """US M2 money supply (billions USD)."""
    if FRED_API_KEY:
        # FRED API free key required, but works real-time
        import requests
        url = (
            f"https://api.stlouisfed.org/fred/series/observations"
            f"?series_id=M2SL&api_key={FRED_API_KEY}"
            f"&sort_order=desc&limit=1&file_type=json"
        )
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            value = float(data["observations"][0]["value"])
            return value  # in billions
    # Fallback: manual update (change weekly)
    # As of May 11, 2026: M2 ~ $21,200B (placeholder)
    return 21200.0


def classify_macro_regime(dxy, yield_10y, m2):
    """Simple rule-based macro sentiment."""
    if dxy is None or yield_10y is None:
        return "unknown"
    # DXY > 105 = strong dollar (bearish), < 100 = weak dollar (bullish)
    # 10Y > 4.5% = restrictive (bearish), < 3.5% = accommodative (bullish)
    if dxy < 100 and yield_10y < 3.5:
        return "bullish"
    elif dxy > 105 and yield_10y > 4.5:
        return "bearish"
    else:
        return "neutral"


def main():
    dxy = get_dxy()
    yield_10y = get_10y_yield()
    m2 = get_m2()
    regime = classify_macro_regime(dxy, yield_10y, m2)

    output = {
        "timestamp": datetime.utcnow().isoformat(),
        "dxy": dxy,
        "us_10y_yield_percent": yield_10y,
        "us_m2_billions": m2,
        "macro_regime": regime,
        "note": "DXY < 100 & yield < 3.5% = bullish; DXY > 105 & yield > 4.5% = bearish."
    }

    with open("/tmp/btc_macro_state.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
