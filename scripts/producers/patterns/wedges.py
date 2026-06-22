"""
wedges.py — Rising Wedge and Falling Wedge detection.

Tier 2 patterns.
Uses numpy.polyfit for trendline regression.
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
from volume import volume_declines_through_pattern
from config import (
    MIN_TOUCHES, MIN_PATTERN_AMPLITUDE,
    CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW, TARGET_CAP,
)


def _fit_wedge_trendlines(
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    min_touches: int = MIN_TOUCHES,
) -> Optional[Dict]:
    """Fit upper and lower trendlines for wedge patterns."""
    if len(swing_highs) < min_touches or len(swing_lows) < min_touches:
        return None

    # Use last 5 of each
    highs = swing_highs[-5:]
    lows = swing_lows[-5:]

    if len(highs) < 3 or len(lows) < 3:
        return None

    hx = np.array([h["idx"] for h in highs])
    hy = np.array([h["price"] for h in highs])
    lx = np.array([l["idx"] for l in lows])
    ly = np.array([l["price"] for l in lows])

    h_slope, h_intercept = np.polyfit(hx, hy, 1)
    l_slope, l_intercept = np.polyfit(lx, ly, 1)

    # Count touches near each trendline
    h_tolerance = 0.02  # 2% tolerance
    l_tolerance = 0.02

    h_touches = sum(
        1 for h in swing_highs[-8:]
        if abs(h["price"] - (h_slope * h["idx"] + h_intercept))
        / max(h["price"], 1) <= h_tolerance
    )
    l_touches = sum(
        1 for l in swing_lows[-8:]
        if abs(l["price"] - (l_slope * l["idx"] + l_intercept))
        / max(l["price"], 1) <= l_tolerance
    )

    if h_touches < min_touches or l_touches < min_touches:
        return None

    # Amplitude check
    midpoint = (hy[0] + ly[0]) / 2
    amplitude = (hy[0] - ly[0]) / midpoint
    if amplitude < MIN_PATTERN_AMPLITUDE:
        return None

    return {
        "h_slope": float(h_slope),
        "h_intercept": float(h_intercept),
        "l_slope": float(l_slope),
        "l_intercept": float(l_intercept),
        "h_touches": h_touches,
        "l_touches": l_touches,
        "first_idx": int(min(hx[0], lx[0])),
        "last_idx": int(max(hx[-1], lx[-1])),
    }


def detect_rising_wedge(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Rising Wedge: both trendlines slope UP but converge.
    Highs rising slower than lows → bearish signal.
    """
    closed = candles[:-1]
    if not closed:
        return None

    wedge = _fit_wedge_trendlines(swing_highs, swing_lows)
    if wedge is None:
        return None

    # Both slopes must be positive
    if wedge["h_slope"] <= 0 or wedge["l_slope"] <= 0:
        return None

    # Convergence: upper slope < lower slope
    if wedge["h_slope"] >= wedge["l_slope"]:
        return None

    span = wedge["last_idx"] - wedge["first_idx"]
    if span < 15:
        return None

    # Volume declining through formation
    vol_declining = volume_declines_through_pattern(
        candles, wedge["first_idx"], wedge["last_idx"]
    )

    # Project trendlines to current
    n = len(closed)
    h_proj = wedge["h_slope"] * n + wedge["h_intercept"]
    l_proj = wedge["l_slope"] * n + wedge["l_intercept"]

    last_close = closed[-1]["close"]
    # Wedge height at formation START (widest point — used for measured move)
    h_start = wedge["h_slope"] * wedge["first_idx"] + wedge["h_intercept"]
    l_start = wedge["l_slope"] * wedge["first_idx"] + wedge["l_intercept"]
    wedge_height = h_start - l_start  # positive for rising wedge
    stop = h_proj * 1.01
    pattern_id = f"RWEDGE_4H_{wedge['first_idx']}"

    if last_close < l_proj * CONFIRM_BUFFER_BELOW:
        state = PatternState.CONFIRMED
        confidence = 72 if vol_declining else 60
        vol_ok = vol_declining
        desc = "Rising wedge breakdown — bearish resolution"
        # Target measured from breakdown price downward by wedge height
        target = last_close - wedge_height * TARGET_CAP
    elif last_close > h_proj * CONFIRM_BUFFER_ABOVE:
        state = PatternState.FAILED
        confidence = 65
        vol_ok = False
        desc = "Rising wedge FAILED — breakout above (bullish counter-signal)"
        target = h_proj
    else:
        state = PatternState.FORMING
        confidence = 48
        vol_ok = vol_declining
        desc = "Rising wedge forming — compression before expected breakdown"
        # Target from lower trendline projected downward by wedge height
        target = l_proj - wedge_height * TARGET_CAP

    return PatternDetection(
        pattern_name="RISING_WEDGE",
        tf="4H",
        direction="bearish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "upper_trendline": round(h_proj, 1),
            "lower_trendline": round(l_proj, 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_falling_wedge(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Falling Wedge: both trendlines slope DOWN but converge.
    Lows falling slower than highs → bullish reversal signal.
    """
    closed = candles[:-1]
    if not closed:
        return None

    wedge = _fit_wedge_trendlines(swing_highs, swing_lows)
    if wedge is None:
        return None

    # Both slopes must be negative
    if wedge["h_slope"] >= 0 or wedge["l_slope"] >= 0:
        return None

    # Convergence: abs(lower slope) < abs(upper slope)
    if abs(wedge["l_slope"]) >= abs(wedge["h_slope"]):
        return None

    span = wedge["last_idx"] - wedge["first_idx"]
    if span < 15:
        return None

    vol_declining = volume_declines_through_pattern(
        candles, wedge["first_idx"], wedge["last_idx"]
    )

    n = len(closed)
    h_proj = wedge["h_slope"] * n + wedge["h_intercept"]
    l_proj = wedge["l_slope"] * n + wedge["l_intercept"]

    last_close = closed[-1]["close"]
    # Wedge height at formation START (widest point — used for measured move)
    h_start = wedge["h_slope"] * wedge["first_idx"] + wedge["h_intercept"]
    l_start = wedge["l_slope"] * wedge["first_idx"] + wedge["l_intercept"]
    wedge_height = h_start - l_start  # positive (h_proj > l_proj)
    stop = l_proj * 0.99
    pattern_id = f"FWEDGE_4H_{wedge['first_idx']}"

    if last_close > h_proj * CONFIRM_BUFFER_ABOVE:
        state = PatternState.CONFIRMED
        confidence = 72 if vol_declining else 60
        vol_ok = vol_declining
        desc = "Falling wedge breakout — bullish resolution"
        # Target measured from breakout price upward by wedge height
        target = last_close + wedge_height * TARGET_CAP
    elif last_close < l_proj * CONFIRM_BUFFER_BELOW:
        state = PatternState.FAILED
        confidence = 65
        vol_ok = False
        desc = "Falling wedge FAILED — breakdown below (bearish acceleration)"
        target = l_proj
    else:
        state = PatternState.FORMING
        confidence = 48
        vol_ok = vol_declining
        desc = "Falling wedge forming — compression before expected breakout"
        # Target from upper trendline projected upward by wedge height
        target = h_proj + wedge_height * TARGET_CAP

    return PatternDetection(
        pattern_name="FALLING_WEDGE",
        tf="4H",
        direction="bullish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "upper_trendline": round(h_proj, 1),
            "lower_trendline": round(l_proj, 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )
