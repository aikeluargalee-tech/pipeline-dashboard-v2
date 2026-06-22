#!/usr/bin/env python3
"""
Polymarket BTC Prediction Markets
Queries Gamma API, filters BTC-specific markets, outputs odds card + JSONL log.
"""
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

GAMMA_BASE = "https://gamma-api.polymarket.com"
DATA_DIR = Path.home() / "btc-polymarket" / "data"
JSONL_PATH = DATA_DIR / "markets.jsonl"
MYT = timezone(timedelta(hours=8))

# Keywords for classifying BTC markets — MUST contain at least one in question
BTC_KEYWORDS = ["bitcoin", "btc"]
# Skip these false positive keywords
SKIP_KEYWORDS = ["world cup", "fifa", "nba", "nfl", "ufc", "boxing", "super bowl",
                 "oscar", "grammy", "emmy", "election", "president", "congress",
                 "rihanna", "album", "movie", "film",
                 "temperature", "weather", "hurricane", "earthquake",
                 "airdrop", "megaeth", "token launch"]
PRICE_KEYWORDS = ["above", "below", "price", "$", "high", "low", "close", "reach", "hit"]
EVENT_KEYWORDS = ["approved", "reserve", "strategic", "etf", "launch", "sec", "ban", "regulation", "legal", "halving"]
MIN_VOLUME = 100_000  # Skip tiny markets


def fetch_btc_markets() -> list:
    """Fetch BTC-related markets from Polymarket Gamma API."""
    all_markets = []
    for tag in ["bitcoin", "crypto"]:
        try:
            url = f"{GAMMA_BASE}/markets?tag={tag}&active=true&closed=false&limit=50"
            req = Request(url, headers={"User-Agent": "Milo-BTC/1.0"})
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            all_markets.extend(data)
        except Exception as e:
            print(f"  [WARN] Gamma API failed for tag={tag}: {e}", file=sys.stderr)

    if not all_markets:
        return []

    # Deduplicate by ID
    seen = set()
    unique = []
    for m in all_markets:
        mid = m.get("id")
        if mid and mid not in seen:
            seen.add(mid)
            unique.append(m)
    return unique


def is_btc_market(market: dict) -> bool:
    """Check if a market is BTC-related and not a false positive."""
    question = (market.get("question") or "").lower()
    # Must contain a BTC keyword
    if not any(kw in question for kw in BTC_KEYWORDS):
        return False
    # Must NOT contain any skip keyword
    if any(kw in question for kw in SKIP_KEYWORDS):
        return False
    return True


def classify_market(market: dict) -> str:
    """Classify market into category."""
    question = (market.get("question") or "").lower()
    if any(kw in question for kw in PRICE_KEYWORDS):
        return "price"
    if any(kw in question for kw in EVENT_KEYWORDS):
        return "event"
    return "other"


def parse_outcome_prices(market: dict) -> dict:
    """Parse outcomePrices JSON string into dict."""
    try:
        prices = json.loads(market.get("outcomePrices", "[]"))
        outcomes = json.loads(market.get("outcomes", "[]"))
        if len(prices) >= 2 and len(outcomes) >= 2:
            return {
                "yes_pct": round(float(prices[0]) * 100, 1),
                "no_pct": round(float(prices[1]) * 100, 1),
                "yes_label": outcomes[0],
                "no_label": outcomes[1],
            }
    except (json.JSONDecodeError, IndexError, ValueError, TypeError):
        pass
    return {"yes_pct": 50, "no_pct": 50, "yes_label": "Yes", "no_label": "No"}


def format_card(markets: list, now: datetime) -> str:
    """Render the prediction markets card."""
    lines = []
    lines.append("═══════════════════════════════════════════")
    lines.append("  POLYMARKET — BTC PREDICTION MARKETS")
    lines.append(f"  {now.strftime('%Y-%m-%d %H:%M')} MYT")
    lines.append("═══════════════════════════════════════════")
    lines.append("")

    categories = {"price": ("PRICE TARGETS", []), "event": ("EVENTS", []), "other": ("OTHER", [])}

    for m in markets:
        cat = classify_market(m)
        categories[cat][1].append(m)

    bull_weight = 0
    bear_weight = 0

    for label, cat_markets in categories.values():
        if not cat_markets:
            continue
        lines.append(f"  {label}:")
        for m in cat_markets[:5]:
            question = m.get("question", "?")
            prices = parse_outcome_prices(m)
            vol = float(m.get("volume", 0))
            short_q = question[:65] + ("..." if len(question) > 65 else "")
            lines.append(f"  {short_q}")
            lines.append(f"     YES: {prices['yes_pct']}%  |  Vol: ${vol/1e6:.1f}M")

            # Weight sentiment — YES > 50% = bullish, YES < 50% = bearish
            # Weight by: distance from 50% × volume
            yes = prices["yes_pct"]
            if yes > 55:
                bull_weight += (yes - 50) * vol
            elif yes < 45:
                bear_weight += (50 - yes) * vol
            # 45-55 = neutral — don't count
        lines.append("")

    # Sentiment summary
    total = bull_weight + bear_weight
    if total > 0:
        bull_pct = round(bull_weight / total * 100)
        bear_pct = 100 - bull_pct
        lines.append(f"  SENTIMENT: {bull_pct}% BULL / {bear_pct}% BEAR")
        if bull_pct >= 65:
            lines.append("  Implies: Market pricing in upside")
        elif bear_pct >= 65:
            lines.append("  Implies: Market pricing in downside risk")
        else:
            lines.append("  Implies: Market uncertain — no clear edge")
    else:
        lines.append("  SENTIMENT: No volume-weighted signal")

    # Most active
    if markets:
        top = max(markets, key=lambda m: float(m.get("volume", 0)))
        lines.append(f"  Most active: {top.get('question', '?')[:60]}...")

    return "\n".join(lines)


def main():
    now = datetime.now(MYT)
    ts = now.isoformat()

    markets = fetch_btc_markets()
    btc_markets = [m for m in markets if is_btc_market(m) and float(m.get("volume", 0)) >= MIN_VOLUME]
    btc_markets.sort(key=lambda m: float(m.get("volume", 0)), reverse=True)

    # Log to JSONL
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    log_entry = {
        "ts": ts,
        "count": len(btc_markets),
        "markets": [
            {
                "question": m.get("question"),
                "yes_pct": parse_outcome_prices(m)["yes_pct"],
                "volume": float(m.get("volume", 0)),
                "category": classify_market(m),
            }
            for m in btc_markets[:10]
        ],
    }
    with open(JSONL_PATH, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Print card
    if not btc_markets:
        print("No active BTC prediction markets found on Polymarket.")
    else:
        print(format_card(btc_markets, now))

    print(f"\n[POLYMARKET] {len(btc_markets)} BTC markets logged")


if __name__ == "__main__":
    main()
