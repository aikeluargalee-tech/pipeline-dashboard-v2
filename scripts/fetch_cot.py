#!/usr/bin/env python3
"""CME COT BTC Futures scraper → /tmp/btc_cot.json"""
import json, time, os, re
from pathlib import Path
from playwright.sync_api import sync_playwright

def parse_cot(text):
    result = {"timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()), "error": None}
    
    idx = text.find("BITCOIN - CHICAGO MERCANTILE EXCHANGE")
    if idx < 0:
        result["error"] = "BITCOIN section not found"
        return result
    
    section = text[idx:idx+3000]
    
    # Extract date
    m = re.search(r'AS OF (\d{2}/\d{2}/\d{2})', section)
    if m:
        result["as_of"] = m.group(1)
    
    # Extract OI
    m = re.search(r'OPEN INTEREST:\s+([\d,]+)', section)
    if m:
        result["open_interest"] = int(m.group(1).replace(',',''))
    
    # Find commitment numbers - they appear as: 18,154 16,895 3,205 227 2,387 ...
    # Pattern: 8 comma-numbers in one line after OI line
    # The line AFTER "COMMITMENTS" or the line with 8 numbers
    lines = section.split('\n')
    commitment_line = None
    for i, line in enumerate(lines):
        # Look for a line with 8+ comma-separated numbers
        nums = re.findall(r'(-?[\d,]+)', line.replace(' ', '  '))
        nums = [n.strip() for n in nums if re.match(r'^-?[\d,]+$', n.strip())]
        if len(nums) >= 8:
            try:
                parsed = [int(n.replace(',','')) for n in nums[:8]]
                # Validate: first 8 are reasonable COT numbers (100-100000 range)
                if all(100 < abs(p) < 1000000 for p in parsed):
                    commitment_line = parsed
                    break
            except Exception:
                continue
    
    if commitment_line:
        result["noncomm_long"] = commitment_line[0]
        result["noncomm_short"] = commitment_line[1]
        result["noncomm_spreads"] = commitment_line[2]
        result["comm_long"] = commitment_line[3]
        result["comm_short"] = commitment_line[4]
        result["total_long"] = commitment_line[5]
        result["total_short"] = commitment_line[6]
        result["nonreport_long"] = commitment_line[7]
        if len(commitment_line) > 8:
            result["nonreport_short"] = commitment_line[8]
    
    # Find WoW changes
    for i, line in enumerate(lines):
        if "CHANGES FROM" in line:
            m = re.search(r'FROM\s+(\d{2}/\d{2}/\d{2})', line)
            if m:
                result["change_date"] = m.group(1)
            # Next line should have change numbers
            if i+1 < len(lines):
                next_line = lines[i+1]
                nums = re.findall(r'(-?[\d,]+)', next_line)
                nums = [n.strip() for n in nums if re.match(r'^-?[\d,]+$', n.strip())]
                if len(nums) >= 5:
                    result["wow_noncomm_long"] = int(nums[0].replace(',',''))
                    result["wow_noncomm_short"] = int(nums[1].replace(',',''))
                    if len(nums) > 2:
                        result["wow_noncomm_spreads"] = int(nums[2].replace(',',''))
                    if len(nums) > 4:
                        result["wow_comm_short"] = int(nums[4].replace(',',''))
            break
    
    # Compute nets
    if "noncomm_long" in result:
        result["noncomm_net"] = result["noncomm_long"] - result.get("noncomm_short", 0)
        result["comm_net"] = result.get("comm_long", 0) - result.get("comm_short", 0)
    
    # Signal
    nc_net = result.get("noncomm_net", 0)
    comm_net = result.get("comm_net", 0)
    if nc_net > 2000 and abs(comm_net) < 2000:
        result["signal"] = "BULLISH — Lev funds heavily long, commercials not hedging aggressively"
    elif nc_net < -1000:
        result["signal"] = "BEARISH — Lev funds net short"
    elif abs(comm_net) > 3000:
        result["signal"] = "CAUTION — Commercials hedging heavily (late-cycle)"
    else:
        result["signal"] = "NEUTRAL — No extreme positioning"
    
    return result

def main():
    url = "https://www.cftc.gov/dea/futures/deacmesf.htm"
    cache_path = "/tmp/btc_cot.json"
    
    try:
        if os.path.exists(cache_path):
            age = time.time() - os.path.getmtime(cache_path)
            if age < 43200:
                print(f"[CACHE] {age/3600:.1f}h old, skipping")
                return
    except Exception:
        pass
    
    print(f"[FETCH] {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome",
            args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"])
        ctx = browser.new_context(user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36")
        page = ctx.new_page()
        page.set_viewport_size({"width": 1400, "height": 1000})
        
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(8)
            text = page.evaluate("() => document.body.innerText")
            result = parse_cot(text)
        except Exception as e:
            result = {"error": str(e), "timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())}
        finally:
            browser.close()
    
    with open(cache_path, "w") as f:
        json.dump(result, f, indent=2)
    
    if result.get("error"):
        print(f"[ERROR] {result['error']}")
    else:
        print(f"[OK] COT {result.get('as_of','?')}: NC net {result.get('noncomm_net','?')}, Comm net {result.get('comm_net','?')} → {result.get('signal','?')}")
    
    cache_dir = os.path.expanduser("~/pipeline-dashboard V2/data/cache")
    os.makedirs(cache_dir, exist_ok=True)
    with open(os.path.join(cache_dir, "btc_cot.json"), "w") as f:
        json.dump(result, f, indent=2)

if __name__ == "__main__":
    main()
