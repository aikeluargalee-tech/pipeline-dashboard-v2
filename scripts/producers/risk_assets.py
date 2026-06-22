#!/usr/bin/env python3
"""
Macro Risk Dashboard — risk assets context for BTC analysis.
Fully free: yfinance, no API keys needed.
Writes /tmp/btc_risk_state.json.

Tickers:
  SPY  — S&P 500 (broad US equities)
  QQQ  — Nasdaq-100 (tech-heavy)
  IWM  — Russell 2000 (small caps, risk appetite proxy)
  GLD  — Gold ETF (safe haven, inverse BTC correlation at extremes)
  ^VIX — CBOE Volatility Index (fear gauge, >30 = stress)
"""

import json
import yfinance as yf
from datetime import datetime, timezone

TICKERS = {
    "SPY":  "S&P 500",
    "QQQ":  "Nasdaq-100",
    "IWM":  "Russell 2000",
    "GLD":  "Gold ETF",
    "^VIX": "VIX (Fear Index)",
}

THRESHOLDS = {
    "VIX_high": 30,    # Above = market stress
    "VIX_med":  20,    # Above = elevated caution
    "GLD_spike": 2.0,  # % daily gain signalling risk-off rush
}


def classify_risk(assets):
    """Simple risk classification from VIX + equity direction + gold."""
    vix = assets.get("^VIX", {}).get("close")
    spy_chg = assets.get("SPY", {}).get("change_pct")
    gld_chg = assets.get("GLD", {}).get("change_pct")

    if vix is None:
        return "unknown"

    signals = []

    # VIX-based stress levels
    if vix > THRESHOLDS["VIX_high"]:
        signals.append("high_stress")
    elif vix > THRESHOLDS["VIX_med"]:
        signals.append("elevated")

    # Risk-on: equities up, gold flat/down
    if spy_chg is not None and spy_chg > 0.5 and (gld_chg is None or gld_chg < 0.5):
        signals.append("risk_on")

    # Risk-off: equities down, gold up
    if spy_chg is not None and spy_chg < -0.5 and gld_chg is not None and gld_chg > 1.0:
        signals.append("risk_off")

    if "high_stress" in signals:
        return "risk_off"
    elif "risk_on" in signals and "risk_off" not in signals:
        return "risk_on"
    elif "risk_off" in signals:
        return "risk_off"
    elif "elevated" in signals:
        return "caution"
    else:
        return "neutral"


def main():
    assets = {}
    errors = []

    for symbol, name in TICKERS.items():
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="5d")
            if hist.empty:
                errors.append(f"{symbol}: no data")
                continue
            close = round(float(hist["Close"].iloc[-1]), 2)
            open_p = round(float(hist["Open"].iloc[0]), 2)
            change_pct = round(((close - open_p) / open_p) * 100, 2) if open_p else None
            low = round(float(hist["Low"].iloc[-1]), 2)
            high = round(float(hist["High"].iloc[-1]), 2)

            assets[symbol] = {
                "name": name,
                "close": close,
                "open": open_p,
                "high": high,
                "low": low,
                "change_pct": change_pct,
            }
        except Exception as e:
            errors.append(f"{symbol}: {e}")

    risk_regime = classify_risk(assets)

    vix_val = assets.get("^VIX", {}).get("close")

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "yfinance (free, real-time)",
        "risk_regime": risk_regime,
        "vix": vix_val,
        "vix_interpretation": (
            "extreme fear" if vix_val and vix_val > 30 else
            "elevated caution" if vix_val and vix_val > 20 else
            "normal" if vix_val else "unknown"
        ),
        "assets": assets,
        "errors": errors if errors else None,
        "note": (
            "VIX > 30 = stress. Gold spiking + equities falling = risk-off. "
            "BTC often correlates with QQQ in risk-on, decouples in extreme risk-off."
        ),
    }

    with open("/tmp/btc_risk_state.json", "w") as f:
        json.dump(output, f, indent=2)

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
