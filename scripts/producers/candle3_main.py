"""
main.py — 3-Candle Confluence Analyzer runner.
Called by cron every 15 minutes.
"""
import sys
import json
import logging
from datetime import datetime, timezone

# sys.path fixed for V2 standalone

from market_data import (
    fetch_candles,
    fetch_indicators_4h,
    get_taker_for_candle,
    get_funding_rate,
)
from candles import compute_three_candle_pattern
from regime import classify_regime
from confluence import (
    confluence_score,
    final_bias,
    compute_range_signal,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("btc-3candle")


def run_pipeline() -> dict:
    """Run the full pipeline. Returns a dict for logging/display."""
    now = datetime.now(timezone.utc)
    is_4h_close = (now.hour % 4 == 0 and now.minute == 0)
    
    # --- Fetch data ---
    logger.info("Fetching market data...")
    df_15m = fetch_candles(timeframe="15m", limit=30, force_fresh=True)
    df_4h = fetch_candles(timeframe="4h", limit=55, force_fresh=True)
    indicators = fetch_indicators_4h()
    funding_rate = get_funding_rate()
    
    price = float(df_15m["close"].iloc[-1])
    
    # --- 15m Pattern ---
    pattern_15m = compute_three_candle_pattern(df_15m, "15m")
    
    # Get taker ratios for 15m (if available — live only)
    taker_15m = [1.0, 1.0, 1.0]
    for i, idx in enumerate([-3, -2, -1]):
        ts = int(df_15m.iloc[idx]["timestamp"])
        taker_15m[i] = get_taker_for_candle(ts, 900)
    
    # --- 4H Pattern ---
    pattern_4h = compute_three_candle_pattern(df_4h, "4H")
    
    # --- Regime ---
    regime = classify_regime(
        df_4h=df_4h,
        rsi=indicators["rsi"],
        macd_hist=indicators["histogram"],
        ma50=indicators["ema50"],
        funding_rate=funding_rate,
        taker_ratio=taker_15m[-1],  # latest available
    )
    
    # --- Confluence + Bias ---
    conf_score = confluence_score(pattern_15m, pattern_4h, regime)
    bias, confidence = final_bias(
        confluence=conf_score,
        pattern_15m_conf=pattern_15m.confidence,
        pattern_4h_conf=pattern_4h.confidence,
        regime_conf=regime.confidence,
    )
    
    support = min(
        pattern_15m.c3.low, pattern_15m.c2.low, pattern_15m.c1.low,
        pattern_4h.c3.low, pattern_4h.c2.low, pattern_4h.c1.low,
    )
    resistance = max(
        pattern_15m.c3.high, pattern_15m.c2.high, pattern_15m.c1.high,
        pattern_4h.c3.high, pattern_4h.c2.high, pattern_4h.c1.high,
    )
    
    range_signal = compute_range_signal(
        bias, confidence, regime.state, support, resistance,
    )
    
    result = {
        "timestamp": now.isoformat(),
        "price": price,
        "4h_close": is_4h_close,
        "15m": {
            "pattern": pattern_15m.pattern_label,
            "confidence": pattern_15m.confidence,
            "candle_types": [pattern_15m.c3.candle_type, pattern_15m.c2.candle_type, pattern_15m.c1.candle_type],
            "dir_score": pattern_15m.dir_score,
            "range_score": pattern_15m.range_score,
            "vol_score": pattern_15m.vol_score,
            "wick_score": pattern_15m.wick_score,
            "volume_trend": pattern_15m.volume_trend,
        },
        "4h": {
            "pattern": pattern_4h.pattern_label,
            "confidence": pattern_4h.confidence,
            "dir_score": pattern_4h.dir_score,
            "range_score": pattern_4h.range_score,
            "vol_score": pattern_4h.vol_score,
            "wick_score": pattern_4h.wick_score,
            "volume_trend": pattern_4h.volume_trend,
        },
        "regime": {
            "state": regime.state,
            "confidence": regime.confidence,
            "rsi": regime.rsi,
            "macd_cross": regime.macd_cross,
        },
        "confluence_score": conf_score,
        "bias": bias,
        "confidence": confidence,
        "support": support,
        "resistance": resistance,
        "range_signal": range_signal,
    }
    
    return result


def main():
    result = run_pipeline()
    
    # Print card to stdout (for cron capture)
    from scripts.card import generate_card
    from candles import Candle as _C
    
    # Reconstruct patterns for card generation
    df_15m = fetch_candles(timeframe="15m", limit=30)
    df_4h = fetch_candles(timeframe="4h", limit=55)
    indicators = fetch_indicators_4h()
    
    pattern_15m = compute_three_candle_pattern(df_15m, "15m")
    pattern_4h = compute_three_candle_pattern(df_4h, "4H")
    
    regime = classify_regime(
        df_4h, indicators["rsi"], indicators["histogram"],
        indicators["ema50"], get_funding_rate(),
    )
    
    card = generate_card(
        price=result["price"],
        pattern_15m=pattern_15m,
        pattern_4h=pattern_4h,
        regime=regime,
        bias=result["bias"],
        confidence=result["confidence"],
        confluence=result["confluence_score"],
        range_signal=result["range_signal"],
        is_4h_close=result["4h_close"],
    )
    
    print(card)
    
    # Log to reads.jsonl
    import os
    log_dir = "/home/maswilee/pipeline-dashboard V2/data"
    os.makedirs(log_dir, exist_ok=True)
    with open(os.path.join(log_dir, "reads.jsonl"), "a") as f:
        f.write(json.dumps(result, default=str) + "\n")
    
    logger.info(f"Run complete: bias={result['bias']}, conf={result['confidence']}%")


if __name__ == "__main__":
    main()
