#!/usr/bin/env python3
"""
Volume Profile (VRVP/POC) analyzer for BTC/USDT
Standalone script — fetches 1H candles from Bitget public API,
builds volume-at-price profile, and identifies POC, VAH, VAL, HVN, LVN.

Usage:
    ~/.hermes/hermes-agent/.venv/bin/python3 ~/btc-volume-profile/scripts/profile.py
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

# ── Constants ──────────────────────────────────────────────────────────────
API_URL = (
    "https://api.bitget.com/api/v2/spot/market/candles"
    "?symbol=BTCUSDT&granularity=1h&limit=200"
)
NUM_BINS = 50
VA_PCT = 0.70
HVN_FACTOR = 1.5
LVN_FACTOR = 0.5

OUTPUT_DIR = os.path.expanduser("~/pipeline-dashboard V2/data")
JSONL_PATH = os.path.join(OUTPUT_DIR, "profile.jsonl")

# ── Fetch ──────────────────────────────────────────────────────────────────
def fetch_candles():
    """Fetch 200 1H BTC/USDT candles from Bitget public REST API."""
    req = urllib.request.Request(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0 (hermes-volume-profile)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.loads(resp.read())
    except Exception as e:
        print(f"ERROR: Failed to fetch candles: {e}", file=sys.stderr)
        sys.exit(1)

    if raw.get("code") != "00000":
        print(f"ERROR: API returned error: {raw}", file=sys.stderr)
        sys.exit(1)

    candles_raw = raw["data"]
    candles = []
    for c in candles_raw:
        candles.append({
            "ts": int(c[0]),
            "open": float(c[1]),
            "high": float(c[2]),
            "low": float(c[3]),
            "close": float(c[4]),
            "base_vol": float(c[5]),   # BTC volume
        })
    return candles


# ── Volume Profile Engine ──────────────────────────────────────────────────
def build_profile(candles):
    """
    Build volume-at-price profile from candle list.
    Returns dict with bins, poc, vah/val, hvn/lvn, shape, current_price.
    """
    # Global price range
    all_high = max(c["high"] for c in candles)
    all_low  = min(c["low"] for c in candles)
    price_range = all_high - all_low
    bin_size = price_range / NUM_BINS

    # Initialize bins: (mid_price, low_edge, high_edge, volume)
    bins = []
    for i in range(NUM_BINS):
        low_edge  = all_low + i * bin_size
        high_edge = low_edge + bin_size
        mid_price = (low_edge + high_edge) / 2
        bins.append({"low": low_edge, "high": high_edge, "mid": mid_price, "vol": 0.0})

    # Distribute volume across bins
    for c in candles:
        candle_range = c["high"] - c["low"]
        if candle_range <= 0:
            # Flat candle — assign all volume to the bin containing its price
            for b in bins:
                if b["low"] <= c["low"] <= b["high"]:
                    b["vol"] += c["base_vol"]
                    break
            continue

        for b in bins:
            overlap_low  = max(b["low"], c["low"])
            overlap_high = min(b["high"], c["high"])
            if overlap_high > overlap_low:
                proportion = (overlap_high - overlap_low) / candle_range
                b["vol"] += c["base_vol"] * proportion

    total_vol = sum(b["vol"] for b in bins)
    if total_vol == 0:
        print("ERROR: Total volume is zero — cannot build profile.", file=sys.stderr)
        sys.exit(1)

    mean_vol = total_vol / NUM_BINS

    # POC — bin with highest volume
    sorted_by_vol = sorted(bins, key=lambda b: b["vol"], reverse=True)
    poc_bin = sorted_by_vol[0]
    poc = round(poc_bin["mid"])

    # Value Area — bins covering VA_PCT (70%) of total volume
    cumulative = 0.0
    va_bins = []
    for b in sorted_by_vol:
        va_bins.append(b)
        cumulative += b["vol"]
        if cumulative >= total_vol * VA_PCT:
            break

    vah = round(max(b["high"] for b in va_bins))
    val = round(min(b["low"] for b in va_bins))

    # HVN — bins > HVN_FACTOR × mean_vol
    hvn_bins = [b for b in bins if b["vol"] > HVN_FACTOR * mean_vol]
    hvn_bins.sort(key=lambda b: b["vol"], reverse=True)

    # LVN — bins < LVN_FACTOR × mean_vol
    lvn_bins = [b for b in bins if b["vol"] < LVN_FACTOR * mean_vol]
    lvn_bins.sort(key=lambda b: b["vol"])

    # Shape classification
    shape = classify_shape(bins, mean_vol, total_vol)

    # Current price = most recent candle close
    current_price = candles[-1]["close"]

    return {
        "poc": poc,
        "vah": vah,
        "val": val,
        "total_vol": total_vol,
        "mean_vol": mean_vol,
        "hvn": [round(b["mid"]) for b in hvn_bins],
        "lvn": [round(b["mid"]) for b in lvn_bins],
        "shape": shape,
        "price": round(current_price),
        "bins": bins,
        "poc_bin": poc_bin,
        "hvn_bins": hvn_bins,
        "lvn_bins": lvn_bins,
        "num_candles": len(candles),
        "price_range": price_range,
    }


def classify_shape(bins, mean_vol, total_vol):
    """
    Classify the volume profile shape:
      - 'normal': single dominant peak, bell-like
      - 'bimodal': two clear peaks separated by a valley
      - 'flat': no clear peak, volume evenly distributed
    """
    vols = [b["vol"] for b in bins]

    # Find local maxima (peaks)
    peaks = []
    for i in range(1, len(vols) - 1):
        if vols[i] > vols[i - 1] and vols[i] > vols[i + 1]:
            peaks.append({"idx": i, "vol": vols[i], "mid": bins[i]["mid"]})

    # Criterion 1: Flat — no peaks or max < 1.3× mean
    max_vol = max(vols)
    if len(peaks) == 0 or max_vol < 1.3 * mean_vol:
        return "flat"

    # Criterion 2: Bimodal — two peaks both > 0.55× max peak, separated by ≥3 bins
    peaks.sort(key=lambda p: p["vol"], reverse=True)
    if len(peaks) >= 2:
        p1, p2 = peaks[0], peaks[1]
        if p2["vol"] > 0.55 * p1["vol"] and abs(p2["idx"] - p1["idx"]) >= 3:
            # Check for a valley between them
            lo = min(p1["idx"], p2["idx"])
            hi = max(p1["idx"], p2["idx"])
            valley_min = min(vols[lo + 1 : hi])
            if valley_min < 0.7 * min(p1["vol"], p2["vol"]):
                return "bimodal"

    # Default: normal
    return "normal"


# ── Output ─────────────────────────────────────────────────────────────────
def format_output(profile):
    """Produce the human-readable output block."""
    poc  = profile["poc"]
    vah  = profile["vah"]
    val  = profile["val"]
    price = profile["price"]

    mkt_tz = timezone(timedelta(hours=8))  # MYT
    now = datetime.now(tz=mkt_tz)
    ts_display = now.strftime("%Y-%m-%d %H:%M MYT")

    # Distance calculations
    if price > 0:
        poc_dist = (price - poc) / price * 100
        vah_dist = (vah - price) / price * 100
        val_dist = (price - val) / price * 100  # positive = price above val
        val_dist_str = f"{val_dist:.1f}%"  # how far below

        if abs(poc_dist) < 0.05:
            poc_rel = "at POC"
        elif poc_dist > 0:
            poc_rel = f"below by -{poc_dist:.1f}%"
        else:
            poc_rel = f"above by +{abs(poc_dist):.1f}%"
    else:
        poc_rel = "N/A"
        vah_dist = val_dist_str = 0

    va_range = vah - val
    va_pct = (va_range / price * 100) if price > 0 else 0

    lines = []
    lines.append("═══════════════════════════════════════════")
    lines.append("  VOLUME PROFILE — BTC/USDT 1H")
    lines.append(f"  {ts_display} | {profile['num_candles']} candles")
    lines.append("═══════════════════════════════════════════")
    lines.append("")
    lines.append(f"  Current Price: ${price:,}")
    lines.append("")
    lines.append(f"  POC: ${poc:,} ({poc_rel})")
    lines.append(f"  VAH: ${vah:,} (above by +{vah_dist:.1f}%)" if vah > price else f"  VAH: ${vah:,} (below by {vah_dist:.1f}%)")
    lines.append(f"  VAL: ${val:,} (below by -{val_dist_str})")
    lines.append(f"  Value Area Range: ${va_range:,} ({va_pct:.1f}%)")
    lines.append("")

    # HVN
    lines.append("  High Volume Nodes (Acceptance):")
    if profile["hvn_bins"]:
        for b in profile["hvn_bins"]:
            multiplier = b["vol"] / profile["mean_vol"]
            mid = round(b["mid"])
            label = ""
            if mid == poc:
                label = "POC — maximum acceptance"
            elif multiplier > 2.5:
                label = f"strong shelf, {multiplier:.1f}× avg volume"
            else:
                label = f"support/resistance shelf, {multiplier:.1f}× avg volume"
            lines.append(f"    • ${mid:,} ({label})")
    else:
        lines.append("    (none)")
    lines.append("")

    # LVN
    lines.append("  Low Volume Nodes (Rejection/Vacuum):")
    if profile["lvn_bins"]:
        for b in profile["lvn_bins"]:
            multiplier = b["vol"] / profile["mean_vol"]
            mid = round(b["mid"])
            if mid > vah:
                tag = "thin zone above VAH — breakout point"
            elif mid < val:
                tag = "thin zone below VAL — breakdown point"
            else:
                tag = "gap — fast move expected"
            lines.append(f"    • ${mid:,} ({tag}, {multiplier:.1f}× avg volume)")
    else:
        lines.append("    (none)")
    lines.append("")

    # Shape
    shape = profile["shape"]
    lines.append(f"  Shape: {shape.capitalize()} distribution")
    if shape == "normal":
        lines.append(f"  Implication: Fair value at ${poc:,}")
        if abs((price - poc) / price) < 0.005 if price > 0 else False:
            lines.append("  Price at POC → range-bound, wait for VAH/VAL test")
        elif price > vah:
            lines.append("  Price above VAH → overbought, watch for mean reversion")
        elif price < val:
            lines.append("  Price below VAL → oversold, watch for mean reversion")
        else:
            lines.append("  Price in value area → range-bound, trade extremes")
    elif shape == "bimodal":
        lines.append("  Implication: Two competing fair values — consolidation or range expansion ahead")
        lines.append("  Watch for acceptance at either node")
    else:
        lines.append("  Implication: No clear consensus — transitional/indecisive market")
        lines.append("  Wait for a POC to emerge")
    lines.append("")

    return "\n".join(lines)


def write_jsonl(profile):
    """Append one JSONL record to the log file."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    mkt_tz = timezone(timedelta(hours=8))
    record = {
        "ts": datetime.now(tz=mkt_tz).strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "poc": profile["poc"],
        "vah": profile["vah"],
        "val": profile["val"],
        "hvn": profile["hvn"],
        "lvn": profile["lvn"],
        "shape": profile["shape"],
        "price": profile["price"],
    }
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(record) + "\n")


# ── Main ───────────────────────────────────────────────────────────────────
def main():
    candles = fetch_candles()
    profile = build_profile(candles)
    print(format_output(profile))
    write_jsonl(profile)
    print(f"(Logged to {JSONL_PATH})")


if __name__ == "__main__":
    main()
