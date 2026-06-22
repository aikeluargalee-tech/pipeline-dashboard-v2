"""
triangles.py — Ascending, Descending, and Symmetrical Triangle detection.

Tier 1: Ascending Triangle, Descending Triangle
Tier 2: Symmetrical Triangle
"""
from typing import List, Dict, Optional
import numpy as np
import sys
from pathlib import Path

_src = Path(__file__).parent.parent
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))
if str(_src) not in sys.path:
    sys.path.insert(0, str(_src))

from state import PatternState, PatternDetection
from volume import volume_confirms_breakout
from config import (
    FLAT_TOLERANCE, MIN_TOUCHES, TRIANGLE_MIN_SPAN, TRIANGLE_MAX_SPAN,
    MIN_PATTERN_AMPLITUDE, CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW,
)


def _cluster_price(prices: List[float], tolerance: float) -> Optional[float]:
    """Find a cluster of prices within tolerance. Returns average or None."""
    if len(prices) < MIN_TOUCHES:
        return None
    prices = sorted(prices)
    # Check if min_touches consecutive prices are within tolerance
    for i in range(len(prices) - MIN_TOUCHES + 1):
        cluster = prices[i : i + MIN_TOUCHES]
        if (max(cluster) - min(cluster)) / min(cluster) <= tolerance:
            return sum(cluster) / len(cluster)
    return None


def detect_ascending_triangle(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Ascending Triangle: flat resistance + rising lows → bullish continuation.

    Conditions:
    - >= 3 swing highs within FLAT_TOLERANCE of each other (flat resistance)
    - >= 3 swing lows, each higher than the previous (rising support)
    - Pattern spans TRIANGLE_MIN_SPAN to TRIANGLE_MAX_SPAN candles
    """
    closed = candles[:-1]
    if not closed:
        return None

    # Need enough pivots
    if len(swing_highs) < MIN_TOUCHES or len(swing_lows) < MIN_TOUCHES:
        return None

    # Find flat resistance cluster from last N swing highs
    recent_highs = swing_highs[-8:] if len(swing_highs) >= 8 else swing_highs
    high_prices = [h["price"] for h in recent_highs]
    resistance = _cluster_price(high_prices, FLAT_TOLERANCE)
    if resistance is None:
        return None

    # Count touches on resistance
    resistance_touches = [
        h for h in recent_highs
        if abs(h["price"] - resistance) / resistance <= FLAT_TOLERANCE
    ]
    if len(resistance_touches) < MIN_TOUCHES:
        return None

    # Find rising lows
    recent_lows = swing_lows[-8:] if len(swing_lows) >= 8 else swing_lows
    if len(recent_lows) < MIN_TOUCHES:
        return None

    # Check rising sequence: each low higher than previous
    rising = True
    for i in range(1, min(len(recent_lows), 5)):
        if recent_lows[-i]["price"] <= recent_lows[-(i+1)]["price"]:
            rising = False
            break
    if not rising:
        return None

    # Pattern span check
    first_touch_idx = min(t["idx"] for t in resistance_touches)
    last_idx = max(max(t["idx"] for t in resistance_touches), recent_lows[-1]["idx"])
    span = last_idx - first_touch_idx
    if span < TRIANGLE_MIN_SPAN or span > TRIANGLE_MAX_SPAN:
        return None

    # Amplitude check
    support = min(l["price"] for l in recent_lows[-MIN_TOUCHES:])
    amplitude = (resistance - support) / resistance
    if amplitude < MIN_PATTERN_AMPLITUDE:
        return None

    # Determine state
    last_close = closed[-1]["close"]
    target = resistance + (resistance - support)
    stop = support * 0.99
    invalidation = min(l["price"] for l in recent_lows) * CONFIRM_BUFFER_BELOW

    # Pattern ID for tracking
    pattern_id = f"ASC_TRI_4H_{first_touch_idx}"

    if last_close > resistance * CONFIRM_BUFFER_ABOVE:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 82 if vol_ok else 65
        desc = f"Ascending triangle breakout above ${resistance:,.0f} resistance"
    elif last_close < support * CONFIRM_BUFFER_BELOW:
        state = PatternState.FAILED
        confidence = 55
        vol_ok = False
        desc = f"Ascending triangle failed — broke below ${support:,.0f} support"
    else:
        state = PatternState.FORMING
        confidence = 50
        vol_ok = False
        desc = f"Ascending triangle forming below ${resistance:,.0f} resistance"

    return PatternDetection(
        pattern_name="ASCENDING_TRIANGLE",
        tf="4H",
        direction="bullish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "resistance": round(resistance, 1),
            "support": round(support, 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(invalidation, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_descending_triangle(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Descending Triangle: flat support + falling highs → bearish continuation.

    Mirror of ascending triangle.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_highs) < MIN_TOUCHES or len(swing_lows) < MIN_TOUCHES:
        return None

    # Find flat support cluster
    recent_lows = swing_lows[-8:] if len(swing_lows) >= 8 else swing_lows
    low_prices = [l["price"] for l in recent_lows]
    support = _cluster_price(low_prices, FLAT_TOLERANCE)
    if support is None:
        return None

    support_touches = [
        l for l in recent_lows
        if abs(l["price"] - support) / support <= FLAT_TOLERANCE
    ]
    if len(support_touches) < MIN_TOUCHES:
        return None

    # Find falling highs
    recent_highs = swing_highs[-8:] if len(swing_highs) >= 8 else swing_highs
    if len(recent_highs) < MIN_TOUCHES:
        return None

    falling = True
    for i in range(1, min(len(recent_highs), 5)):
        if recent_highs[-i]["price"] >= recent_highs[-(i+1)]["price"]:
            falling = False
            break
    if not falling:
        return None

    # Span check
    first_touch_idx = min(t["idx"] for t in support_touches)
    last_idx = max(max(t["idx"] for t in support_touches), recent_highs[-1]["idx"])
    span = last_idx - first_touch_idx
    if span < TRIANGLE_MIN_SPAN or span > TRIANGLE_MAX_SPAN:
        return None

    # Amplitude check
    resistance = max(h["price"] for h in recent_highs[-MIN_TOUCHES:])
    amplitude = (resistance - support) / support
    if amplitude < MIN_PATTERN_AMPLITUDE:
        return None

    last_close = closed[-1]["close"]
    target = support - (resistance - support)
    stop = resistance * 1.01
    invalidation = max(h["price"] for h in recent_highs) * CONFIRM_BUFFER_ABOVE

    pattern_id = f"DESC_TRI_4H_{first_touch_idx}"

    if last_close < support * CONFIRM_BUFFER_BELOW:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 82 if vol_ok else 65
        desc = f"Descending triangle breakdown below ${support:,.0f} support"
    elif last_close > resistance * CONFIRM_BUFFER_ABOVE:
        state = PatternState.FAILED
        confidence = 55
        vol_ok = False
        desc = f"Descending triangle failed — broke above ${resistance:,.0f} resistance"
    else:
        state = PatternState.FORMING
        confidence = 50
        vol_ok = False
        desc = f"Descending triangle forming above ${support:,.0f} support"

    return PatternDetection(
        pattern_name="DESCENDING_TRIANGLE",
        tf="4H",
        direction="bearish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "resistance": round(resistance, 1),
            "support": round(support, 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(invalidation, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_symmetrical_triangle(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Symmetrical Triangle: converging trendlines — bilateral pattern.

    Upper trendline slopes DOWN, lower trendline slopes UP.
    Direction bias = prior trend (price 50 candles ago vs current).
    Confidence inherently capped at 62% due to bilateral nature.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_highs) < MIN_TOUCHES or len(swing_lows) < MIN_TOUCHES:
        return None

    # Use last 5 pivots of each type
    recent_highs = swing_highs[-5:]
    recent_lows = swing_lows[-5:]

    if len(recent_highs) < 3 or len(recent_lows) < 3:
        return None

    # Fit linear regression to highs → should slope DOWN
    hx = np.array([h["idx"] for h in recent_highs])
    hy = np.array([h["price"] for h in recent_highs])
    h_slope, h_intercept = np.polyfit(hx, hy, 1)

    # Fit linear regression to lows → should slope UP
    lx = np.array([l["idx"] for l in recent_lows])
    ly = np.array([l["price"] for l in recent_lows])
    l_slope, l_intercept = np.polyfit(lx, ly, 1)

    # Upper must slope down, lower must slope up
    if h_slope >= 0 or l_slope <= 0:
        return None

    # Span check
    first_idx = min(hx[0], lx[0])
    last_idx = max(hx[-1], lx[-1])
    span = last_idx - first_idx
    if span < TRIANGLE_MIN_SPAN or span > TRIANGLE_MAX_SPAN:
        return None

    # Amplitude check
    mid_price = (hy[0] + ly[0]) / 2
    amplitude = (hy[0] - ly[0]) / mid_price
    if amplitude < MIN_PATTERN_AMPLITUDE:
        return None

    # Prior trend: 50 candles ago vs current
    prior_idx = max(0, len(closed) - 51)
    if len(closed) > 50:
        prior_close = closed[prior_idx]["close"]
        current_close = closed[-1]["close"]
        prior_trend = "bullish" if current_close > prior_close else "bearish"
    else:
        prior_trend = "neutral"

    last_close = closed[-1]["close"]

    # Project trendlines to current candle
    h_proj = h_slope * len(closed) + h_intercept
    l_proj = l_slope * len(closed) + l_intercept

    target_up = h_proj + (h_proj - l_proj)
    target_down = l_proj - (h_proj - l_proj)
    pattern_id = f"SYM_TRI_4H_{first_idx}"

    if last_close > h_proj * CONFIRM_BUFFER_ABOVE:
        # Breakout upward
        state = PatternState.CONFIRMED
        direction = "bullish"
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        aligned = prior_trend == "bullish"
        confidence = 62 if aligned else 55
        if vol_ok:
            confidence = min(confidence + 8, 70)
        desc = f"Symmetrical triangle breakout upward (trend: {prior_trend})"
        target = target_up
        stop = l_proj * 0.99
    elif last_close < l_proj * CONFIRM_BUFFER_BELOW:
        # Breakout downward
        state = PatternState.CONFIRMED
        direction = "bearish"
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        aligned = prior_trend == "bearish"
        confidence = 62 if aligned else 55
        if vol_ok:
            confidence = min(confidence + 8, 70)
        desc = f"Symmetrical triangle breakdown downward (trend: {prior_trend})"
        target = target_down
        stop = h_proj * 1.01
    else:
        state = PatternState.FORMING
        direction = prior_trend if prior_trend != "neutral" else "bullish"
        confidence = 45
        vol_ok = False
        desc = f"Symmetrical triangle forming — bilateral, awaiting breakout"
        target = target_up if direction == "bullish" else target_down
        stop = (l_proj * 0.99) if direction == "bullish" else (h_proj * 1.01)

    return PatternDetection(
        pattern_name="SYMMETRICAL_TRIANGLE",
        tf="4H",
        direction=direction,
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "upper_trendline": round(float(h_proj), 1),
            "lower_trendline": round(float(l_proj), 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )
