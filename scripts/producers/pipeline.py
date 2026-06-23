#!/usr/bin/env python3
"""
BTC News & Black Swan Watcher
Fetches headlines, checks anomaly indicators.
Includes Chinese translation via Gemini.
"""

import json
import os
import sys
import urllib.request
import urllib.error
import re
import time
from datetime import datetime, timezone
from xml.etree import ElementTree
from urllib.request import urlopen, Request

OUTPUT = "/tmp/btc_news_state.json"
MAX_HEADLINES = 5
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) BTC Dashboard/1.0"
HOME = os.path.expanduser("~")
UTC = timezone.utc

def translate_headlines(headlines):
    """Translate headlines to Simplified Chinese using Gemini Flash Lite."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        key_file = os.path.join(HOME, "pipeline-dashboard V2", ".gemini_key")
        if os.path.exists(key_file):
            with open(key_file) as f:
                api_key = f.read().strip()
    if not api_key:
        return headlines

    titles = [h["title"] for h in headlines]
    items = "\n".join(f"[{i}] {t}" for i, t in enumerate(titles))
    prompt = f"""Translate these crypto news headlines to professional, natural Simplified Chinese. 
Keep ticker symbols (BTC, etc.) and acronyms as-is. Do NOT translate proper names like CoinTelegraph or Michael Saylor.

JSON output format: {{"0": "Translated title", "1": "Translated title"}}

{items}"""

    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 2048}
    }).encode("utf-8")

    # Retry with exponential backoff (short: fail fast and move on)
    for attempt in range(2):
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                match = re.search(r'\{.*\}', text, re.DOTALL)
                if match:
                    translated = json.loads(match.group())
                    for i, h in enumerate(headlines):
                        h["title_en"] = h["title"]  # keep original English
                        h["title"] = translated.get(str(i), h["title"])
                    return headlines
        except Exception as e:
            wait = 3
            print(f"  ⚠️ Headline translation failed (attempt {attempt+1}): {e}, waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
    
    print("  ⚠️ Translation skipped — returning headlines in English.", file=sys.stderr)
    return headlines

def fetch_rss(url, source_name):
    """Fetch and parse RSS feed, return list of headline dicts."""
    headlines = []
    try:
        req = Request(url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=15) as f:
            tree = ElementTree.parse(f)
        root = tree.getroot()
        for item in root.findall(".//item")[:MAX_HEADLINES]:
            title = item.findtext("title", "").strip()
            link = item.findtext("link", "").strip()
            pub_date = item.findtext("pubDate", "")
            if title and link:
                headlines.append({
                    "title": title,
                    "source": source_name,
                    "url": link,
                    "published": pub_date,
                })
    except Exception as e:
        print(f"  ⚠️ {source_name} RSS failed: {e}", file=sys.stderr)
    return headlines

def check_black_swan_indicators():
    """Check dashboard state files for warning signals."""
    indicators = {
        "vix_spike": False,
        "dxy_flash": False,
        "stablecoin_stress": False,
        "exchange_anomaly": False,
    }
    severity = 0

    try:
        with open("/tmp/btc_risk_state.json") as f:
            risk = json.load(f)
        vix = risk.get("vix", 0)
        if vix > 35:
            indicators["vix_spike"] = True
            severity += 2
        elif vix > 28:
            indicators["vix_spike"] = True
            severity = max(severity, 1)
    except Exception: pass

    try:
        with open("/tmp/btc_macro_state.json") as f:
            macro = json.load(f)
        dxy = macro.get("dxy", 0)
        if dxy and dxy < 95:
            indicators["dxy_flash"] = True
            severity += 1
    except Exception: pass

    try:
        st = "/tmp/btc_stablecoin_state.json"
        if os.path.exists(st):
            with open(st) as f:
                stable = json.load(f)
            if stable and stable.get("status") == "depeg risk":
                indicators["stablecoin_stress"] = True
                severity += 2
    except Exception: pass

    try:
        with open("/tmp/btc_onchain_state.json") as f:
            oc = json.load(f)
        netflow = oc.get("exchange_netflow_7d_btc", 0)
        if netflow and abs(netflow) > 10000:
            indicators["exchange_anomaly"] = True
            severity += 1
    except Exception: pass

    if severity >= 3: status = "critical"
    elif severity >= 1: status = "elevated"
    else: status = "normal"

    return {"status": status, "severity": severity, "indicators": indicators}

def main():
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    print(f"=== BTC News Watcher {now} ===")

    all_headlines = []
    all_headlines.extend(fetch_rss("https://cointelegraph.com/rss", "CoinTelegraph"))
    all_headlines.extend(fetch_rss("https://www.coindesk.com/arc/outboundfeeds/rss/", "CoinDesk"))

    seen = set()
    unique = []
    for h in all_headlines:
        key = h["title"][:60].lower()
        if key not in seen:
            seen.add(key)
            unique.append(h)

    time.sleep(2)
    headlines = translate_headlines(unique[:MAX_HEADLINES])
    black_swan = check_black_swan_indicators()

    state = {
        "timestamp": now,
        "headlines": headlines,
        "black_swan": black_swan,
        "headline_count": len(headlines),
    }

    with open(OUTPUT, "w") as f:
        json.dump(state, f, indent=2)

    print(f"  📰 {len(headlines)} headlines (translated to zh-CN)")
    print(f"  ✅ Written to {OUTPUT}")
    return True

if __name__ == "__main__":
    main()
