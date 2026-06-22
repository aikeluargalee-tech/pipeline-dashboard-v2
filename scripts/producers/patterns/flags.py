"""
flags.py — Bull Flag, Bear Flag, Bull Pennant, Bear Pennant.

Tier 1: Bull Flag, Bear Flag
Tier 2: Bull Pennant, Bear Pennant
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
from volume import (
    volume_confirms_breakout, volume_declines_through_pattern,
)
from config import (
    POLE_MIN_RETURN, POLE_MAX_CANDLES,
    FLAG_MIN_CANDLES, FLAG_MAX_CANDLES, FLAG_MAX_RETRACE,
    PENNANT_MIN_CANDLES, PENNANT_MAX_CANDLES,
    CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW,
    MIN_PATTERN_AMPLITUDE, TARGET_CAP,
)


def _find_pole(
    candles: List[Dict],
    direction: str,
    max_candles: int = POLE_MAX_CANDLES,
    min_return: float = POLE_MIN_RETURN,
) -> Optional[Dict]:
    """
    Find a sharp pole (impulse move) in the specified direction.

    Returns dict with start_idx, end_idx, start_price, end_price, length.
    """
    closed = candles[:-1]
    n = len(closed)
    if n < max_candles + 5:
        return None

    # Look at last N candles for a sharp move
    search_start = max(0, n - max_candles - 20)
    for i in range(search_start, n - 3):
        for j in range(i + 3, min(i + max_candles + 1, n)):
            start_price = closed[i]["close"]
            end_price = closed[j]["close"]

            if direction == "bullish":
                ret = (end_price - start_price) / start_price
                if ret >= min_return:
                    # Check it's a clean pole (mostly one-directional)
                    mid = (i + j) // 2
                    mid_price = closed[mid]["close"]
                    if mid_price > start_price and mid_price < end_price:
                        return {
                            "start_idx": i,
                            "end_idx": j,
                            "start_price": start_price,
                            "end_price": end_price,
                            "return_pct": ret,
                        }
            else:  # bearish
                ret = (start_price - end_price) / start_price
                if ret >= min_return:
                    mid = (i + j) // 2
                    mid_price = closed[mid]["close"]
                    if mid_price < start_price and mid_price > end_price:
                        return {
                            "start_idx": i,
                            "end_idx": j,
                            "start_price": start_price,
                            "end_price": end_price,
                            "return_pct": ret,
                        }
    return None


def _find_flag_channel(
    candles: List[Dict],
    start_idx: int,
    end_idx: int,
    direction: str,
    min_candles: int = FLAG_MIN_CANDLES,
    max_candles: int = FLAG_MAX_CANDLES,
    converging: bool = False,
) -> Optional[Dict]:
    """
    Find the flag/pennant consolidation after a pole.

    Flag: parallel channel slightly against the pole direction.
    Pennant: converging trendlines (tight symmetrical triangle after pole).

    converging=False → flag (parallel channel)
    converging=True → pennant (converging trendlines)
    """
    closed = candles[:-1]
    n = len(closed)
    available = n - end_idx - 1  # candles after pole
    if available < min_candles:
        return None

    flag_end = min(end_idx + max_candles + 1, n)
    flag_start = end_idx + 1

    if flag_end - flag_start < min_candles:
        return None

    flag_candles = closed[flag_start:flag_end]

    if converging:
        # Pennant: fit converging trendlines to highs and lows
        idxs = np.arange(len(flag_candles))
        highs = np.array([c["high"] for c in flag_candles])
        lows = np.array([c["low"] for c in flag_candles])

        if len(idxs) < 3:
            return None

        high_slope, high_intercept = np.polyfit(idxs, highs, 1)
        low_slope, low_intercept = np.polyfit(idxs, lows, 1)

        # For pennant, trendlines must converge
        if direction == "bullish":
            # After bull pole: flag drifts down slightly, highs fall, lows rise
            if high_slope >= 0 and low_slope <= 0:
                pass  # convergence
            elif not (high_slope < 0 and low_slope > 0):
                return None
        else:
            # After bear pole: flag drifts up slightly, highs fall, lows rise
            if not (high_slope < 0 and low_slope > 0):
                # Check if just decaying
                if not (abs(high_slope) < 0.001 and abs(low_slope) < 0.001):
                    return None

        upper_line = high_intercept + high_slope * len(flag_candles)
        lower_line = low_intercept + low_slope * len(flag_candles)
    else:
        # Flag: parallel channel
        highs = np.array([c["high"] for c in flag_candles])
        lows = np.array([c["low"] for c in flag_candles])

        upper_line = max(highs[:3]) if len(highs) >= 3 else highs[-1]
        lower_line = min(lows[:3]) if len(lows) >= 3 else lows[-1]

    # Check retracement: flag range vs pole range
    pole_range = abs(
        closed[end_idx]["close"] - closed[flag_start - 1]["close"]
    )
    flag_range = upper_line - lower_line

    # Retracement = flag range should be <= FLAG_MAX_RETRACE of pole
    if pole_range > 0:
        retrace = flag_range / pole_range
        if retrace > FLAG_MAX_RETRACE:
            return None

    # Volume should decline through flag
    vol_declining = volume_declines_through_pattern(
        candles, flag_start, flag_end
    )

    return {
        "start_idx": flag_start,
        "end_idx": flag_end - 1,
        "upper_line": float(upper_line),
        "lower_line": float(lower_line),
        "mid_line": float((upper_line + lower_line) / 2),
        "retrace_pct": float(flag_range / pole_range) if pole_range > 0 else 0.0,
        "vol_declining": vol_declining,
        "span": flag_end - flag_start,
    }


def detect_bull_flag(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Bull Flag: sharp up move + tight downward-drifting consolidation."""
    closed = candles[:-1]
    if not closed:
        return None

    pole = _find_pole(candles, "bullish")
    if pole is None:
        return None

    flag = _find_flag_channel(candles, pole["start_idx"], pole["end_idx"], "bullish")
    if flag is None:
        return None

    last_close = closed[-1]["close"]
    target = pole["end_price"] + (pole["end_price"] - pole["start_price"]) * TARGET_CAP
    stop = flag["lower_line"] * 0.992
    pattern_id = f"BFLAG_4H_{pole['start_idx']}"

    vol_declining = flag.get("vol_declining", False)

    if last_close > flag["upper_line"] * CONFIRM_BUFFER_ABOVE:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 75 if (vol_ok and vol_declining) else 62
        desc = f"Bull flag breakout — target ${target:,.0f}"
    elif last_close < flag["lower_line"] * CONFIRM_BUFFER_BELOW:
        state = PatternState.FAILED
        confidence = 58
        vol_ok = False
        desc = f"Bull flag FAILED — breakdown below flag support"
    else:
        state = PatternState.FORMING
        confidence = 50
        vol_ok = vol_declining
        desc = f"Bull flag forming — consolidating after {pole['return_pct']:.1%} impulse"

    return PatternDetection(
        pattern_name="BULL_FLAG",
        tf="4H",
        direction="bullish",
        state=state,
        confidence=confidence,
        candles_span=flag["end_idx"] - pole["start_idx"],
        volume_confirmed=vol_ok,
        key_levels={
            "pole_top": round(pole["end_price"], 1),
            "pole_bottom": round(pole["start_price"], 1),
            "flag_upper": round(flag["upper_line"], 1),
            "flag_lower": round(flag["lower_line"], 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_bear_flag(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Bear Flag: sharp drop + slight upward-drifting consolidation."""
    closed = candles[:-1]
    if not closed:
        return None

    pole = _find_pole(candles, "bearish")
    if pole is None:
        return None

    flag = _find_flag_channel(candles, pole["start_idx"], pole["end_idx"], "bearish")
    if flag is None:
        return None

    last_close = closed[-1]["close"]
    target = pole["end_price"] - (pole["start_price"] - pole["end_price"]) * TARGET_CAP
    stop = flag["upper_line"] * 1.01
    pattern_id = f"BFLAG_4H_{pole['start_idx']}"

    vol_declining = flag.get("vol_declining", False)

    if last_close < flag["lower_line"] * CONFIRM_BUFFER_BELOW:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 75 if (vol_ok and vol_declining) else 62
        desc = f"Bear flag breakdown — target ${target:,.0f}"
    elif last_close > flag["upper_line"] * CONFIRM_BUFFER_ABOVE:
        state = PatternState.FAILED
        confidence = 58
        vol_ok = False
        desc = f"Bear flag FAILED — breakout above flag resistance"
    else:
        state = PatternState.FORMING
        confidence = 50
        vol_ok = vol_declining
        desc = f"Bear flag forming — consolidating after {pole['return_pct']:.1%} drop"

    return PatternDetection(
        pattern_name="BEAR_FLAG",
        tf="4H",
        direction="bearish",
        state=state,
        confidence=confidence,
        candles_span=flag["end_idx"] - pole["start_idx"],
        volume_confirmed=vol_ok,
        key_levels={
            "pole_top": round(pole["start_price"], 1),
            "pole_bottom": round(pole["end_price"], 1),
            "flag_upper": round(flag["upper_line"], 1),
            "flag_lower": round(flag["lower_line"], 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_bull_pennant(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Bull Pennant: sharp rise + tight converging consolidation."""
    closed = candles[:-1]
    if not closed:
        return None

    pole = _find_pole(candles, "bullish")
    if pole is None:
        return None

    flag = _find_flag_channel(
        candles, pole["start_idx"], pole["end_idx"], "bullish",
        min_candles=PENNANT_MIN_CANDLES, max_candles=PENNANT_MAX_CANDLES,
        converging=True,
    )
    if flag is None:
        return None

    last_close = closed[-1]["close"]
    target = pole["end_price"] + (pole["end_price"] - pole["start_price"])
    stop = flag["lower_line"] * 0.99
    pattern_id = f"BPEN_4H_{pole['start_idx']}"

    vol_declining = flag.get("vol_declining", False)

    if last_close > flag["upper_line"] * CONFIRM_BUFFER_ABOVE:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 72 if (vol_ok and vol_declining) else 58
        desc = f"Bull pennant breakout — target ${target:,.0f}"
    elif last_close < flag["lower_line"] * CONFIRM_BUFFER_BELOW:
        state = PatternState.FAILED
        confidence = 54
        vol_ok = False
        desc = f"Bull pennant FAILED — breakdown below support"
    else:
        state = PatternState.FORMING
        confidence = 48
        vol_ok = vol_declining
        desc = f"Bull pennant forming — tight consolidation after impulse"

    return PatternDetection(
        pattern_name="BULL_PENNANT",
        tf="4H",
        direction="bullish",
        state=state,
        confidence=confidence,
        candles_span=flag["end_idx"] - pole["start_idx"],
        volume_confirmed=vol_ok,
        key_levels={
            "pole_top": round(pole["end_price"], 1),
            "pole_bottom": round(pole["start_price"], 1),
            "pennant_upper": round(flag["upper_line"], 1),
            "pennant_lower": round(flag["lower_line"], 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )


def detect_bear_pennant(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """Bear Pennant: sharp drop + tight converging consolidation."""
    closed = candles[:-1]
    if not closed:
        return None

    pole = _find_pole(candles, "bearish")
    if pole is None:
        return None

    flag = _find_flag_channel(
        candles, pole["start_idx"], pole["end_idx"], "bearish",
        min_candles=PENNANT_MIN_CANDLES, max_candles=PENNANT_MAX_CANDLES,
        converging=True,
    )
    if flag is None:
        return None

    last_close = closed[-1]["close"]
    target = pole["end_price"] - (pole["start_price"] - pole["end_price"])
    stop = flag["upper_line"] * 1.01
    pattern_id = f"BPEN_4H_{pole['start_idx']}"

    vol_declining = flag.get("vol_declining", False)

    if last_close < flag["lower_line"] * CONFIRM_BUFFER_BELOW:
        state = PatternState.CONFIRMED
        vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
        confidence = 72 if (vol_ok and vol_declining) else 58
        desc = f"Bear pennant breakdown — target ${target:,.0f}"
    elif last_close > flag["upper_line"] * CONFIRM_BUFFER_ABOVE:
        state = PatternState.FAILED
        confidence = 54
        vol_ok = False
        desc = f"Bear pennant FAILED — breakout above resistance"
    else:
        state = PatternState.FORMING
        confidence = 48
        vol_ok = vol_declining
        desc = f"Bear pennant forming — tight consolidation after drop"

    return PatternDetection(
        pattern_name="BEAR_PENNANT",
        tf="4H",
        direction="bearish",
        state=state,
        confidence=confidence,
        candles_span=flag["end_idx"] - pole["start_idx"],
        volume_confirmed=vol_ok,
        key_levels={
            "pole_top": round(pole["start_price"], 1),
            "pole_bottom": round(pole["end_price"], 1),
            "pennant_upper": round(flag["upper_line"], 1),
            "pennant_lower": round(flag["lower_line"], 1),
            "target": round(target, 1),
            "stop": round(stop, 1),
        },
        description=desc,
        invalidation_price=round(stop, 1),
        btc_price=round(last_close, 1),
        pattern_id=pattern_id,
    )
