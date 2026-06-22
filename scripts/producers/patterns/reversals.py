"""
reversals.py — Double Top, Double Bottom, Head & Shoulders, Inverse H&S.

Tier 1: Double Top, Double Bottom
Tier 2: Head & Shoulders, Inverse Head & Shoulders
"""
from typing import List, Dict, Optional
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
    second_peak_lower_volume,
)
from config import (
    PEAK_TOLERANCE, DOUBLE_MIN_SEPARATION, VALLEY_DEPTH,
    SHOULDER_HEIGHT_TOLERANCE, SHOULDER_TIME_TOLERANCE,
    CONFIRM_BUFFER_ABOVE, CONFIRM_BUFFER_BELOW,
    MIN_PATTERN_AMPLITUDE,
)


def detect_double_top(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Double Top: two peaks at similar price, separated by a valley.

    CONFIRMED: close below neckline (valley low).
    FAILED: close above average of two peaks.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_highs) < 2:
        return None

    # Scan recent swing highs for two within tolerance
    recent_highs = swing_highs[-6:] if len(swing_highs) >= 6 else swing_highs

    for i in range(len(recent_highs) - 1):
        for j in range(i + 1, len(recent_highs)):
            h1, h2 = recent_highs[i], recent_highs[j]
            # Price tolerance
            avg_peak = (h1["price"] + h2["price"]) / 2
            if abs(h1["price"] - h2["price"]) / avg_peak > PEAK_TOLERANCE:
                continue
            # Separation
            if h2["idx"] - h1["idx"] < DOUBLE_MIN_SEPARATION:
                continue

            # Find valley between them
            valley_candles = [
                c for c in closed
                if h1["idx"] < closed.index(c) < h2["idx"]
            ]
            if not valley_candles:
                continue
            valley_low = min(c["low"] for c in valley_candles)
            valley_depth = (avg_peak - valley_low) / avg_peak
            if valley_depth < VALLEY_DEPTH:
                continue

            # Found a valid double top
            last_close = closed[-1]["close"]
            target = valley_low - (avg_peak - valley_low)
            stop = avg_peak * 1.01
            pattern_id = f"DTOP_4H_{h1['idx']}"

            vol_divergence = second_peak_lower_volume(candles, h1["idx"], h2["idx"])

            if last_close < valley_low * CONFIRM_BUFFER_BELOW:
                state = PatternState.CONFIRMED
                confidence = 80 if vol_divergence else 67
                vol_ok = vol_divergence
                desc = f"Double top confirmed — breakdown below ${valley_low:,.0f} neckline"
            elif last_close > avg_peak * CONFIRM_BUFFER_ABOVE:
                state = PatternState.FAILED
                confidence = 72
                vol_ok = False
                desc = f"Double top FAILED — breakout above ${avg_peak:,.0f} (bullish counter-signal)"
            else:
                state = PatternState.FORMING
                confidence = 55 if vol_divergence else 45
                vol_ok = vol_divergence
                desc = f"Double top forming — second peak at ${h2['price']:,.0f}"

            return PatternDetection(
                pattern_name="DOUBLE_TOP",
                tf="4H",
                direction="bearish",
                state=state,
                confidence=confidence,
                candles_span=h2["idx"] - h1["idx"],
                volume_confirmed=vol_ok,
                key_levels={
                    "peak1": round(h1["price"], 1),
                    "peak2": round(h2["price"], 1),
                    "neckline": round(valley_low, 1),
                    "target": round(target, 1),
                    "stop": round(stop, 1),
                },
                description=desc,
                invalidation_price=round(stop, 1),
                btc_price=round(last_close, 1),
                pattern_id=pattern_id,
            )

    return None


def detect_double_bottom(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Double Bottom: two troughs at similar price, separated by a peak.

    CONFIRMED: close above neckline (peak high).
    FAILED: close below lower of two troughs.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_lows) < 2:
        return None

    recent_lows = swing_lows[-6:] if len(swing_lows) >= 6 else swing_lows

    for i in range(len(recent_lows) - 1):
        for j in range(i + 1, len(recent_lows)):
            l1, l2 = recent_lows[i], recent_lows[j]
            avg_trough = (l1["price"] + l2["price"]) / 2
            if abs(l1["price"] - l2["price"]) / avg_trough > PEAK_TOLERANCE:
                continue
            if l2["idx"] - l1["idx"] < DOUBLE_MIN_SEPARATION:
                continue

            # Find peak between them
            peak_candles = [
                c for c in closed
                if l1["idx"] < closed.index(c) < l2["idx"]
            ]
            if not peak_candles:
                continue
            peak_high = max(c["high"] for c in peak_candles)
            peak_rise = (peak_high - avg_trough) / avg_trough
            if peak_rise < VALLEY_DEPTH:
                continue

            last_close = closed[-1]["close"]
            target = peak_high + (peak_high - avg_trough)
            stop = min(l1["price"], l2["price"]) * 0.99
            pattern_id = f"DBOT_4H_{l1['idx']}"

            # Volume: second trough should show exhaustion (lower vol)
            vol_exhaustion = candles[l2["idx"]]["volume"] < candles[l1["idx"]]["volume"]

            if last_close > peak_high * CONFIRM_BUFFER_ABOVE:
                state = PatternState.CONFIRMED
                vol_ok = volume_confirms_breakout(candles, len(closed) - 1, avg_volume)
                confidence = 80 if (vol_exhaustion or vol_ok) else 67
                desc = f"Double bottom confirmed — breakout above ${peak_high:,.0f} neckline"
            elif last_close < min(l1["price"], l2["price"]) * CONFIRM_BUFFER_BELOW:
                state = PatternState.FAILED
                confidence = 72
                vol_ok = False
                desc = f"Double bottom FAILED — breakdown below ${avg_trough:,.0f} (bearish counter-signal)"
            else:
                state = PatternState.FORMING
                confidence = 55 if vol_exhaustion else 45
                vol_ok = vol_exhaustion
                desc = f"Double bottom forming — second trough at ${l2['price']:,.0f}"

            return PatternDetection(
                pattern_name="DOUBLE_BOTTOM",
                tf="4H",
                direction="bullish",
                state=state,
                confidence=confidence,
                candles_span=l2["idx"] - l1["idx"],
                volume_confirmed=vol_ok,
                key_levels={
                    "trough1": round(l1["price"], 1),
                    "trough2": round(l2["price"], 1),
                    "neckline": round(peak_high, 1),
                    "target": round(target, 1),
                    "stop": round(stop, 1),
                },
                description=desc,
                invalidation_price=round(stop, 1),
                btc_price=round(last_close, 1),
                pattern_id=pattern_id,
            )

    return None


def detect_head_and_shoulders(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Head & Shoulders (Top): three peaks — left shoulder, higher head, right shoulder.

    Most studied reversal pattern. 63-83% completion rate.
    CONFIRMED: close below neckline connecting the two troughs.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_highs) < 3:
        return None

    # Need 3 consecutive swing highs
    recent_highs = swing_highs[-8:] if len(swing_highs) >= 8 else swing_highs
    if len(recent_highs) < 3:
        return None

    for i in range(len(recent_highs) - 2):
        ls = recent_highs[i]       # left shoulder
        head = recent_highs[i + 1]  # head
        rs = recent_highs[i + 2]    # right shoulder

        # Head must be highest
        if head["price"] <= ls["price"] or head["price"] <= rs["price"]:
            continue

        # Shoulder symmetry: RS within 10% of LS height
        ls_height = head["price"] - ls["price"]
        rs_height = head["price"] - rs["price"]
        if ls_height <= 0:
            continue
        if abs(rs_height - ls_height) / ls_height > SHOULDER_HEIGHT_TOLERANCE:
            continue

        # Time symmetry: gaps within 40%
        ls_to_head = head["idx"] - ls["idx"]
        head_to_rs = rs["idx"] - head["idx"]
        if ls_to_head <= 0 or head_to_rs <= 0:
            continue
        time_ratio = abs(ls_to_head - head_to_rs) / max(ls_to_head, head_to_rs)
        if time_ratio > SHOULDER_TIME_TOLERANCE:
            continue

        # Find neckline: connect the two troughs between LS-head and head-RS
        troughs_between = [l for l in swing_lows if ls["idx"] < l["idx"] < rs["idx"]]
        if len(troughs_between) < 2:
            continue
        troughs_between.sort(key=lambda x: x["idx"])

        # Find trough between LS and head
        t1 = None
        for t in troughs_between:
            if t["idx"] < head["idx"]:
                t1 = t
        # Find trough between head and RS
        t2 = None
        for t in troughs_between:
            if t["idx"] > head["idx"]:
                t2 = t
                break

        if not t1 or not t2:
            continue

        # Neckline = lower of the two troughs (conservative)
        neckline = min(t1["price"], t2["price"])

        # Amplitude check
        amplitude = (head["price"] - neckline) / head["price"]
        if amplitude < MIN_PATTERN_AMPLITUDE:
            continue

        last_close = closed[-1]["close"]
        target = neckline - (head["price"] - neckline)
        stop = head["price"] * 1.01
        pattern_id = f"HS_4H_{ls['idx']}"

        # Volume: right shoulder should be on lower volume than left
        vol_divergence = candles[rs["idx"]]["volume"] < candles[ls["idx"]]["volume"]

        if last_close < neckline * CONFIRM_BUFFER_BELOW:
            state = PatternState.CONFIRMED
            confidence = 83 if vol_divergence else 70
            vol_ok = vol_divergence
            desc = f"H&S top confirmed — breakdown below ${neckline:,.0f} neckline"
        elif last_close > head["price"] * CONFIRM_BUFFER_ABOVE:
            state = PatternState.FAILED
            confidence = 78  # Failed H&S is a strong bullish signal
            vol_ok = False
            desc = f"H&S top FAILED — breakout above head (strong bullish counter-signal)"
        else:
            state = PatternState.FORMING
            confidence = 55 if vol_divergence else 45
            vol_ok = vol_divergence
            desc = f"H&S top forming — right shoulder at ${rs['price']:,.0f}"

        return PatternDetection(
            pattern_name="HEAD_AND_SHOULDERS",
            tf="4H",
            direction="bearish",
            state=state,
            confidence=confidence,
            candles_span=rs["idx"] - ls["idx"],
            volume_confirmed=vol_ok,
            key_levels={
                "left_shoulder": round(ls["price"], 1),
                "head": round(head["price"], 1),
                "right_shoulder": round(rs["price"], 1),
                "neckline": round(neckline, 1),
                "target": round(target, 1),
                "stop": round(stop, 1),
            },
            description=desc,
            invalidation_price=round(stop, 1),
            btc_price=round(last_close, 1),
            pattern_id=pattern_id,
        )

    return None


def detect_inverse_head_and_shoulders(
    candles: List[Dict],
    swing_highs: List[Dict],
    swing_lows: List[Dict],
    avg_volume: float,
) -> Optional[PatternDetection]:
    """
    Inverse Head & Shoulders: three troughs — left shoulder, deeper head, right shoulder.

    CONFIRMED: close above neckline on above-avg volume.
    """
    closed = candles[:-1]
    if not closed:
        return None

    if len(swing_lows) < 3:
        return None

    recent_lows = swing_lows[-8:] if len(swing_lows) >= 8 else swing_lows
    if len(recent_lows) < 3:
        return None

    for i in range(len(recent_lows) - 2):
        ls = recent_lows[i]        # left shoulder (trough)
        head = recent_lows[i + 1]  # head (deepest trough)
        rs = recent_lows[i + 2]    # right shoulder

        # Head must be deepest (lowest price)
        if head["price"] >= ls["price"] or head["price"] >= rs["price"]:
            continue

        # Shoulder symmetry
        ls_depth = ls["price"] - head["price"]
        rs_depth = rs["price"] - head["price"]
        if ls_depth <= 0:
            continue
        if abs(rs_depth - ls_depth) / ls_depth > SHOULDER_HEIGHT_TOLERANCE:
            continue

        # Time symmetry
        ls_to_head = head["idx"] - ls["idx"]
        head_to_rs = rs["idx"] - head["idx"]
        if ls_to_head <= 0 or head_to_rs <= 0:
            continue
        time_ratio = abs(ls_to_head - head_to_rs) / max(ls_to_head, head_to_rs)
        if time_ratio > SHOULDER_TIME_TOLERANCE:
            continue

        # Neckline: connect peaks between troughs
        peaks_between = [h for h in swing_highs if ls["idx"] < h["idx"] < rs["idx"]]
        if len(peaks_between) < 2:
            continue
        peaks_between.sort(key=lambda x: x["idx"])

        t1 = None
        for p in peaks_between:
            if p["idx"] < head["idx"]:
                t1 = p
        t2 = None
        for p in peaks_between:
            if p["idx"] > head["idx"]:
                t2 = p
                break

        if not t1 or not t2:
            continue

        neckline = max(t1["price"], t2["price"])
        amplitude = (neckline - head["price"]) / neckline
        if amplitude < MIN_PATTERN_AMPLITUDE:
            continue

        last_close = closed[-1]["close"]
        target = neckline + (neckline - head["price"])
        stop = head["price"] * 0.99
        pattern_id = f"IHS_4H_{ls['idx']}"

        # Volume: right shoulder on higher volume = accumulation
        vol_expansion = candles[rs["idx"]]["volume"] > candles[ls["idx"]]["volume"]
        vol_ok = vol_expansion

        if last_close > neckline * CONFIRM_BUFFER_ABOVE:
            state = PatternState.CONFIRMED
            confidence = 83 if vol_expansion else 70
            desc = f"Inverse H&S confirmed — breakout above ${neckline:,.0f} neckline"
        elif last_close < head["price"] * CONFIRM_BUFFER_BELOW:
            state = PatternState.FAILED
            confidence = 78
            vol_ok = False
            desc = f"Inverse H&S FAILED — breakdown below head (strong bearish counter-signal)"
        else:
            state = PatternState.FORMING
            confidence = 55 if vol_expansion else 45
            desc = f"Inverse H&S forming — right shoulder at ${rs['price']:,.0f}"

        return PatternDetection(
            pattern_name="INVERSE_HEAD_AND_SHOULDERS",
            tf="4H",
            direction="bullish",
            state=state,
            confidence=confidence,
            candles_span=rs["idx"] - ls["idx"],
            volume_confirmed=vol_ok,
            key_levels={
                "left_shoulder": round(ls["price"], 1),
                "head": round(head["price"], 1),
                "right_shoulder": round(rs["price"], 1),
                "neckline": round(neckline, 1),
                "target": round(target, 1),
                "stop": round(stop, 1),
            },
            description=desc,
            invalidation_price=round(stop, 1),
            btc_price=round(last_close, 1),
            pattern_id=pattern_id,
        )

    return None
