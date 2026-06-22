"""
channels.py — Channel Up and Channel Down detection.

Tier 3 patterns.
Parallel trendlines sloping in the same direction.
FORMING = trend active, FAILED = trend broken, CONFIRMED = acceleration.
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
from config import (
    MIN_TOUCHES, CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW,
    MIN_PATTERN_AMPLITUDE,
)


def _fit_channel(
    swing_highs: List[Dict],
    swing_lows: List[Dict],
) -> Optional[Dict]:
    """Fit parallel trendlines for channel patterns."""
    if len(swing_highs) < MIN_TOUCHES or len(swing_lows) < MIN_TOUCHES:
        return None

    highs = swing_highs[-6:]
    lows = swing_lows[-6:]

    if len(highs) < 3 or len(lows) < 3:
        return None

    hx = np.array([h["idx"] for h in highs])
    hy = np.array([h["price"] for h in highs])
    lx = np.array([l["idx"] for l in lows])
    ly = np.array([l["price"] for l in lows])

    h_slope, h_intercept = np.polyfit(hx, hy, 1)
    l_slope, l_intercept = np.polyfit(lx, ly, 1)

    # Parallel check: slope difference <= 15% of larger slope
    max_slope = max(abs(h_slope), abs(l_slope))
    if max_slope < 0.001:
        # Horizontal channel — acceptable as a special case
        slope_diff = 0.0
    else:
        slope_diff = abs(h_slope - l_slope) / max_slope

    if slope_diff > 0.15:
        return None

    # Count touches
    tolerance = 0.02
    h_touches = sum(
        1 for h in swing_highs[-10:]
        if abs(h["price"] - (h_slope * h["idx"] + h_intercept))
        / max(h["price"], 1) <= tolerance
    )
    l_touches = sum(
        1 for l in swing_lows[-10:]
        if abs(l["price"] - (l_slope * l["idx"] + l_intercept))
        / max(l["price"], 1) <= tolerance
    )

    if h_touches < MIN_TOUCHES or l_touches < MIN_TOUCHES:
        return None

    # Amplitude
    midpoint = (hy[0] + ly[0]) / 2
    amplitude = (hy[0] - ly[0]) / midpoint
    if amplitude < MIN_PATTERN_AMPLITUDE:
        return None

    return {
        "h_slope": float(h_slope),
        "h_intercept": float(h_intercept),
        "l_slope": float(l_slope),
        "l_intercept": float(l_intercept),
        "first_idx": int(min(hx[0], lx[0])),
        "last_idx": int(max(hx[-1], lx[-1])),
        "direction": "up" if h_slope > 0 and l_slope > 0 else "down",
    }


def detect_channel_up(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Channel Up: parallel rising trendlines — bullish trend active."""
    closed = candles[:-1]
    if not closed:
        return None

    ch = _fit_channel(swing_highs, swing_lows)
    if ch is None:
        return None

    if ch["direction"] != "up":
        return None

    # Both must slope up
    if ch["h_slope"] <= 0 or ch["l_slope"] <= 0:
        # Check for near-horizontal
        if abs(ch["h_slope"]) > 0.0005 or abs(ch["l_slope"]) > 0.0005:
            return None

    span = ch["last_idx"] - ch["first_idx"]
    if span < 20:
        return None

    n = len(closed)
    h_proj = ch["h_slope"] * n + ch["h_intercept"]
    l_proj = ch["l_slope"] * n + ch["l_intercept"]

    last_close = closed[-1]["close"]
    target = h_proj * 1.02
    stop = l_proj * 0.99
    pattern_id = f"CHUP_4H_{ch['first_idx']}"

    if last_close > h_proj * CONFIRM_BUFFER_ABOVE:
        state = PatternState.CONFIRMED
        confidence = 72
        vol_ok = True
        desc = "Channel Up acceleration — breakout above upper channel (trend acceleration)"
    elif last_close < l_proj * CONFIRM_BUFFER_BELOW:
        state = PatternState.FAILED
        confidence = 68
        vol_ok = False
        desc = "Channel Up broken — close below lower channel (trend reversal signal)"
    else:
        state = PatternState.FORMING
        confidence = 68
        vol_ok = False
        desc = "Channel Up active — bullish trend, buy zone near lower channel"

    return PatternDetection(
        pattern_name="CHANNEL_UP",
        tf="4H",
        direction="bullish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "upper_channel": round(float(h_proj), 1),
            "lower_channel": round(float(l_proj), 1),
            "target": round(float(target), 1),
            "stop": round(float(stop), 1),
        },
        description=desc,
        invalidation_price=round(float(stop), 1),
        btc_price=round(float(last_close), 1),
        pattern_id=pattern_id,
    )


def detect_channel_down(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Channel Down: parallel falling trendlines — bearish trend active."""
    closed = candles[:-1]
    if not closed:
        return None

    ch = _fit_channel(swing_highs, swing_lows)
    if ch is None:
        return None

    if ch["direction"] != "down":
        return None

    if ch["h_slope"] >= 0 or ch["l_slope"] >= 0:
        if abs(ch["h_slope"]) > 0.0005 or abs(ch["l_slope"]) > 0.0005:
            return None

    span = ch["last_idx"] - ch["first_idx"]
    if span < 20:
        return None

    n = len(closed)
    h_proj = ch["h_slope"] * n + ch["h_intercept"]
    l_proj = ch["l_slope"] * n + ch["l_intercept"]

    last_close = closed[-1]["close"]
    target = l_proj * 0.98
    stop = h_proj * 1.01
    pattern_id = f"CHDN_4H_{ch['first_idx']}"

    if last_close < l_proj * CONFIRM_BUFFER_BELOW:
        state = PatternState.CONFIRMED
        confidence = 72
        vol_ok = True
        desc = "Channel Down acceleration — breakdown below lower channel"
    elif last_close > h_proj * CONFIRM_BUFFER_ABOVE:
        state = PatternState.FAILED
        confidence = 68
        vol_ok = False
        desc = "Channel Down broken — close above upper channel (trend reversal signal)"
    else:
        state = PatternState.FORMING
        confidence = 68
        vol_ok = False
        desc = "Channel Down active — bearish trend, resistance near upper channel"

    return PatternDetection(
        pattern_name="CHANNEL_DOWN",
        tf="4H",
        direction="bearish",
        state=state,
        confidence=confidence,
        candles_span=span,
        volume_confirmed=vol_ok,
        key_levels={
            "upper_channel": round(float(h_proj), 1),
            "lower_channel": round(float(l_proj), 1),
            "target": round(float(target), 1),
            "stop": round(float(stop), 1),
        },
        description=desc,
        invalidation_price=round(float(stop), 1),
        btc_price=round(float(last_close), 1),
        pattern_id=pattern_id,
    )
