#!/usr/bin/env python3
"""
Risk Monitor — whale activity scanner for BTC risk signals.
Source: GitHub crypto-market-data (whale ratio, free, daily).
Writes /tmp/btc_risk_alerts.json.

For keyword/news monitoring: use the browser-based workflow (see skill).
Programmatic web scraping is blocked by most sources in 2026.
"""

import json
import requests
from datetime import datetime, timezone

WHALE_RATIO_URL = (
    "https://raw.githubusercontent.com/ErcinDedeoglu/"
    "crypto-market-data/main/data/daily/btc_exchange_whale_ratio.json"
)


def fetch_whale_ratio():
    """Fetch latest whale ratio from GitHub."""
    try:
        resp = requests.get(WHALE_RATIO_URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        entries = data.get("data", [])
        if len(entries) < 7:
            return None

        latest_7 = [float(e["value"]) for e in entries[-7:]]
        current = latest_7[-1]
        avg_7d = sum(latest_7) / 7
        trend = "rising" if current > avg_7d else "falling" if current < avg_7d else "flat"

        if current > 0.65:
            signal = "whale_dominant"
        elif current < 0.50:
            signal = "retail_dominant"
        else:
            signal = "balanced"

        return {
            "current_ratio": round(current, 4),
            "avg_7d": round(avg_7d, 4),
            "trend": trend,
            "signal": signal,
            "interpretation": (
                "Whales dominating exchange flows (>65%)"
                if current > 0.65
                else "Retail dominating exchange flows (<50%)"
                if current < 0.50
                else "Balanced whale/retail activity"
            ),
            "source": "GitHub crypto-market-data (free, daily)",
        }
    except Exception as e:
        return {"error": str(e)}


def main():
    whale_data = fetch_whale_ratio()

    alerts = []
    risk_level = "low"

    if whale_data and "error" not in whale_data:
        signal = whale_data.get("signal")
        ratio = whale_data.get("current_ratio", 0)
        trend = whale_data.get("trend", "")

        if signal == "whale_dominant" and trend == "rising":
            alerts.append(
                f"⚠️ Whale ratio {ratio:.2f} and rising — "
                "large players accumulating/distributing"
            )
            risk_level = "elevated"
        elif signal == "whale_dominant":
            alerts.append(f"🟡 Whale ratio elevated ({ratio:.2f}) — monitor closely")
            risk_level = "elevated"
        elif signal == "retail_dominant" and trend == "falling":
            alerts.append(
                f"ℹ️ Retail dominating, whales stepping back ({ratio:.2f})"
            )
        else:
            ratio_str = round(ratio, 2)
            alerts.append(f"✅ Whale activity balanced ({ratio_str})")
    else:
        alerts.append("⚠️ Whale data unavailable")
        risk_level = "unknown"

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "risk_level": risk_level,
        "alerts": alerts,
        "whale": whale_data,
        "note": (
            "Automated whale monitoring. Whale ratio = top 10 exchange inflows "
            "/ total inflows. >0.65 = whales dominant, <0.50 = retail dominant."
        ),
    }

    with open("/tmp/btc_risk_alerts.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))
    # Also print a concise summary
    print(f"\n→ Risk level: {risk_level.upper()}")
    for a in alerts:
        print(f"  {a}")


if __name__ == "__main__":
    main()
