#!/usr/bin/env python3
"""Fetch MA50/MA200, BBW, ATR%, Funding Rate, Taker Ratio, OI Delta for BTC dashboard."""
import json
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc

def fetch_market_data():
    try:
        import ccxt
    except ImportError:
        return {"error": "ccxt not available"}

    result = {
        "timestamp": datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC"),
        "error": None
    }
    exchange = ccxt.binanceusdm()

    try:
        # ── OHLCV for MAs, BB, ATR ──
        ohlcv = exchange.fetch_ohlcv('BTC/USDT', '1h', limit=250)
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        current_price = closes[-1]
        result["current_price"] = current_price

        # MA50
        if len(closes) >= 50:
            ma50 = sum(closes[-50:]) / 50
            result["ma50"] = round(ma50, 2)
            result["above_ma50"] = current_price > ma50
        else:
            result["ma50"] = None

        # MA200
        if len(closes) >= 200:
            ma200 = sum(closes[-200:]) / 200
            result["ma200"] = round(ma200, 2)
            result["above_ma200"] = current_price > ma200
        else:
            result["ma200"] = None

        # Regime from MAs
        above_both = result.get("above_ma50") and result.get("above_ma200")
        below_both = not result.get("above_ma50") and not result.get("above_ma200")
        if above_both:
            result["ma_regime"] = "bullish"
        elif below_both:
            result["ma_regime"] = "bearish"
        else:
            result["ma_regime"] = "mixed"

        # BBW (20,2)
        if len(closes) >= 20:
            sma20 = sum(closes[-20:]) / 20
            variance = sum((c - sma20) ** 2 for c in closes[-20:]) / 20
            std20 = variance ** 0.5
            bb_upper = sma20 + 2 * std20
            bb_lower = sma20 - 2 * std20
            bbw = (bb_upper - bb_lower) / sma20 if sma20 else None
            result["bbw"] = round(bbw, 4) if bbw else None
            result["bbw_label"] = "compressed" if (bbw and bbw < 0.02) else "normal" if (bbw and bbw < 0.06) else "expanded"

            # BB lower band touch check
            in_lower_band = current_price <= bb_lower * 1.01  # within 1% of lower band
            in_upper_band = current_price >= bb_upper * 0.99  # within 1% of upper band
            if in_lower_band:
                result["bb_position"] = "lower_band"
            elif in_upper_band:
                result["bb_position"] = "upper_band"
            else:
                result["bb_position"] = "mid"

        # ATR(14) %
        if len(highs) >= 15:
            tr_values = []
            for i in range(1, 15):
                tr = max(
                    highs[-i] - lows[-i],
                    abs(highs[-i] - closes[-i-1]),
                    abs(lows[-i] - closes[-i-1])
                )
                tr_values.append(tr)
            atr14 = sum(tr_values) / 14
            atr_pct = (atr14 / current_price * 100) if current_price else None
            result["atr_pct"] = round(atr_pct, 2) if atr_pct else None
            result["atr_label"] = "low" if (atr_pct and atr_pct < 0.5) else "moderate" if (atr_pct and atr_pct < 1.5) else "high"
    except Exception as e:
        result["ohlcv_error"] = str(e)

    try:
        # ── Funding Rate ──
        mark = exchange.fetch_mark_price('BTC/USDT')
        funding_rate = mark.get('lastFundingRate', mark.get('info', {}).get('lastFundingRate', 0))
        if isinstance(funding_rate, str):
            funding_rate = float(funding_rate)
        result["funding_rate"] = round(funding_rate * 100, 4)  # as percentage

        # Funding classification
        if result["funding_rate"] < -0.01:
            result["funding_label"] = "negative"
        elif result["funding_rate"] > 0.01:
            result["funding_label"] = "positive"
        else:
            result["funding_label"] = "neutral"
    except Exception as e:
        result["funding_error"] = str(e)

    try:
        # ── Taker Buy/Sell Ratio ──
        import requests
        r = requests.get("https://fapi.binance.com/futures/data/takerlongshortRatio",
                         params={"symbol": "BTCUSDT", "period": "1h", "limit": 24},
                         timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data:
                latest = data[-1]
                buy_vol = float(latest.get('buyVol', 0))
                sell_vol = float(latest.get('sellVol', 0))
                total = buy_vol + sell_vol
                taker_ratio = buy_vol / total if total > 0 else 0.5
                result["taker_buy_ratio"] = round(taker_ratio, 4)

                # Compute 24h average
                ratios_24h = []
                for d in data:
                    bv = float(d.get('buyVol', 0))
                    sv = float(d.get('sellVol', 0))
                    t = bv + sv
                    if t > 0:
                        ratios_24h.append(bv / t)
                result["taker_24h_avg"] = round(sum(ratios_24h) / len(ratios_24h), 4) if ratios_24h else None

                # Taker direction
                if taker_ratio > 0.52:
                    result["taker_label"] = "aggressive_buying"
                elif taker_ratio < 0.48:
                    result["taker_label"] = "aggressive_selling"
                else:
                    result["taker_label"] = "balanced"

        # Fall back to CCXT ticker
        if not result.get("taker_buy_ratio"):
            ticker = exchange.fetch_ticker('BTC/USDT')
            if ticker.get('baseVolume') and ticker.get('quoteVolume'):
                # Approximate: vwap * baseVolume ≈ buy side
                vwap = ticker.get('vwap')
        _ = r  # noqa
    except Exception as e:
        result["taker_error"] = str(e)

    try:
        # ── OI Delta (4h) ──
        oi_hist = exchange.fetch_open_interest_history('BTC/USDT', '1h', limit=8)
        if oi_hist and len(oi_hist) >= 2:
            # Parse OI history - some entries are lists, some are dicts
            oi_values = []
            for entry in oi_hist:
                if isinstance(entry, dict):
                    val = entry.get('openInterestValue', 0) or 0
                elif isinstance(entry, list):
                    val = entry[4] if len(entry) > 4 else 0
                else:
                    val = 0
                oi_values.append(float(val))

            current_oi = oi_values[-1]
            prev_oi = oi_values[0]  # ~4h ago (limit=8, 1h bars)
            oi_delta_pct = ((current_oi - prev_oi) / prev_oi * 100) if prev_oi else None
            result["oi_current"] = round(current_oi, 2)
            result["oi_prev"] = round(prev_oi, 2)
            result["oi_delta_pct"] = round(oi_delta_pct, 2) if oi_delta_pct else None

            # OI delta direction
            if oi_delta_pct and oi_delta_pct > 2:
                result["oi_label"] = "rising"
            elif oi_delta_pct and oi_delta_pct < -2:
                result["oi_label"] = "falling"
            else:
                result["oi_label"] = "flat"
    except Exception as e:
        result["oi_error"] = str(e)

    try:
        # ── Coinbase Premium Index ──
        import ccxt
        cb = ccxt.coinbase()
        bn = ccxt.binance()
        cb_ticker = cb.fetch_ticker('BTC/USD')
        bn_ticker = bn.fetch_ticker('BTC/USDT')
        cb_price = cb_ticker['last']
        bn_price = bn_ticker['last']
        coinbase_premium = (cb_price - bn_price) / bn_price * 100
        result["coinbase_premium"] = round(coinbase_premium, 4)
        result["cb_label"] = "US institutional demand" if coinbase_premium > 0.01 else "US demand soft" if coinbase_premium < -0.01 else "neutral"
    except Exception as e:
        result["cb_error"] = str(e)

    try:
        # ── Perp vs Spot Premium ──
        perp = ccxt.binanceusdm()
        spot = ccxt.binance()
        perp_ticker = perp.fetch_ticker('BTC/USDT')
        spot_ticker = spot.fetch_ticker('BTC/USDT')
        perp_premium = (perp_ticker['last'] - spot_ticker['last']) / spot_ticker['last'] * 100
        result["perp_premium"] = round(perp_premium, 4)
        result["perp_label"] = "aggressive_longs" if perp_premium > 0 else "risk_off" if perp_premium < 0 else "neutral"
    except Exception as e:
        result["perp_error"] = str(e)

    return result


if __name__ == "__main__":
    data = fetch_market_data()
    output_path = "/tmp/btc_market_state.json"
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Market data written to {output_path}")
    if data.get("error"):
        print(f"   ⚠️ {data['error']}")
    for k in ["ma50", "ma200", "bbw", "atr_pct", "funding_rate", "taker_buy_ratio", "oi_delta_pct"]:
        if k in data:
            print(f"   {k}: {data[k]}")
    sys.exit(0 if not data.get("error") else 1)
