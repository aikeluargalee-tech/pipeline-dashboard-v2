"""
regime.py — Market regime classification (modified: MA200 dropped, trend-structure based).
"""
from dataclasses import dataclass
import pandas as pd
import numpy as np


@dataclass
class RegimeState:
    state: str          # BULL, BEAR, REVERSAL, RANGE
    confidence: int     # 0-100
    rsi: float
    macd_cross: str     # BULL or BEAR
    ma50: float
    price: float
    funding_rate: float
    taker_ratio: float  # latest available

    def summary(self) -> str:
        return (
            f"REGIME: {self.state:8s} (conf {self.confidence}) | "
            f"RSI: {self.rsi:.1f} | MACD: {self.macd_cross:4s} | "
            f"MA50: ${self.ma50:,.0f} | Funding: {self.funding_rate*100:+.3f}%"
        )


def classify_regime(
    df_4h: pd.DataFrame,
    rsi: float,
    macd_hist: float,
    ma50: float,
    funding_rate: float = 0.0,
    taker_ratio: float = 1.0,
) -> RegimeState:
    """
    Classify regime using MA50 + higher-high/lower-low structure on 4H.
    MA200 is NOT used.
    
    df_4h: DataFrame with [timestamp, open, high, low, close, volume], ascending.
    """
    price = float(df_4h["close"].iloc[-1])
    
    if len(df_4h) < 5:
        # Not enough data for structure check — fall back to RSI heuristic
        if rsi > 60:
            return RegimeState("BULL", 40, rsi, "?" if macd_hist >= 0 else "BEAR", ma50, price, funding_rate, taker_ratio)
        elif rsi < 40:
            return RegimeState("BEAR", 40, rsi, "?" if macd_hist >= 0 else "BEAR", ma50, price, funding_rate, taker_ratio)
        return RegimeState("RANGE", 30, rsi, "?" if macd_hist >= 0 else "BEAR", ma50, price, funding_rate, taker_ratio)
    
    # Higher-high / higher-low check (last 3 candles)
    highs = df_4h["high"].iloc[-3:].values
    lows = df_4h["low"].iloc[-3:].values
    
    hh_hl = (highs[0] < highs[1] < highs[2]) and (lows[0] < lows[1] < lows[2])
    lh_ll = (highs[0] > highs[1] > highs[2]) and (lows[0] > lows[1] > lows[2])
    
    macd_cross = "BULL" if macd_hist >= 0 else "BEAR"
    
    # BULL regime: price > MA50 + higher highs/lows structure
    if price > ma50 and hh_hl:
        return RegimeState("BULL", 80, rsi, macd_cross, ma50, price, funding_rate, taker_ratio)
    
    # BEAR regime: price < MA50 + lower highs/lows structure
    if price < ma50 and lh_ll:
        return RegimeState("BEAR", 80, rsi, macd_cross, ma50, price, funding_rate, taker_ratio)
    
    # REVERSAL setup: price < MA50, high taker ratio (buy pressure), negative funding (shorts paying)
    if price < ma50 and taker_ratio >= 1.20 and funding_rate < -0.00010:
        return RegimeState("REVERSAL", 60, rsi, macd_cross, ma50, price, funding_rate, taker_ratio)
    
    # RANGE: default
    confidence = 50 if (35 <= rsi <= 65) else 30
    return RegimeState("RANGE", confidence, rsi, macd_cross, ma50, price, funding_rate, taker_ratio)
