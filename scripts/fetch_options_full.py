#!/usr/bin/env python3
"""Full Deribit BTC Options scraper — metrics page + API → /tmp/btc_options_full.json"""
import json, time, os, re
from playwright.sync_api import sync_playwright

def parse_metrics(text):
    result = {"timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "error": None}
    
    lines = text.split('\n')
    
    # Extract key metrics by position/pattern
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        
        # 24h Put Volume: next line has number
        if "Put Volume:" in line:
            for j in range(i+1, min(i+5, len(lines))):
                try:
                    result["put_volume_24h"] = float(lines[j].strip().replace(',',''))
                    break
                except Exception: pass
        
        if "Call Volume:" in line:
            for j in range(i+1, min(i+5, len(lines))):
                try:
                    result["call_volume_24h"] = float(lines[j].strip().replace(',',''))
                    break
                except Exception: pass
        
        if "Put/Call Ratio:" in line and "Volume" not in lines[i-1] if i>0 else True:
            for j in range(i+1, min(i+5, len(lines))):
                try:
                    result["pcr_volume"] = float(lines[j].strip())
                    break
                except Exception: pass
        
        if "Call Open Interest" in line:
            for j in range(i+1, min(i+3, len(lines))):
                try:
                    result["call_oi"] = float(lines[j].strip().replace(',',''))
                    break
                except Exception: pass
        
        if "Put Open Interest" in line and "Call" not in lines[i-1] if i>0 else True:
            for j in range(i+1, min(i+3, len(lines))):
                try:
                    result["put_oi"] = float(lines[j].strip().replace(',',''))
                    break
                except Exception: pass
        
        if "Total Open Interest" in line:
            for j in range(i+1, min(i+3, len(lines))):
                try:
                    result["total_oi"] = float(lines[j].strip().replace(',',''))
                    break
                except Exception: pass
        
        if "Notional Value" in line:
            for j in range(i+1, min(i+3, len(lines))):
                val = lines[j].strip().replace('$','').replace(',','')
                try:
                    result["notional_value"] = float(val)
                    break
                except Exception: pass
    
    # Compute PCR
    if "call_oi" in result and "put_oi" in result and result["call_oi"] > 0:
        result["pcr_oi"] = round(result["put_oi"] / result["call_oi"], 2)
    
    # Signal
    pcr = result.get("pcr_oi", 0)
    pcr_vol = result.get("pcr_volume", 0)
    if pcr < 0.7 and pcr_vol < 0.8:
        result["signal"] = "BULLISH — Heavy call buying, low put demand"
    elif pcr > 1.2:
        result["signal"] = "BEARISH — Elevated put buying, hedging surging"
    else:
        result["signal"] = "NEUTRAL — Balanced call/put positioning"
    
    return result

def main():
    url = "https://metrics.deribit.com/options/BTC"
    cache_path = "/tmp/btc_options_full.json"
    
    try:
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 7200:  # 2 hours
                print(f"[CACHE] {age/3600:.1f}h old, skipping")
                return
    except Exception: pass
    
    print(f"[FETCH] {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome",
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36")
        page = ctx.new_page()
        page.set_viewport_size({"width": 1400, "height": 1200})
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(10)
            text = page.evaluate("() => document.body.innerText")
            result = parse_metrics(text)
        except Exception as e:
            result = {"error": str(e), "timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
        finally:
            browser.close()
    
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)
    
    if result.get("error"):
        print(f"[ERROR] {result['error']}")
    else:
        print(f"[OK] OI {result.get('total_oi','?'):.0f}, PCR {result.get('pcr_oi','?')}, Notional ${result.get('notional_value','?')/1e9:.1f}B → {result.get('signal','?')}")
    
    cache_dir = os.path.expanduser("~/pipeline-dashboard V2/data/cache")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "btc_options_full.json"), "w") as f:
        json.dump(result, f, indent=2)

if __name__ == "__main__":
    main()
