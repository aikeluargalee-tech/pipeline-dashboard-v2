"""
complex.py — Cup & Handle and Rounding Bottom detection.

Tier 3 patterns. Run on 1D candles only.
Cup & Handle: multi-week U-shaped bottom + handle consolidation.
Rounding Bottom: slow gradual arc, highest completion rate (89%) but very rare.
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
from volume import volume_mirror_bottom, volume_confirms_breakout
from config import (
    RIM_TOLERANCE, CUP_MIN_DEPTH, HANDLE_RETRACE, CUP_MIN_SPAN,
    CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW, MIN_PATTERN_AMPLITUDE, TARGET_CAP,
)


def _is_stale_breakout(candles, rim_level, max_candles=5):
    """
    Check if the breakout above rim_level happened too long ago.
    Returns True if the first crossover was > max_candles candles ago.
    Used to mark slow-forming patterns as LATE — logged, not alerted.
    """
    closed = candles[:-1]
    for i, c in enumerate(closed):
        if c["close"] > rim_level * CONFIRM_BUFFER_ABOVE:
            candles_since = len(closed) - i
            return candles_since > max_candles
    return False  # never crossed — not stale, genuinely new breakout


def detect_cup_and_handle(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Cup & Handle: rounded U-shaped bottom + small downward-drifting handle.

    Run on 1D candles only (too slow-forming for 4H).
    """
    closed = candles[:-1]
    if not closed or len(closed) < CUP_MIN_SPAN + 25:
        return None

    n = len(closed)

    # Scan for cup formations
    for start_idx in range(0, n - CUP_MIN_SPAN - 10):
        end_idx = start_idx + CUP_MIN_SPAN
        if end_idx >= n:
            break

        segment = closed[start_idx:end_idx + 1]
        seg_highs = [c["high"] for c in segment]
        seg_lows = [c["low"] for c in segment]

        # Find left rim (high near start) and right rim (high near end)
        left_quarter = segment[:max(1, len(segment) // 4)]
        right_quarter = segment[-max(1, len(segment) // 4):]

        left_rim = max(c["high"] for c in left_quarter)
        right_rim = max(c["high"] for c in right_quarter)

        # Rims must be within tolerance
        if abs(left_rim - right_rim) / max(left_rim, 1) > RIM_TOLERANCE:
            continue

        rim_level = (left_rim + right_rim) / 2

        # Cup bottom = lowest point
        cup_bottom = min(seg_lows)
        cup_depth = (rim_level - cup_bottom) / rim_level

        if cup_depth < CUP_MIN_DEPTH:
            continue

        # Rounded test: middle third must stay near bottom (not V-shaped)
        third = len(segment) // 3
        mid_third = segment[third : 2 * third]
        if not mid_third:
            continue
        mid_avg = sum(c["close"] for c in mid_third) / len(mid_third)
        if mid_avg > cup_bottom * 1.08:
            continue  # too V-shaped

        # Handle: after right rim, 5-25 candles of slight downward drift
        handle_start = end_idx + 1
        handle_end_candidates = min(handle_start + 25, n)

        for handle_end in range(handle_start + 5, handle_end_candidates):
            handle = closed[handle_start:handle_end]
            if len(handle) < 5:
                continue

            handle_highs = [c["high"] for c in handle]
            handle_lows = [c["low"] for c in handle]
            handle_high = max(handle_highs)
            handle_low = min(handle_lows)

            # Handle must stay below rim
            if handle_high > rim_level * 1.02:
                continue

            # Handle should drift slightly downward
            handle_retrace = (rim_level - handle_low) / (rim_level - cup_bottom)
            if handle_retrace > HANDLE_RETRACE:
                continue

            # Volume pattern
            vol_mirror = volume_mirror_bottom(candles, start_idx, end_idx)

            last_close = closed[-1]["close"]
            target = rim_level + (rim_level - cup_bottom) * TARGET_CAP
            stop = handle_low * 0.99
            pattern_id = f"CNH_1D_{start_idx}"

            if last_close > rim_level * CONFIRM_BUFFER_ABOVE:
                if _is_stale_breakout(candles, rim_level):
                    state = PatternState.LATE
                    confidence = 40  # reduced — breakout already happened
                    vol_ok = False
                    desc = f"Cup & Handle LATE — breakout above ${rim_level:,.0f} rim (already confirmed)"
                else:
                    state = PatternState.CONFIRMED
                    vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
                    confidence = 75 if (vol_ok and vol_mirror) else 61
                    desc = f"Cup & Handle breakout above ${rim_level:,.0f} rim"
            elif last_close < handle_low * CONFIRM_BUFFER_BELOW:
                state = PatternState.FAILED
                confidence = 55
                vol_ok = False
                desc = f"Cup & Handle FAILED — breakdown below handle"
            else:
                state = PatternState.FORMING
                confidence = 50
                vol_ok = vol_mirror
                desc = f"Cup & Handle forming — handle at ${handle_low:,.0f}"

            return PatternDetection(
                pattern_name="CUP_AND_HANDLE",
                tf="1D",
                direction="bullish",
                state=state,
                confidence=confidence,
                candles_span=handle_end - start_idx,
                volume_confirmed=vol_ok,
                key_levels={
                    "left_rim": round(left_rim, 1),
                    "right_rim": round(right_rim, 1),
                    "rim_level": round(rim_level, 1),
                    "cup_bottom": round(cup_bottom, 1),
                    "handle_low": round(handle_low, 1),
                    "target": round(target, 1),
                    "stop": round(stop, 1),
                },
                description=desc,
                invalidation_price=round(stop, 1),
                btc_price=round(last_close, 1),
                pattern_id=pattern_id,
            )

    return None


def detect_rounding_bottom(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Rounding Bottom (Saucer): slow gradual arc from downtrend to uptrend.
    89% completion rate — highest of all patterns but extremely rare.

    Fits a degree-2 polynomial to find upward-opening parabolas.
    Run on 1D candles only.
    """
    closed = candles[:-1]
    if not closed:
        return None

    n = len(closed)
    # Scan at three window sizes: 100, 150, 200 candles
    for window in [100, 150, 200]:
        if n < window + 10:
            continue

        for start_idx in range(0, n - window, max(1, window // 4)):
            end_idx = start_idx + window
            if end_idx >= n:
                break

            segment = closed[start_idx:end_idx]

            # Fit degree-2 polynomial
            x = np.arange(len(segment))
            y = np.array([c["close"] for c in segment])
            try:
                coeffs = np.polyfit(x, y, 2)
            except np.linalg.LinAlgError:
                continue

            a, b, c = coeffs

            # Positive 'a' = upward-opening parabola = rounding bottom
            if a <= 0:
                continue

            # Gradual check: no 10-candle window drops > 8%
            max_drop = 0.0
            for i in range(0, len(segment) - 9, 5):
                drop = (min(segment[i:i+10], key=lambda c: c["low"])["low"]
                        - segment[i]["high"]) / segment[i]["high"]
                max_drop = min(max_drop, drop)
            if max_drop < -0.08:
                continue

            # Volume mirror
            vol_mirror = volume_mirror_bottom(candles, start_idx, end_idx)

            # Rim: max price at start or end of segment
            left_max = max(c["high"] for c in segment[:max(1, len(segment)//5)])
            right_max = max(c["high"] for c in segment[-max(1, len(segment)//5):])
            rim_level = (left_max + right_max) / 2

            # Cup bottom = lowest close
            cup_bottom = min(c["close"] for c in segment)
            depth = (rim_level - cup_bottom) / rim_level
            if depth < 0.08:
                continue

            last_close = closed[-1]["close"]
            target = rim_level + (rim_level - cup_bottom) * TARGET_CAP
            stop = cup_bottom * 0.98
            pattern_id = f"RBOT_1D_{start_idx}"

            if last_close > rim_level * CONFIRM_BUFFER_ABOVE:
                if _is_stale_breakout(candles, rim_level):
                    state = PatternState.LATE
                    vol_ok = False
                    confidence = 45
                    desc = f"Rounding bottom LATE — breakout above ${rim_level:,.0f} (already confirmed)"
                else:
                    state = PatternState.CONFIRMED
                    vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
                    confidence = 89 if vol_mirror else 75
                    desc = f"Rounding bottom confirmed — breakout above ${rim_level:,.0f}"
            else:
                state = PatternState.FORMING
                confidence = 60 if vol_mirror else 45
                vol_ok = vol_mirror
                desc = f"Rounding bottom forming — gradual accumulation arc"

            return PatternDetection(
                pattern_name="ROUNDING_BOTTOM",
                tf="1D",
                direction="bullish",
                state=state,
                confidence=confidence,
                candles_span=window,
                volume_confirmed=vol_ok,
                key_levels={
                    "rim_level": round(rim_level, 1),
                    "cup_bottom": round(cup_bottom, 1),
                    "target": round(target, 1),
                    "stop": round(stop, 1),
                },
                description=desc,
                invalidation_price=round(stop, 1),
                btc_price=round(last_close, 1),
                pattern_id=pattern_id,
            )

    return None
