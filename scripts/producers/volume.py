"""
volume.py — Volume signature validation for pattern confirmation.
Volume is additive — affects confidence, never gates detection.
"""
from typing import List, Dict, Any
from config import VOL_LOOKBACK, VOL_BREAKOUT_MULTIPLIER


def vol_avg(candles: List[Dict], lookback: int = VOL_LOOKBACK) -> float:
    """Average volume over last N closed candles."""
    closed = candles[:-1]  # exclude forming candle
    if len(closed) < lookback:
        lookback = len(closed)
    window = closed[-lookback:]
    if not window:
        return 0.0
    return sum(c["volume"] for c in window) / len(window)


def volume_confirms_breakout(
    candles: List[Dict],
    breakout_idx: int,
    avg_vol: float,
    multiplier: float = VOL_BREAKOUT_MULTIPLIER,
) -> bool:
    """Breakout candle volume >= multiplier * average volume."""
    if breakout_idx < 0 or breakout_idx >= len(candles):
        return False
    if avg_vol <= 0:
        return False
    return candles[breakout_idx]["volume"] >= avg_vol * multiplier


def volume_declines_through_pattern(
    candles: List[Dict], start_idx: int, end_idx: int
) -> bool:
    """Check if volume declines from first half to second half of pattern."""
    if start_idx >= end_idx or end_idx > len(candles):
        return False
    mid = (start_idx + end_idx) // 2
    if mid <= start_idx or end_idx <= mid:
        return False
    first_half = [candles[i]["volume"] for i in range(start_idx, mid)]
    second_half = [candles[i]["volume"] for i in range(mid, end_idx)]
    if not first_half or not second_half:
        return False
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    return avg_second < avg_first


def second_peak_lower_volume(
    candles: List[Dict], peak1_idx: int, peak2_idx: int
) -> bool:
    """Check if second peak has lower volume than first (distribution signal)."""
    try:
        return candles[peak2_idx]["volume"] < candles[peak1_idx]["volume"]
    except (IndexError, KeyError):
        return False


def volume_spike_on_candle(
    candles: List[Dict], idx: int, avg_vol: float, multiplier: float = 1.5
) -> bool:
    """Generic volume spike check on a specific candle."""
    if idx < 0 or idx >= len(candles) or avg_vol <= 0:
        return False
    return candles[idx]["volume"] >= avg_vol * multiplier


def volume_mirror_bottom(
    candles: List[Dict], start_idx: int, end_idx: int
) -> bool:
    """
    For rounding bottom: volume should mirror the shape.
    Second half volume > first half volume * 0.8.
    """
    if start_idx >= end_idx:
        return False
    mid = (start_idx + end_idx) // 2
    if mid <= start_idx or end_idx <= mid:
        return False
    first_half = [candles[i]["volume"] for i in range(start_idx, mid)]
    second_half = [candles[i]["volume"] for i in range(mid, end_idx)]
    if not first_half or not second_half:
        return False
    avg_first = sum(first_half) / len(first_half)
    avg_second = sum(second_half) / len(second_half)
    if avg_first <= 0:
        return False
    return avg_second > avg_first * 0.8
