#!/usr/bin/env python3
"""A4 Liquidation Magnets — Parse browser_vision output → enriched JSON + history tracking.

Input: CLI args from browser_vision structured output
Output: /tmp/btc_heatmap_clusters.json (full enriched format)
        /tmp/btc_heatmap_history.json (last 10 readings for trend detection)

Usage:
  python3 parse_heatmap.py \\
    --above-cluster "77000-77200" \\
    --below-cluster "76000-76200" \\
    --above-magnet "76800" \\
    --below-magnet "76400" \\
    --confidence "High" \\
    --current-area "76,600"
"""

import argparse, json, os, sys
from datetime import datetime, timezone
from collections import deque

OUTPUT_PATH = "/tmp/btc_heatmap_clusters.json"
HISTORY_PATH = "/tmp/btc_heatmap_history.json"
MAX_HISTORY = 10


# ─── Helpers ────────────────────────────────────────────
def extract_price(v):
    if not v or str(v).lower() in ("none", "none visible", "n/a", ""):
        return None
    cleaned = "".join(c for c in str(v).replace(",", "") if c.isdigit() or c == ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_range(v):
    if not v or str(v).lower() in ("none", "none visible", "n/a", ""):
        return None
    parts = [p.strip() for p in str(v).replace("–", "-").replace("—", "-").split("-")]
    prices = [extract_price(p) for p in parts]
    prices = [p for p in prices if p is not None]
    if len(prices) >= 2:
        return {"low": int(min(prices)), "high": int(max(prices))}
    elif len(prices) == 1:
        return {"low": int(prices[0]), "high": int(prices[0])}
    return None


def get_btc_price():
    """Cross-check against Binance spot price."""
    try:
        import urllib.request
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        with urllib.request.urlopen(url, timeout=5) as resp:
            data = json.loads(resp.read())
            return float(data["price"])
    except Exception:
        return None


def classify_density(cluster_width_usd, btc_price):
    """Classify cluster density based on width relative to price."""
    if not btc_price or not cluster_width_usd:
        return "Unknown"
    width_pct = cluster_width_usd / btc_price * 100
    if width_pct <= 0.3:
        return "Dense 🔥"
    elif width_pct <= 1.0:
        return "Moderate"
    else:
        return "Scattered"


def classify_tightness(width_usd):
    """Classify how tight the magnet sandwich is."""
    if width_usd is None:
        return "Unknown"
    if width_usd <= 500:
        return "Vice Grip ⚡"
    elif width_usd <= 1500:
        return "Tight"
    elif width_usd <= 3000:
        return "Moderate"
    else:
        return "Wide"


def load_history():
    """Load history file, return list of entries."""
    try:
        if os.path.exists(HISTORY_PATH):
            with open(HISTORY_PATH) as f:
                return json.load(f)
    except Exception:
        pass
    return []


def save_history(history):
    """Save history, keeping only last MAX_HISTORY entries."""
    history = history[-MAX_HISTORY:]
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f, indent=2)


def compute_trend(history, current, btc_price):
    """Compute trend from history — direction + delta."""
    total_reads = len(history) + 1

    if total_reads == 1:
        return {"direction": "First reading ⏳", "reads": 1, "delta_range_usd": 0}
    if total_reads == 2:
        return {"direction": "Gathering data ⏳ (need 1 more)", "reads": 2, "delta_range_usd": 0}

    prev = history[-1]
    prev_range = prev.get("range", {}).get("width_usd")
    curr_range = current.get("range", {}).get("width_usd")

    if prev_range is None or curr_range is None:
        return {"direction": "Insufficient data", "reads": len(history) + 1, "delta_range_usd": 0}

    delta = curr_range - prev_range
    abs_delta = abs(delta)

    if abs_delta < 20:
        direction = "→ Steady"
    elif delta < 0:
        direction = "→ Tightening ⚠️" if abs_delta > 100 else "→ Tightening"
    else:
        direction = "→ Expanding" if abs_delta > 100 else "→ Slightly wider"

    return {
        "direction": direction,
        "reads": len(history) + 1,
        "delta_range_usd": delta,
        "prev_range_usd": prev_range,
    }


def validate(result, btc_price):
    """Check below cluster is below real price, above cluster is above."""
    issues = []

    below_cluster = result.get("below", {}).get("strongest_cluster") or {}
    above_cluster = result.get("above", {}).get("strongest_cluster") or {}

    if below_cluster.get("low") and below_cluster["low"] > btc_price:
        issues.append(
            f"BELOW cluster ${below_cluster['low']:,}-${below_cluster['high']:,} "
            f"is ABOVE real price ${btc_price:,.0f}"
        )
    if above_cluster.get("high") and above_cluster["high"] < btc_price:
        issues.append(
            f"ABOVE cluster ${above_cluster['low']:,}-${above_cluster['high']:,} "
            f"is BELOW real price ${btc_price:,.0f}"
        )

    below_mag = result.get("below", {}).get("nearest_magnet") or {}
    above_mag = result.get("above", {}).get("nearest_magnet") or {}
    if below_mag.get("price") and below_mag["price"] > btc_price:
        issues.append(f"BELOW magnet ${below_mag['price']:,} is ABOVE real price")
    if above_mag.get("price") and above_mag["price"] < btc_price:
        issues.append(f"ABOVE magnet ${above_mag['price']:,} is BELOW real price")

    return issues


# ─── Main Build ─────────────────────────────────────────
def build(args):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    btc_price = get_btc_price()
    print(f"💰 BTC Price: ${btc_price:,.0f}" if btc_price else "⚠️  Could not fetch BTC price")

    # Parse inputs
    above_cluster = extract_range(args.above_cluster)
    below_cluster = extract_range(args.below_cluster)
    nearest_above = extract_price(args.above_magnet)
    nearest_below = extract_price(args.below_magnet)

    result = {
        "timestamp": ts,
        "confidence": args.confidence,
        "btc_price": int(btc_price) if btc_price else None,
        "current_price_area": args.current_area,
    }

    # ─── Above ───
    above = {}
    if above_cluster:
        above_width = above_cluster["high"] - above_cluster["low"]
        above["strongest_cluster"] = {
            "low": above_cluster["low"],
            "high": above_cluster["high"],
        }
        above["density"] = classify_density(above_width, btc_price)
        above["cluster_width_usd"] = above_width
    else:
        above["strongest_cluster"] = None
        above["density"] = "None"
        above["cluster_width_usd"] = 0

    if nearest_above and btc_price:
        above["nearest_magnet"] = {
            "price": int(nearest_above),
            "distance_pct": round((nearest_above - btc_price) / btc_price * 100, 1),
            "distance_usd": int(nearest_above - btc_price),
        }
    elif nearest_above:
        above["nearest_magnet"] = {"price": int(nearest_above)}
    else:
        above["nearest_magnet"] = None

    # ─── Below ───
    below = {}
    if below_cluster:
        below_width = below_cluster["high"] - below_cluster["low"]
        below["strongest_cluster"] = {
            "low": below_cluster["low"],
            "high": below_cluster["high"],
        }
        below["density"] = classify_density(below_width, btc_price)
        below["cluster_width_usd"] = below_width
    else:
        below["strongest_cluster"] = None
        below["density"] = "None"
        below["cluster_width_usd"] = 0

    if nearest_below and btc_price:
        below["nearest_magnet"] = {
            "price": int(nearest_below),
            "distance_pct": round((nearest_below - btc_price) / btc_price * 100, 1),
            "distance_usd": int(nearest_below - btc_price),
        }
    elif nearest_below:
        below["nearest_magnet"] = {"price": int(nearest_below)}
    else:
        below["nearest_magnet"] = None

    result["above"] = above
    result["below"] = below

    # ─── Range Sandwich ───
    if nearest_above and nearest_below:
        width_usd = int(nearest_above - nearest_below)
        width_pct = round(width_usd / btc_price * 100, 1) if btc_price else None
    else:
        width_usd = None
        width_pct = None

    result["range"] = {
        "width_usd": width_usd,
        "width_pct": width_pct,
        "tightness": classify_tightness(width_usd),
    }

    # ─── Trend from History ───
    history = load_history()
    result["trend"] = compute_trend(history, result, btc_price)

    # Append to history (strip trend from stored entries to avoid nesting)
    history_entry = {k: v for k, v in result.items() if k != "trend"}
    history.append(history_entry)
    save_history(history)

    # ─── Validation ───
    result["tactical_note"] = ""
    if btc_price:
        issues = validate(result, btc_price)
        if issues:
            for issue in issues:
                print(f"❌ VALIDATION: {issue}")
            result["confidence"] = "vision_misread"
        else:
            print("✅ All clusters validated against real price")

    # ─── Write ───
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"✅ Written to {OUTPUT_PATH}")
    print(f"📊 Trend: {result['trend']['direction']} | Range: {result['range']['tightness']}")

    # Summary for copy-paste
    print("\n── A4 SUMMARY ──")
    print(f"  Above: ${nearest_above:,} (+{above.get('nearest_magnet',{}).get('distance_pct','?')}%) — {above.get('density','?')}")
    print(f"  Below: ${nearest_below:,} ({below.get('nearest_magnet',{}).get('distance_pct','?')}%) — {below.get('density','?')}")
    print(f"  Range: ${width_usd:,} ({result['range']['tightness']})")
    print(f"  Trend: {result['trend']['direction']}")
    if btc_price and nearest_above and nearest_below:
        above_dist = nearest_above - btc_price
        below_dist = btc_price - nearest_below
        print(f"  Bias: {'⬆️ Upside pull' if above_dist < below_dist else '⬇️ Downside pull' if below_dist < above_dist else '↔️ Balanced'}")

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse A4 liquidation heatmap data")
    parser.add_argument("--above-cluster", required=True, help="E.g. '77000-77200'")
    parser.add_argument("--below-cluster", required=True, help="E.g. '76000-76200'")
    parser.add_argument("--above-magnet", required=True, help="E.g. '76800'")
    parser.add_argument("--below-magnet", required=True, help="E.g. '76400'")
    parser.add_argument("--confidence", required=True, help="Low/Medium/High")
    parser.add_argument("--current-area", default="", help="E.g. '76,600'")
    args = parser.parse_args()
    build(args)
