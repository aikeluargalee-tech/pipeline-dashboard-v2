"""
candles.py — Candle attribute computation + 4-factor pattern scoring.
Deterministic. No fuzzy LLM logic.
"""
from dataclasses import dataclass, field
from typing import Optional
import pandas as pd
import numpy as np


@dataclass
class Candle:
    """Single candle with computed attributes."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float

    # Computed
    body: float = 0.0          # |close - open|
    body_pct: float = 0.0       # body / range * 100
    direction: str = "NEUTRAL"  # BULL, BEAR, NEUTRAL
    size_label: str = "S"       # S (small), M (medium), L (large)
    body_label: str = "S"       # body size label
    candle_type: str = "NEUTRAL"  # ATR-normalized: BULL_STRONG, BEAR_STRONG, BULL_PIN, BEAR_PIN, DOJI, NEUTRAL
    wick_upper: float = 0.0
    wick_lower: float = 0.0
    wick_upper_pct: float = 0.0
    wick_lower_pct: float = 0.0
    range_pct: float = 0.0      # range / close * 100
    volume_ratio: float = 1.0   # vol / 6-candle avg vol
    atr: float = 0.0            # ATR value for normalization (set externally)

    def __post_init__(self):
        self.body = abs(self.close - self.open)
        self.range_pct = (self.high - self.low) / self.close * 100 if self.close > 0 else 0

        if self.body > 0:
            self.body_pct = self.body / (self.high - self.low) * 100 if (self.high != self.low) else 0
        
        self.direction = "BULL" if self.close > self.open else ("BEAR" if self.close < self.open else "NEUTRAL")

        # Wick computation
        if self.close >= self.open:
            self.wick_upper = self.high - self.close
            self.wick_lower = self.open - self.low
        else:
            self.wick_upper = self.high - self.open
            self.wick_lower = self.close - self.low
        
        candle_range = self.high - self.low
        self.wick_upper_pct = (self.wick_upper / candle_range * 100) if candle_range > 0 else 0
        self.wick_lower_pct = (self.wick_lower / candle_range * 100) if candle_range > 0 else 0

        # Size labels
        self.size_label = self._classify_size()
        self.body_label = self._classify_body()
        self.candle_type = self._classify_type()

    def _classify_size(self) -> str:
        """S/M/L based on ATR if available, else fallback to range_pct thresholds."""
        if self.atr > 0 and self.close > 0:
            range_atr_ratio = (self.high - self.low) / self.atr
            if range_atr_ratio < 0.3:
                return "S"
            elif range_atr_ratio < 0.7:
                return "M"
            return "L"
        # Fallback: static thresholds for 15m candles
        if self.range_pct < 0.15:
            return "S"
        elif self.range_pct < 0.40:
            return "M"
        return "L"

    def _classify_body(self) -> str:
        """Body size label: Doji (<15%), Small (15-50%), Marubozu (>50%)."""
        if self.body_pct < 15:
            return "D"   # Doji
        elif self.body_pct < 50:
            return "S"   # Small body
        return "M"       # Marubozu-like

    def _classify_type(self) -> str:
        """ATR-normalized candle type classification.
        
        Uses body/range ratios for shape, ATR for context:
        - STRONG: large range ( > 0.5 ATR), body dominates ( > 60% of range)
        - PINBAR: long wick ( > 60% of range), small body ( < 30% of range)
        - DOJI: tiny body ( < 10% of range)
        - NEUTRAL: none of the above
        """
        candle_range = self.high - self.low
        if candle_range <= 0:
            return "NEUTRAL"

        body_ratio = self.body / candle_range
        upper_wick_ratio = self.wick_upper / candle_range
        lower_wick_ratio = self.wick_lower / candle_range

        # ATR context: is this a significant candle?
        atr_significant = (self.atr > 0 and candle_range / self.atr > 0.5) or (self.atr <= 0 and self.range_pct > 0.25)

        # Doji: body is < 10% of range
        if body_ratio < 0.10:
            return "DOJI"

        # Strong: large range, body dominates, small wicks
        if atr_significant and body_ratio > 0.60 and upper_wick_ratio < 0.25 and lower_wick_ratio < 0.25:
            return "BULL_STRONG" if self.direction == "BULL" else "BEAR_STRONG"

        # Bullish pinbar: long lower wick, small body at top
        if lower_wick_ratio > 0.60 and body_ratio < 0.30:
            return "BULL_PIN"

        # Bearish pinbar: long upper wick, small body at bottom
        if upper_wick_ratio > 0.60 and body_ratio < 0.30:
            return "BEAR_PIN"

        return "NEUTRAL"

    def range_label(self) -> str:
        """EXP (expanding), CONTR (contracting), INSIDE, or OUTSIDE — computed externally."""
        return "EXP"  # placeholder, set by compare logic


@dataclass
class ThreeCandlePattern:
    """Three-candle sequence with 4-factor pattern scoring."""
    c3: Candle
    c2: Candle
    c1: Candle
    timeframe: str

    # Range comparison
    c3_range_label: str = ""
    c2_range_label: str = ""
    c1_range_label: str = ""

    # 4-factor scores (0-100 total)
    dir_score: int = 0      # Directional consistency (0-40)
    range_score: int = 0    # Range trend (0-30)
    vol_score: int = 0      # Volume trend (0-20)
    wick_score: int = 0     # Wick rejection (0-10)
    confidence: int = 0     # Total
    
    pattern_label: str = "MIXED"
    volume_trend: str = "FLAT"

    def compute(self):
        self._compute_range_labels()
        self._compute_directional_consistency()
        self._compute_range_trend()
        self._compute_volume_trend()
        self._compute_wick_rejection()
        
        self.confidence = min(100, self.dir_score + self.range_score + self.vol_score + self.wick_score)
        self._derive_label()

    def _compute_range_labels(self):
        """Compare range sizes: EXP (expanding), CONTR (contracting), INSIDE, OUTSIDE."""
        def compare(c_prev: Candle, c_curr: Candle) -> str:
            """Compare current candle range to previous."""
            prev_range = c_prev.high - c_prev.low
            curr_range = c_curr.high - c_curr.low
            if curr_range > prev_range * 1.1:
                return "EXP"
            elif curr_range < prev_range * 0.9:
                return "CONTR"
            else:
                return "SAME"
        
        def inside(c_prev: Candle, c_curr: Candle) -> bool:
            return c_curr.high <= c_prev.high and c_curr.low >= c_prev.low

        def outside(c_prev: Candle, c_curr: Candle) -> bool:
            return c_curr.high >= c_prev.high and c_curr.low <= c_prev.low

        self.c3_range_label = "EXP"  # baseline
        self.c2_range_label = compare(self.c3, self.c2)
        self.c1_range_label = compare(self.c2, self.c1)

        # Override with INSIDE/OUTSIDE if applicable
        if inside(self.c2, self.c1):
            self.c1_range_label = "INSIDE"
        if outside(self.c2, self.c1):
            self.c1_range_label = "OUTSIDE"
        if inside(self.c3, self.c2):
            self.c2_range_label = "INSIDE"
        if outside(self.c3, self.c2):
            self.c2_range_label = "OUTSIDE"

    def _compute_directional_consistency(self) -> int:
        """Score 0-40 based on direction alignment across 3 candles."""
        dirs = [self.c3.direction, self.c2.direction, self.c1.direction]
        
        if dirs[0] == dirs[1] == dirs[2]:
            self.dir_score = 40
        elif dirs[0] == dirs[1] or dirs[1] == dirs[2]:
            # Two consecutive same direction
            if dirs[0] == dirs[1]:
                self.dir_score = 20
            else:
                self.dir_score = 15  # last two same
        else:
            self.dir_score = 0

    def _compute_range_trend(self) -> int:
        """Score 0-30 based on range pattern."""
        labels = [self.c3_range_label, self.c2_range_label, self.c1_range_label]
        
        if labels == ["EXP", "EXP", "EXP"]:
            self.range_score = 30
        elif labels[2] == "CONTR" and labels[1] in ("EXP", "CONTR"):
            # Coiling: EXP→CONTR→CONTR or CONTR→CONTR→CONTR
            if "EXP" in labels[:2]:
                self.range_score = 20  # POST_EXP_COIL
            else:
                self.range_score = 25  # Tight coil
        elif "OUTSIDE" in (labels[1], labels[2]):
            self.range_score = 25  # Engulf
        elif "INSIDE" in (labels[1], labels[2]):
            self.range_score = 10
        else:
            self.range_score = 0

    def _compute_volume_trend(self) -> int:
        """Score 0-20 based on volume direction and alignment."""
        v3, v2, v1 = self.c3.volume_ratio, self.c2.volume_ratio, self.c1.volume_ratio
        
        if v1 > v2 > v3:
            self.volume_trend = "RISING"
            # Rising volume + bullish direction = strong
            if self.c1.direction == "BULL" and self.dir_score >= 20:
                self.vol_score = 20
            elif self.dir_score >= 20:
                self.vol_score = 10
            else:
                self.vol_score = 5
        elif v1 < v2 < v3:
            self.volume_trend = "FALLING"
            self.vol_score = 15  # Volume declining = absorption/coil
        else:
            self.volume_trend = "FLAT"
            self.vol_score = 5

    def _compute_wick_rejection(self) -> int:
        """Score 0-10 for wick rejection signals."""
        score = 0
        # C3 or C2 wick >30% on high volume
        for c in [self.c3, self.c2]:
            if c.wick_upper_pct > 30 or c.wick_lower_pct > 30:
                if c.volume_ratio > 1.5:
                    score += 5
        
        # C1 wick >30% on volume >1.5x avg
        if self.c1.wick_upper_pct > 30 or self.c1.wick_lower_pct > 30:
            if self.c1.volume_ratio > 1.5:
                score += 10
        self.wick_score = min(10, score)

    def _derive_label(self):
        """Derive human-readable pattern label from scores."""
        if self.dir_score >= 30 and self.vol_score >= 15 and self.range_score >= 20:
            self.pattern_label = "MOMENTUM"
        elif self.dir_score >= 30 and self.range_score >= 25:
            self.pattern_label = "ENGULF" if any("OUTSIDE" in l for l in [self.c1_range_label, self.c2_range_label]) else "MOMENTUM"
        elif self.range_score >= 20 and self.vol_score >= 10 and self.dir_score < 30:
            self.pattern_label = "POST_EXP_COIL" if self.range_score == 20 else "COIL"
        elif self.wick_score >= 10:
            self.pattern_label = "ABSORPTION"
        elif self.dir_score <= 10 and self.range_score <= 10:
            self.pattern_label = "MIXED"
        else:
            self.pattern_label = "MIXED"

    def summary(self) -> str:
        return (
            f"C3  {self.c3.size_label} {self.c3.direction[:4]:4s} [{self.c3.candle_type:12s}] | "
            f"Wicks U:{int(self.c3.wick_upper_pct)} L:{int(self.c3.wick_lower_pct)} | "
            f"{self.c3_range_label:5s} | Vol:{self.c3.volume_ratio:.1f}x"
        )


def compute_three_candle_pattern(df: pd.DataFrame, timeframe: str) -> ThreeCandlePattern:
    """
    Extract last 3 candles from DataFrame and compute pattern.
    df must have columns: timestamp, open, high, low, close, volume
    sorted ascending by timestamp.
    """
    if len(df) < 3:
        raise ValueError(f"Need at least 3 candles, got {len(df)}")
    
    last3 = df.iloc[-3:]
    
    # Compute ATR (14-period) for normalization
    atr = 0.0
    if len(df) >= 15:
        high = df["high"].values
        low = df["low"].values
        close = df["close"].values
        tr = np.maximum(high[1:] - low[1:], 
                        np.maximum(np.abs(high[1:] - close[:-1]), 
                                   np.abs(low[1:] - close[:-1])))
        atr = float(np.mean(tr[-14:]))
    
    # Compute volume ratios (vol / 6-candle average where available)
    vol_avg = df["volume"].rolling(6).mean()
    
    candles = []
    for i in range(3):
        row = last3.iloc[i]
        vol_ratio = row["volume"] / vol_avg.iloc[last3.index[i]] if pd.notna(vol_avg.iloc[last3.index[i]]) and vol_avg.iloc[last3.index[i]] > 0 else 1.0
        c = Candle(
            timestamp=int(row["timestamp"]),
            open=float(row["open"]),
            high=float(row["high"]),
            low=float(row["low"]),
            close=float(row["close"]),
            volume=float(row["volume"]),
            atr=atr,
        )
        c.volume_ratio = vol_ratio
        candles.append(c)
    
    pattern = ThreeCandlePattern(
        c3=candles[0],
        c2=candles[1],
        c1=candles[2],
        timeframe=timeframe,
    )
    pattern.compute()
    return pattern
