#!/usr/bin/env python3
"""Deribit Gamma Walls fetcher → /tmp/btc_gamma.json"""
import json, time, os
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request

BASE = "https://www.deribit.com/api/v2/public"
HEADERS = {"User-Agent": "Mozilla/5.0"}

def api_get(path):
    req = urllib.request.Request(f"{BASE}/{path}", headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())

def get_ticker_oi(name):
    """Get OI for a single instrument"""
    try:
        data = api_get(f"ticker?instrument_name={name}")
        result = data.get("result", {})
        return {
            "name": name,
            "oi": result.get("open_interest", 0),
            "strike": result.get("index_price", 0),
            "mark_iv": result.get("mark_iv", 0)
        }
    except Exception:
        return {"name": name, "oi": 0}

def main():
    cache_path = "/tmp/btc_gamma.json"
    
    try:
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 7200:
                with open(cache_path) as f:
                    data = json.load(f)
                if not data.get("error"):
                    print(f"[CACHE] {age/3600:.1f}h old: Call wall ${data.get('call_wall','?')}, Put wall ${data.get('put_wall','?')}")
                    return
    except Exception: pass
    
    print("[FETCH] Deribit gamma walls...")
    
    try:
        # 1. Get spot
        index = api_get("get_index_price?index_name=btc_usd")
        spot = index.get("result", {}).get("index_price", 77000)
        
        # 2. Get all active BTC options
        instruments_data = api_get("get_instruments?currency=BTC&kind=option&expired=false")
        instruments = instruments_data.get("result", [])
        
        # 3. Filter to strikes within +/-15% of spot (meaningful gamma walls)
        lo = spot * 0.85
        hi = spot * 1.15
        near = [i for i in instruments if lo <= (i.get("strike") or 0) <= hi]
        
        # 4. Get OI for each in parallel
        call_oi = {}   # strike → OI
        put_oi = {}    # strike → OI
        names = [i["instrument_name"] for i in near]
        
        print(f"  Spot ${spot:,.0f} | {len(names)} options in range ${lo:,.0f}-${hi:,.0f}")
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(get_ticker_oi, n): n for n in names}
            done = 0
            for future in as_completed(futures):
                result = future.result()
                name = result["name"]
                oi = result["oi"]
                if oi > 0:
                    if name.endswith("-C"):
                        strike = int(name.split("-")[-2])
                        call_oi[strike] = call_oi.get(strike, 0) + oi
                    elif name.endswith("-P"):
                        strike = int(name.split("-")[-2])
                        put_oi[strike] = put_oi.get(strike, 0) + oi
                done += 1
                if done % 20 == 0:
                    print(f"  {done}/{len(names)}...")
        
        # 5. Find walls
        call_wall = max(call_oi, key=call_oi.get) if call_oi else int(spot // 1000 * 1000 + 1000)
        put_wall = max(put_oi, key=put_oi.get) if put_oi else int(spot // 1000 * 1000)
        
        # 6. Compute gamma exposure (simplified — positive = dampened, negative = amplified)
        # Net dealer gamma ≈ total call gamma − total put gamma near spot
        call_oi_total = sum(call_oi.values())
        put_oi_total = sum(put_oi.values())
        gamma_bias = "LONG" if call_oi_total > put_oi_total * 1.2 else "SHORT" if put_oi_total > call_oi_total * 1.2 else "NEUTRAL"
        gamma_effect = "DAMPENED (range-bound)" if gamma_bias == "LONG" else "AMPLIFIED (breakout-prone)" if gamma_bias == "SHORT" else "BALANCED"
        
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "spot": spot,
            "call_wall": call_wall,
            "call_wall_oi": call_oi.get(call_wall, 0),
            "put_wall": put_wall,
            "put_wall_oi": put_oi.get(put_wall, 0),
            "call_wall_pct": round((call_wall / spot - 1) * 100, 2),
            "put_wall_pct": round((put_wall / spot - 1) * 100, 2),
            "gamma_bias": gamma_bias,
            "gamma_effect": gamma_effect,
            "call_oi_total": call_oi_total,
            "put_oi_total": put_oi_total,
            "options_scanned": len(names)
        }
        
    except Exception as e:
        output = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
            "error": str(e)
        }
    
    with open(cache_path, "w") as f:
        json.dump(output, f, indent=2)
    
    if output.get("error"):
        print(f"[ERROR] {output['error']}")
    else:
        print(f"[OK] Call wall ${output['call_wall']:,} ({output['call_wall_pct']}%), Put wall ${output['put_wall']:,} ({output['put_wall_pct']}%), Gamma: {gamma_bias} → {gamma_effect}")

if __name__ == "__main__":
    main()
