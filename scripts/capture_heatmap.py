#!/usr/bin/env python3
"""
BTC Liquidation Heatmap Snapshot
Headless Chrome → Coinglass 24H heatmap → screenshot → Gemini Flash Lite vision → JSON

Output: /tmp/btc_heatmap_clusters.json
Run:    python3 scripts/capture_heatmap.py

ALTERNATIVE (LIVE): From Hermes terminal with browser_vision:
  auxiliary.vision must be: provider=google, model=gemini-3.1-flash-lite
  Then: browser_navigate → Coinglass → browser_vision → reads clusters live
  No Chrome, no screenshot file, no batch latency. Preferred for interactive sessions.
  This batch script remains for hourly cron (deploy.sh).
"""
import base64
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

HOME = Path.home()
SITE_DIR = HOME / "pipeline-dashboard V2"
OUTPUT_PATH = Path("/tmp/btc_heatmap_clusters.json")
SCREENSHOT_PATH = Path("/tmp/coinglass_heatmap_raw.png")
COMPRESSED_PATH = Path("/tmp/coinglass_heatmap.jpg")

# Gemini vision config
GEMINI_KEY_FILE = SITE_DIR / ".gemini_key"
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

GEMINI_API_KEY = ""
if GEMINI_KEY_FILE.exists():
    GEMINI_API_KEY = GEMINI_KEY_FILE.read_text().strip()

VISION_PROMPT = """You are analyzing a BTC liquidation heatmap screenshot from Coinglass (24-hour view).

A liquidation heatmap shows where leveraged positions would get liquidated. Bright yellow/orange zones = dense liquidation clusters. Read the Y-axis price labels on the right side of the chart — those are your ground truth.

Your job:
1. Find the current price line (usually a horizontal line crossing the chart)
2. Identify the BRIGHTEST yellow/orange cluster ABOVE the price line — that is the strongest overhead (short liquidation) zone
3. Identify the BRIGHTEST yellow/orange cluster BELOW the price line — that is the strongest downside (long liquidation) zone
4. Find the CLOSEST visible cluster to price on each side (the nearest magnet)

Rules:
- Read prices from the Y-axis labels — not from pixel math
- Report price ranges in format like "82,000-83,500" not single numbers
- If no clear cluster on a side, say "None visible"
- Be conservative — only report what you can actually see
- Do NOT invent or guess labels

Return EXACTLY this format (no markdown, no extra commentary):

Current price area: <price>
Strongest overhead cluster zone: <range or None visible>
Strongest downside cluster zone: <range or None visible>
Nearest overhead magnet: <price or None>
Nearest downside magnet: <price or None>
Tactical note: <one sentence: which side has bigger clusters, what that means>
Confidence: <Low/Medium/High>
"""


def parse_vision_output(text: str) -> dict:
    """Parse the vision model's text output into structured fields."""
    fields = {
        "current_price_area": r"Current price area:\s*(.+)",
        "overhead_cluster": r"Strongest overhead cluster zone:\s*(.+)",
        "downside_cluster": r"Strongest downside cluster zone:\s*(.+)",
        "nearest_overhead": r"Nearest overhead magnet:\s*(.+)",
        "nearest_downside": r"Nearest downside magnet:\s*(.+)",
        "tactical_note": r"Tactical note:\s*(.+)",
        "confidence": r"Confidence:\s*(.+)",
    }
    result = {}
    for key, pattern in fields.items():
        m = re.search(pattern, text, re.IGNORECASE)
        result[key] = m.group(1).strip() if m else ""
    return result


def extract_price(v: str) -> float | None:
    """Extract a numeric price from a string like '$81,417' or '81417' or '81,417'."""
    if not v or v.lower() in ("none", "none visible", "n/a", ""):
        return None
    cleaned = re.sub(r"[^\d.]", "", v.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return None


def extract_range(v: str) -> dict | None:
    """Extract a price range like '$78,900-$79,500' or '78,900 - 79,500'."""
    if not v or v.lower() in ("none", "none visible", "n/a", ""):
        return None
    parts = re.split(r"\s*[-–—]\s*", v)
    prices = [extract_price(p) for p in parts]
    prices = [p for p in prices if p is not None]
    if len(prices) >= 2:
        return {"low": min(prices), "high": max(prices)}
    elif len(prices) == 1:
        return {"low": prices[0], "high": prices[0]}
    return None


def build_cluster_json(parsed: dict, current_price: float | None) -> dict:
    """Convert parsed vision output into structured JSON."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    above_cluster = extract_range(parsed.get("overhead_cluster", ""))
    below_cluster = extract_range(parsed.get("downside_cluster", ""))
    nearest_above = extract_price(parsed.get("nearest_overhead", ""))
    nearest_below = extract_price(parsed.get("nearest_downside", ""))

    result = {
        "timestamp": ts,
        "current_price_area": parsed.get("current_price_area", ""),
    }

    # Above (short liquidation zones — upside fuel)
    above = {}
    if above_cluster:
        above["strongest_cluster"] = {
            "low": int(above_cluster["low"]),
            "high": int(above_cluster["high"]),
        }
    else:
        above["strongest_cluster"] = None

    if nearest_above and current_price:
        above["nearest_magnet"] = {
            "price": int(nearest_above),
            "distance_pct": round((nearest_above - current_price) / current_price * 100, 1),
        }
    elif nearest_above:
        above["nearest_magnet"] = {"price": int(nearest_above)}
    else:
        above["nearest_magnet"] = None

    # Below (long liquidation zones — downside magnets)
    below = {}
    if below_cluster:
        below["strongest_cluster"] = {
            "low": int(below_cluster["low"]),
            "high": int(below_cluster["high"]),
        }
    else:
        below["strongest_cluster"] = None

    if nearest_below and current_price:
        below["nearest_magnet"] = {
            "price": int(nearest_below),
            "distance_pct": round((nearest_below - current_price) / current_price * 100, 1),
        }
    elif nearest_below:
        below["nearest_magnet"] = {"price": int(nearest_below)}
    else:
        below["nearest_magnet"] = None

    result["above"] = above
    result["below"] = below
    result["tactical_note"] = parsed.get("tactical_note", "")
    result["confidence"] = parsed.get("confidence", "")

    return result


def capture():
    """Main capture routine."""

    # 1. Get current BTC price from Binance for reference
    current_price = None
    try:
        import ccxt
        exchange = ccxt.binance()
        ticker = exchange.fetch_ticker("BTC/USDT")
        current_price = ticker.get("last")
    except Exception:
        pass

    # 2. Launch headless Chrome
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1600,1000")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])

    driver = webdriver.Chrome(options=options)
    print("🚀 Headless Chrome launched")

    try:
        # Navigate to Coinglass 24H heatmap
        url = "https://www.coinglass.com/pro/futures/LiquidationHeatMap"
        driver.get(url)
        print(f"📄 Navigated to Coinglass")

        # Wait for canvas to render (heatmap takes a few seconds)
        time.sleep(10)

        # Try waiting for canvas element
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "canvas"))
            )
            print("✅ Canvas detected")
        except Exception:
            print("⚠️ Canvas wait timed out, proceeding anyway")

        # Extra wait for heatmap data to load
        time.sleep(5)

        # Screenshot
        driver.save_screenshot(str(SCREENSHOT_PATH))
        print(f"📸 Screenshot saved: {SCREENSHOT_PATH}")

    finally:
        driver.quit()
        print("🔒 Browser closed")

    # 3. Compress screenshot for vision API (must be under ~80KB base64)
    try:
        img = Image.open(SCREENSHOT_PATH)
        # Aggressive resize: max 1200 width for 11B vision model
        if img.width > 1200:
            ratio = 1200 / img.width
            new_size = (1200, int(img.height * ratio))
            img = img.resize(new_size, Image.LANCZOS)
        img.save(COMPRESSED_PATH, "JPEG", quality=30, optimize=True)
        size = COMPRESSED_PATH.stat().st_size
        b64_size = int(size * 1.37)  # base64 overhead
        print(f"🗜️ Compressed: {COMPRESSED_PATH} ({size} bytes, ~{b64_size} bytes base64)")
        if b64_size > 100000:
            # Still too large — reduce quality further
            img.save(COMPRESSED_PATH, "JPEG", quality=25, optimize=True)
            print(f"   Re-compressed to {COMPRESSED_PATH.stat().st_size} bytes")
    except Exception as e:
        print(f"⚠️ Compression failed: {e}")
        COMPRESSED_PATH.write_bytes(SCREENSHOT_PATH.read_bytes())

    # 4. Call Gemini vision API
    if not GEMINI_API_KEY:
        print("❌ No Gemini API key — aborting vision analysis")
        return False

    with open(COMPRESSED_PATH, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "contents": [{
            "parts": [
                {"text": VISION_PROMPT},
                {"inline_data": {"mime_type": "image/jpeg", "data": image_b64}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 600,
        }
    }

    print(f"🤖 Calling Gemini {GEMINI_MODEL} vision API...")
    try:
        resp = requests.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY}",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        vision_text = data["candidates"][0]["content"]["parts"][0]["text"]
        print(f"📝 Vision response ({len(vision_text)} chars)")
        print(vision_text[:300] + "..." if len(vision_text) > 300 else vision_text)
    except Exception as e:
        print(f"❌ Gemini vision API failed: {e}")
        partial = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "error": str(e),
            "above": {"strongest_cluster": None, "nearest_magnet": None},
            "below": {"strongest_cluster": None, "nearest_magnet": None},
            "tactical_note": "",
            "confidence": "vision_failed",
        }
        # Don't overwrite existing good data on API failure
        if OUTPUT_PATH.exists():
            try:
                existing = json.loads(OUTPUT_PATH.read_text())
                if existing.get("confidence") not in ("vision_failed", "vision_misread", None):
                    print(f"  Keeping existing good data (confidence: {existing.get('confidence')})")
                    return False
            except Exception:
                pass
        OUTPUT_PATH.write_text(json.dumps(partial, indent=2))
        return False

    # 5. Parse and structure
    parsed = parse_vision_output(vision_text)
    cluster_data = build_cluster_json(parsed, current_price)

    # 5b. VALIDATE: cross-check vision output against real Binance price
    if current_price:
        below_magnet = cluster_data.get("below", {}).get("nearest_magnet", {})
        above_magnet = cluster_data.get("above", {}).get("nearest_magnet", {})
        below_price = below_magnet.get("price") if below_magnet else None
        above_price = above_magnet.get("price") if above_magnet else None
        
        # Detect vision model overestimating current price:
        # "below" magnet above real price = model read chart price too high
        if below_price and below_price > current_price:
            print(f"⚠️  Model overestimated price. 'Below' magnet ${below_price:,} is above real price ${current_price:,.0f}")
            if above_price and above_price > below_price:
                # Above is further up — keep it, below becomes nearest above
                print(f"   Repositioning: nearest overhead = ${below_price:,}")
                cluster_data["above"]["nearest_magnet"] = cluster_data["below"]["nearest_magnet"]
                cluster_data["below"]["nearest_magnet"] = None
                cluster_data["confidence"] = "Medium"
            elif above_price and above_price < current_price:
                # Above is actually below — full swap
                print(f"   Swapping above/below clusters")
                cluster_data["above"], cluster_data["below"] = cluster_data["below"], cluster_data["above"]
            else:
                # No above magnet — move below to above
                print(f"   No above magnet. Moving below → overhead at ${below_price:,}")
                cluster_data["above"]["nearest_magnet"] = cluster_data["below"]["nearest_magnet"]
                cluster_data["below"]["nearest_magnet"] = None
                cluster_data["confidence"] = "Medium"
        
        # Detect "above" magnet below real price = model seriously misread
        if above_price and above_price < current_price and cluster_data.get("confidence", "") != "Medium":
            print(f"⚠️  VISION ERROR: 'above' magnet ${above_price:,} is BELOW real price ${current_price:,.0f}")
            cluster_data["confidence"] = "vision_misread"
            cluster_data["above"]["nearest_magnet"] = None
            cluster_data["below"]["nearest_magnet"] = None

        # Validate STRONGEST CLUSTERS against real price (not just nearest magnets)
        below_cluster = cluster_data.get("below", {}).get("strongest_cluster", {})
        above_cluster = cluster_data.get("above", {}).get("strongest_cluster", {})
        below_low = below_cluster.get("low") if below_cluster else None
        above_high = above_cluster.get("high") if above_cluster else None

        # "Below" cluster entirely above real price → vision model overestimated price
        if below_low and below_low > current_price:
            print(f"⚠️  CLUSTER ERROR: 'below' cluster ${below_low:,}–${below_cluster.get('high', 0):,} is ABOVE real price ${current_price:,.0f}")
            # Vision model overestimated price — this "below" zone is actually overhead.
            # Clear it; don't overwrite the real above cluster.
            cluster_data["below"]["strongest_cluster"] = None
            cluster_data["confidence"] = "Medium"
            print(f"   Cleared: mispositioned below cluster (above cluster at ${above_cluster.get('low', 0):,}–${above_cluster.get('high', 0):,} preserved)")

        # "Above" cluster entirely below real price → model under-read
        if above_high and above_high < current_price:
            print(f"⚠️  CLUSTER ERROR: 'above' cluster ${above_cluster.get('low', 0):,}–${above_high:,} is BELOW real price ${current_price:,.0f}")
            cluster_data["below"]["strongest_cluster"] = cluster_data["above"]["strongest_cluster"]
            cluster_data["above"]["strongest_cluster"] = None
            cluster_data["confidence"] = "Medium"
            print(f"   Repositioned: above cluster → downside zone")

    # 6. Write JSON
    OUTPUT_PATH.write_text(json.dumps(cluster_data, indent=2))
    print(f"✅ Heatmap data written: {OUTPUT_PATH}")

    # Print summary
    above = cluster_data.get("above", {})
    below = cluster_data.get("below", {})
    tac = cluster_data.get("tactical_note", "")
    print(f"\n📊 SUMMARY:")
    print(f"   Above (short liq / upside fuel): {above}")
    print(f"   Below (long liq / downside magnet): {below}")
    print(f"   Tactical: {tac}")
    print(f"   Confidence: {cluster_data.get('confidence', '?')}")

    return True


if __name__ == "__main__":
    success = capture()
    sys.exit(0 if success else 1)
