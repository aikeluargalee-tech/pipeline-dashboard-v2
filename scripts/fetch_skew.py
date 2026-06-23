#!/usr/bin/env python3
"""Fetch BTC options 25-delta skew (RR25) from Deribit public API. No auth needed."""
import json, sys, urllib.request
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

OUTPUT = Path("/tmp/btc_skew.json")
CACHE = Path.home() / "pipeline-dashboard V2" / "data" / "cache" / "btc_skew.json"

def log(msg):
    print(msg, flush=True)

def fetch():
    # Get all active BTC option instruments
    url = "https://www.deribit.com/api/v2/public/get_instruments?currency=BTC&kind=option&expired=false"
    data = json.loads(urllib.request.urlopen(url, timeout=15).read())
    instruments = data.get("result", [])
    if not instruments:
        log("❌ No instruments returned from Deribit")
        return {"error": "No instruments", "timestamp": datetime.now(timezone.utc).isoformat()}

    # Get sorted unique expiries
    expiries = sorted(set(r["instrument_name"].split("-")[1] for r in instruments))
    log(f"  Available expiries: {expiries[:10]}")

    # Try each expiry (starting from nearest) until we find one with 25-delta options
    # Skip expiries that are too close to expiration (today) as their delta range is compressed
    today_str = datetime.now(timezone.utc).strftime("%d%b%y").upper()

    best_call = None
    best_put = None
    spot = None
    chosen_expiry = None

    for expiry in expiries:
        # Skip today's expiry — delta compression makes 25d options unreliable
        if expiry == today_str:
            log(f"  Skipping today's expiry {expiry} (delta compression)")
            continue

        expiry_instruments = [r["instrument_name"] for r in instruments if expiry in r.get("instrument_name", "")]
        if not expiry_instruments:
            continue

        log(f"  Trying expiry {expiry} ({len(expiry_instruments)} instruments)...")

        # Fetch tickers in parallel
        def get_ticker(name):
            try:
                turl = f"https://www.deribit.com/api/v2/public/ticker?instrument_name={name}"
                d = json.loads(urllib.request.urlopen(turl, timeout=10).read())
                r = d.get("result", {})
                return {
                    "name": name,
                    "delta": r.get("greeks", {}).get("delta"),
                    "iv": r.get("mark_iv"),
                    "spot": r.get("underlying_price"),
                }
            except Exception:
                return None

        with ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(get_ticker, expiry_instruments))

        # Find best 25-delta call and put (wider tolerance: 0.15 to 0.35)
        c, p, s = None, None, None
        for r in results:
            if not r or r["delta"] is None or r["iv"] is None:
                continue
            s = s or r["spot"]
            d = r["delta"]
            if r["name"].endswith("-C") and 0.15 < abs(d) <= 0.35:
                if c is None or abs(abs(d) - 0.25) < abs(abs(c["delta"]) - 0.25):
                    c = {"name": r["name"], "delta": d, "iv": r["iv"]}
            elif r["name"].endswith("-P") and 0.15 < abs(d) <= 0.35:
                if p is None or abs(abs(d) - 0.25) < abs(abs(p["delta"]) - 0.25):
                    p = {"name": r["name"], "delta": d, "iv": r["iv"]}

        if c and p:
            best_call = c
            best_put = p
            spot = s
            chosen_expiry = expiry
            log(f"  ✅ Found 25d options in {expiry}: call={c['name']}(Δ{c['delta']:.3f}) put={p['name']}(Δ{p['delta']:.3f})")
            break
        else:
            log(f"  ⚠️ {expiry}: call={'found' if c else 'MISSING'} put={'found' if p else 'MISSING'} — trying next expiry")
            # Keep partial results as fallback
            if c and not best_call:
                best_call, spot = c, s or spot
            if p and not best_put:
                best_put, spot = p, s or spot

    if not best_call or not best_put:
        msg = "Could not find 25-delta options in any expiry"
        log(f"❌ {msg}")
        return {"error": msg, "timestamp": datetime.now(timezone.utc).isoformat()}

    skew = best_call["iv"] - best_put["iv"]

    if skew < -10:
        label = "Extreme fear — historically near local bottoms"
        emoji = "🔴"
    elif skew < -5:
        label = "Elevated hedging — institutions buying downside protection"
        emoji = "🟡"
    elif skew <= 5:
        label = "Neutral"
        emoji = "⬜"
    else:
        label = "Call premium — market pricing upside"
        emoji = "🟢"

    result = {
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "spot": spot,
        "skew_25d": round(skew, 1),
        "put_25d_iv": round(best_put["iv"], 1),
        "call_25d_iv": round(best_call["iv"], 1),
        "put_name": best_put["name"],
        "call_name": best_call["name"],
        "label": label,
        "emoji": emoji,
        "display": f"{emoji} Options skew (25Δ): {skew:+.1f}% — {label.lower()}",
    }

    # Write to /tmp
    OUTPUT.write_text(json.dumps(result, indent=2))
    # Also cache
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(result, indent=2))

    print(f"✅ Skew {skew:+.1f}% → {result['display']}")
    return result

if __name__ == "__main__":
    result = fetch()
    if result and "error" in result:
        sys.exit(1)
