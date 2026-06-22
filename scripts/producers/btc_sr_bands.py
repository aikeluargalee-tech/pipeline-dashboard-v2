#!/usr/bin/env python3
"""
BTC Multi-Timeframe Support & Resistance Band Detector (v2.0)
Fetches Binance klines, identifies S/R bands using multiple methods:
  1. Swing Highs/Lows (pivot points)
  2. Volume-at-Price clusters (volume profile)
  3. Round number psychological levels
  4. Recent range boundaries

Advanced features:
  - Multi-timeframe support (1H, 4H, 1D)
  - ATR-adjusted cluster tolerance
  - Level status tags (ACTIVE/FRESH/WEAKENED/BROKEN/CONFLUENCE)
  - Inverted S/R detection (broken levels flip)
  - Exponential decay weighting for touches
  - Standardized JSON output contract

No external dependencies — uses only Python stdlib + Binance public API.
"""

import json
import sys
import math
import urllib.request
import urllib.error
from datetime import datetime, timezone
from collections import defaultdict

# Timeframe-specific configurations
TIMEFRAME_CONFIG = {
    "1h": {
        "lookback": 72,  # 3 days
        "pivot_lookback": 3,
        "round_step": 500,
        "base_cluster_pct": 0.003,  # 0.3%
        "atr_period": 14,
        "decay_half_life": 15,  # bars
        "status_recent_window": 10,  # bars
    },
    "4h": {
        "lookback": 100,  # ~16 days
        "pivot_lookback": 5,
        "round_step": 1000,
        "base_cluster_pct": 0.005,  # 0.5%
        "atr_period": 14,
        "decay_half_life": 30,  # bars
        "status_recent_window": 10,  # bars
    },
    "1d": {
        "lookback": 90,  # 3 months
        "pivot_lookback": 8,
        "round_step": 2500,
        "base_cluster_pct": 0.010,  # 1.0%
        "atr_period": 14,
        "decay_half_life": 40,  # bars
        "status_recent_window": 10,  # bars
    },
}

SYMBOL = "BTCUSDT"

def fetch_klines(symbol=SYMBOL, interval="4h", limit=100):
    """Fetch OHLCV klines from Binance Futures API."""
    url = f"https://fapi.binance.com/fapi/v1/klines?symbol={symbol}&interval={interval}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "BTC-SR-Bands/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            klines = []
            for k in data:
                klines.append({
                    "open_time": k[0],
                    "open": float(k[1]),
                    "high": float(k[2]),
                    "low": float(k[3]),
                    "close": float(k[4]),
                    "volume": float(k[5]),  # base asset volume (BTC)
                    "quote_volume": float(k[7]),  # quote asset volume (USDT)
                    "close_time": k[6],
                })
            return klines
    except Exception as e:
        print(f"ERROR: Failed to fetch klines: {e}", file=sys.stderr)
        return []

def calc_atr(klines, period=14):
    """Calculate Average True Range (ATR)."""
    if len(klines) < period + 1:
        return 0
    
    tr_values = []
    for i in range(1, len(klines)):
        high = klines[i]["high"]
        low = klines[i]["low"]
        prev_close = klines[i-1]["close"]
        
        tr = max(
            high - low,
            abs(high - prev_close),
            abs(low - prev_close)
        )
        tr_values.append(tr)
    
    # Simple moving average of TR
    if len(tr_values) < period:
        return sum(tr_values) / len(tr_values) if tr_values else 0
    
    atr = sum(tr_values[-period:]) / period
    return atr

def find_swing_pivots(klines, lookback=5):
    """Find swing highs and lows using pivot point detection."""
    highs = []
    lows = []
    
    for i in range(lookback, len(klines) - lookback):
        # Swing High: current high is highest in window
        is_high = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and klines[j]["high"] >= klines[i]["high"]:
                is_high = False
                break
        if is_high:
            highs.append({
                "price": klines[i]["high"],
                "time": klines[i]["open_time"],
                "bar_index": i,
                "type": "swing_high",
                "volume": klines[i]["quote_volume"]
            })
        
        # Swing Low: current low is lowest in window
        is_low = True
        for j in range(i - lookback, i + lookback + 1):
            if j != i and klines[j]["low"] <= klines[i]["low"]:
                is_low = False
                break
        if is_low:
            lows.append({
                "price": klines[i]["low"],
                "time": klines[i]["open_time"],
                "bar_index": i,
                "type": "swing_low",
                "volume": klines[i]["quote_volume"]
            })
    
    return highs, lows

def volume_profile(klines, bin_size=500):
    """Build volume-at-price profile and find high-volume nodes (HVN)."""
    vol_bins = defaultdict(float)
    
    for k in klines:
        # Distribute volume across the candle's price range
        price_low = k["low"]
        price_high = k["high"]
        vol = k["quote_volume"]
        
        low_bin = int(price_low // bin_size) * bin_size
        high_bin = int(price_high // bin_size) * bin_size
        
        if low_bin == high_bin:
            vol_bins[low_bin] += vol
        else:
            # Distribute proportionally
            total_range = price_high - price_low
            for b in range(low_bin, high_bin + bin_size, bin_size):
                overlap_low = max(price_low, b)
                overlap_high = min(price_high, b + bin_size)
                if overlap_high > overlap_low:
                    fraction = (overlap_high - overlap_low) / total_range if total_range > 0 else 0
                    vol_bins[b] += vol * fraction
    
    # Sort by volume descending, find top clusters
    sorted_bins = sorted(vol_bins.items(), key=lambda x: x[1], reverse=True)
    
    # Get HVN (High Volume Nodes) — top 15 bins
    hvn = []
    for price, vol in sorted_bins[:15]:
        hvn.append({
            "price": price + bin_size / 2,  # center of bin
            "price_low": price,
            "price_high": price + bin_size,
            "volume": vol,
            "type": "hvn"
        })
    
    return hvn

def round_numbers(price_range_low, price_range_high, step=1000):
    """Generate psychological round number levels within the price range."""
    levels = []
    start = int(price_range_low // step) * step
    for p in range(start, int(price_range_high) + step, step):
        if price_range_low <= p <= price_range_high:
            levels.append({
                "price": float(p),
                "type": "round_number"
            })
    return levels

def cluster_levels(levels, tolerance_pct=0.005):
    """Cluster nearby price levels into bands using percentage-based tolerance."""
    if not levels:
        return []
    
    # Sort by price
    sorted_levels = sorted(levels, key=lambda x: x["price"])
    
    bands = []
    current_band = [sorted_levels[0]]
    
    for level in sorted_levels[1:]:
        # Check if within tolerance percentage of current band's average
        band_avg = sum(l["price"] for l in current_band) / len(current_band)
        tolerance = band_avg * tolerance_pct
        
        if level["price"] - current_band[0]["price"] <= tolerance:
            current_band.append(level)
        else:
            # Finalize current band
            band = _finalize_band(current_band)
            bands.append(band)
            current_band = [level]
    
    # Don't forget the last band
    if current_band:
        band = _finalize_band(current_band)
        bands.append(band)
    
    return bands

def _finalize_band(levels):
    """Compute band properties from a list of clustered levels."""
    prices = [l["price"] for l in levels]
    avg_price = sum(prices) / len(prices)
    
    # Count touches by type
    touches = len(levels)
    types = set(l.get("type", "unknown") for l in levels)
    
    # Volume (sum from HVN levels if available)
    total_vol = sum(l.get("volume", 0) for l in levels)
    
    # Get bar indices for decay calculation
    bar_indices = [l.get("bar_index", 0) for l in levels if "bar_index" in l]
    
    # Strength scoring
    strength = 0
    
    # Touches: more = stronger
    if touches >= 5:
        strength += 3
    elif touches >= 3:
        strength += 2
    elif touches >= 2:
        strength += 1
    
    # Volume confirmation
    if total_vol > 0:
        strength += 2
    
    # Multiple confirmation types
    if len(types) >= 3:
        strength += 3  # swing + volume + round number
    elif len(types) >= 2:
        strength += 2
    elif len(types) >= 1:
        strength += 1
    
    return {
        "center": round(avg_price, 2),
        "low": round(min(prices), 2),
        "high": round(max(prices), 2),
        "touches": touches,
        "types": sorted(types),
        "volume_usdt": round(total_vol, 2),
        "strength": strength,
        "strength_label": _strength_label(strength),
        "bar_indices": bar_indices,
    }

def _strength_label(strength):
    if strength >= 7:
        return "STRONG"
    elif strength >= 5:
        return "MODERATE"
    elif strength >= 3:
        return "WEAK"
    else:
        return "MINOR"

def apply_decay_weighting(bands, total_bars, half_life=30):
    """Apply exponential decay weighting to touches based on age."""
    for band in bands:
        if not band.get("bar_indices"):
            continue
        
        # Calculate decayed touch weight
        decayed_weight = 0
        for bar_idx in band["bar_indices"]:
            age = total_bars - bar_idx
            weight = math.exp(-age / half_life)
            decayed_weight += weight
        
        # Store decayed touches
        band["touches_decayed"] = round(decayed_weight, 2)
        
        # Adjust strength based on decayed touches
        original_strength = band["strength"]
        
        # Recalculate touch-based strength with decay
        if decayed_weight >= 4.0:
            decay_strength = 3
        elif decayed_weight >= 2.0:
            decay_strength = 2
        elif decayed_weight >= 1.0:
            decay_strength = 1
        else:
            decay_strength = 0
        
        # Get non-touch strength components
        vol_strength = 2 if band["volume_usdt"] > 0 else 0
        type_strength = 3 if len(band["types"]) >= 3 else (2 if len(band["types"]) >= 2 else 1)
        
        # New strength with decay
        band["strength"] = decay_strength + vol_strength + type_strength
        band["strength_label"] = _strength_label(band["strength"])
    
    return bands

def classify_bands(bands, current_price):
    """Classify each band as SUPPORT or RESISTANCE relative to current price."""
    for band in bands:
        if band["center"] < current_price:
            band["role"] = "SUPPORT"
            band["distance_pct"] = round((current_price - band["center"]) / current_price * 100, 2)
        else:
            band["role"] = "RESISTANCE"
            band["distance_pct"] = round((band["center"] - current_price) / current_price * 100, 2)
    return bands

def classify_level_status(band, klines, recent_window=10):
    """
    Classify level status:
    - FRESH: never tested (no recent touches)
    - ACTIVE: tested recently (within recent_window bars)
    - WEAKENED: tested 3+ times
    - BROKEN: price closed through with volume
    - CONFLUENCE: multiple confirmation sources
    """
    total_bars = len(klines)
    recent_touches = [i for i in band.get("bar_indices", []) if i >= total_bars - recent_window]
    
    # Check if broken (price closed through level with volume)
    is_broken = False
    for k in klines[-recent_window:]:
        # Check if candle closed through the band
        if band["role"] == "SUPPORT":
            # Support broken if close is below band low
            if k["close"] < band["low"] and k["quote_volume"] > 0:
                is_broken = True
                break
        else:
            # Resistance broken if close is above band high
            if k["close"] > band["high"] and k["quote_volume"] > 0:
                is_broken = True
                break
    
    # Determine status
    if is_broken:
        return "BROKEN"
    elif len(recent_touches) > 0:
        if band["touches"] >= 3:
            return "WEAKENED"
        else:
            return "ACTIVE"
    elif len(band["types"]) >= 3:
        return "CONFLUENCE"
    elif band["touches"] == 0:
        return "FRESH"
    else:
        return "ACTIVE"

def detect_inverted_sr(bands, klines):
    """
    Detect inverted S/R levels:
    - Broken support becomes resistance
    - Broken resistance becomes support
    """
    inverted = []
    
    for band in bands:
        if band.get("status") == "BROKEN":
            # Flip the role
            inverted_level = band.copy()
            if band["role"] == "SUPPORT":
                inverted_level["role"] = "RESISTANCE"
                inverted_level["inverted_from"] = "SUPPORT"
            else:
                inverted_level["role"] = "SUPPORT"
                inverted_level["inverted_from"] = "RESISTANCE"
            
            inverted_level["status"] = "INVERTED"
            inverted.append(inverted_level)
    
    return inverted

def find_nearest(bands, current_price, role, count=3):
    """Find nearest N bands of a given role (SUPPORT or RESISTANCE)."""
    filtered = [b for b in bands if b["role"] == role]
    filtered.sort(key=lambda x: x["distance_pct"])
    return filtered[:count]

def find_regime_flip_levels(bands, current_price):
    """
    Identify key levels that flip market regime:
    - bullish_flip: nearest resistance that, if broken, confirms bullish regime
    - bearish_flip: nearest support that, if broken, confirms bearish regime
    """
    supports = [b for b in bands if b["role"] == "SUPPORT" and b["strength"] >= 5]
    resistances = [b for b in bands if b["role"] == "RESISTANCE" and b["strength"] >= 5]
    
    supports.sort(key=lambda x: x["distance_pct"])
    resistances.sort(key=lambda x: x["distance_pct"])
    
    return {
        "bullish_flip": resistances[0]["center"] if resistances else None,
        "bearish_flip": supports[0]["center"] if supports else None,
    }

def find_confluence_levels(bands, v7_magnets=None):
    """Find levels where S/R bands align with V7 liquidation magnets."""
    if not v7_magnets:
        return []
    
    confluence = []
    for band in bands:
        for magnet in v7_magnets:
            # Check if within 1% of each other
            if abs(band["center"] - magnet["level"]) / band["center"] < 0.01:
                confluence.append({
                    "level": band["center"],
                    "band_strength": band["strength"],
                    "magnet_intensity": magnet.get("intensity", "unknown"),
                    "role": band["role"],
                    "status": "CONFLUENCE"
                })
    
    return confluence

def run_brief(timeframe="4h", output_format="text"):
    """Main execution — outputs structured S/R band report."""
    if timeframe not in TIMEFRAME_CONFIG:
        print(f"ERROR: Invalid timeframe '{timeframe}'. Use: 1h, 4h, 1d", file=sys.stderr)
        return
    
    config = TIMEFRAME_CONFIG[timeframe]
    klines = fetch_klines(interval=timeframe, limit=config["lookback"])
    
    if not klines:
        print("ERROR: No kline data", file=sys.stderr)
        return
    
    current_price = klines[-1]["close"]
    price_low = min(k["low"] for k in klines)
    price_high = max(k["high"] for k in klines)
    
    # Calculate ATR for dynamic clustering
    atr = calc_atr(klines, config["atr_period"])
    atr_pct = atr / current_price if current_price > 0 else config["base_cluster_pct"]
    
    # Use max of ATR-based and base cluster percentage
    cluster_tolerance = max(atr_pct * 0.5, config["base_cluster_pct"])
    
    # Volume bin size based on round step
    vol_bin_size = config["round_step"]
    
    # 1. Swing pivots
    swing_highs, swing_lows = find_swing_pivots(klines, config["pivot_lookback"])
    
    # 2. Volume profile (HVN)
    hvn = volume_profile(klines, vol_bin_size)
    
    # 3. Round numbers
    rounds = round_numbers(price_low, price_high, config["round_step"])
    
    # Combine all levels
    all_levels = swing_highs + swing_lows + hvn + rounds
    
    # 4. Cluster into bands
    bands = cluster_levels(all_levels, cluster_tolerance)
    
    # 5. Apply decay weighting
    bands = apply_decay_weighting(bands, len(klines), config["decay_half_life"])
    
    # 6. Classify as S/R
    bands = classify_bands(bands, current_price)
    
    # 7. Classify level status
    for band in bands:
        band["status"] = classify_level_status(band, klines, config["status_recent_window"])
    
    # 8. Detect inverted S/R
    inverted_levels = detect_inverted_sr(bands, klines)
    
    # 9. Remove BROKEN bands (they're replaced by inverted entries)
    bands = [b for b in bands if b["status"] != "BROKEN"]
    
    # 10. Filter: only bands within 10% of current price
    bands = [b for b in bands if b["distance_pct"] <= 10]
    
    # Sort by strength descending
    bands.sort(key=lambda x: (-x["strength"], x["distance_pct"]))
    
    # Nearest supports and resistances
    nearest_supports = find_nearest(bands, current_price, "SUPPORT", 3)
    nearest_resistances = find_nearest(bands, current_price, "RESISTANCE", 3)
    
    # Regime flip levels
    regime_flips = find_regime_flip_levels(bands, current_price)
    
    # Output
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    if output_format == "json":
        # Standardized JSON output
        output = {
            "schema_version": "2.0",
            "timestamp": now,
            "timeframe": timeframe,
            "current_price": current_price,
            "atr": round(atr, 2),
            "atr_pct": round(atr_pct * 100, 3),
            "cluster_tolerance_pct": round(cluster_tolerance * 100, 3),
            "candles": len(klines),
            "supports": nearest_supports,
            "resistances": nearest_resistances,
            "all_bands": bands,
            "inverted_levels": inverted_levels,
            "regime_flip_levels": regime_flips,
        }
        print(json.dumps(output, indent=2))
    else:
        # Human-readable text output
        print(f"=== BTC {timeframe.upper()} S/R BANDS ===")
        print(f"Time: {now}")
        print(f"Current Price: ${current_price:,.2f}")
        print(f"ATR({config['atr_period']}): ${atr:,.2f} ({atr_pct*100:.3f}%)")
        print(f"Cluster Tolerance: {cluster_tolerance*100:.3f}%")
        print(f"Range: ${price_low:,.2f} — ${price_high:,.2f}")
        print(f"Candles analyzed: {len(klines)} ({timeframe})")
        print()
        
        print(f"=== NEAREST SUPPORTS ===")
        for i, s in enumerate(nearest_supports, 1):
            print(f"  S{i}: ${s['center']:,.2f} (−{s['distance_pct']}%) [{s['status']}]")
            print(f"      Band: ${s['low']:,.2f} — ${s['high']:,.2f}")
            print(f"      Strength: {s['strength_label']} ({s['strength']}/10)")
            print(f"      Touches: {s['touches']} (decayed: {s.get('touches_decayed', 'N/A')})")
            print(f"      Sources: {', '.join(s['types'])}")
            if s['volume_usdt'] > 0:
                print(f"      Volume: ${s['volume_usdt']/1e6:.1f}M")
            print()
        
        print(f"=== NEAREST RESISTANCES ===")
        for i, r in enumerate(nearest_resistances, 1):
            print(f"  R{i}: ${r['center']:,.2f} (+{r['distance_pct']}%) [{r['status']}]")
            print(f"      Band: ${r['low']:,.2f} — ${r['high']:,.2f}")
            print(f"      Strength: {r['strength_label']} ({r['strength']}/10)")
            print(f"      Touches: {r['touches']} (decayed: {r.get('touches_decayed', 'N/A')})")
            print(f"      Sources: {', '.join(r['types'])}")
            if r['volume_usdt'] > 0:
                print(f"      Volume: ${r['volume_usdt']/1e6:.1f}M")
            print()
        
        if inverted_levels:
            print(f"=== INVERTED S/R LEVELS ===")
            for inv in inverted_levels:
                print(f"  ${inv['center']:,.2f} | {inv['role']} (was {inv['inverted_from']}) | {inv['strength_label']}")
            print()
        
        print(f"=== REGIME FLIP LEVELS ===")
        if regime_flips["bullish_flip"]:
            print(f"  Bullish flip: ${regime_flips['bullish_flip']:,.2f} (break above confirms bullish)")
        if regime_flips["bearish_flip"]:
            print(f"  Bearish flip: ${regime_flips['bearish_flip']:,.2f} (break below confirms bearish)")
        print()
        
        print(f"=== ALL BANDS (within 10%) ===")
        for b in bands:
            role = "S" if b["role"] == "SUPPORT" else "R"
            dist_sign = "−" if b["role"] == "SUPPORT" else "+"
            td = b.get('touches_decayed')
            td_str = f"{td:.2f}d" if td else "N/A"
            print(f"  {role} ${b['center']:,.2f} ({dist_sign}{b['distance_pct']}%) "
                  f"| {b['strength_label']:8s} | {b['status']:10s} | "
                  f"{b['touches']}T ({td_str}) | {', '.join(b['types'])}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="BTC Multi-Timeframe S/R Bands")
    parser.add_argument("--timeframe", "-t", default="4h", choices=["1h", "4h", "1d"],
                       help="Timeframe: 1h, 4h, 1d (default: 4h)")
    parser.add_argument("--json", "-j", action="store_true", help="Output JSON format")
    args = parser.parse_args()
    
    run_brief(timeframe=args.timeframe, output_format="json" if args.json else "text")
