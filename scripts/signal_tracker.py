#!/usr/bin/env python3
"""
Signal Tracker — 3-state evolution model (STRENGTHENED / WEAKENED / FALSIFIED)

Per GetClaw's recommendation: adds intermediate states between binary ACTIVE/RESOLVED.
Wired to the events library (knowledge/events_and_disruptions.md).

Logic:
- Reads events with OPEN/ACTIVE/UNRESOLVED status
- Compares current BTC price + pipeline state against event predictions
- Outputs evolution state and confidence

Usage: python3 scripts/signal_tracker.py
Output: data/signal_tracker.json
"""
import json
import os
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

# === Paths ===
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
EVENTS_PATH = os.path.join(REPO_ROOT, "events_and_disruptions.md")
STRUCTURAL_PATH = os.path.join(REPO_ROOT, "data", "structural.json")
MACRO_PATH = os.path.join(REPO_ROOT, "data", "macro.json")
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "signal_tracker.json")

# === BTC price fetch (lightweight) ===
def get_btc_price() -> Optional[float]:
    """Get current BTC price from structural.json (always fresh from 15-min collector)."""
    try:
        with open(STRUCTURAL_PATH) as f:
            data = json.load(f)
        # Navigate to current price
        sr = data.get("sr_bands", {})
        for tf in ["1h", "4h", "1d"]:
            if tf in sr and isinstance(sr.get(tf), dict):
                price = sr[tf].get("current_price")
                if price:
                    return float(price)
        return None
    except Exception:
        return None


def extract_btc_price_from_event(text: str) -> Optional[float]:
    """Extract BTC price mentioned in event description body.
    
    Handles patterns like:
    - "~$32B at $64K"
    - "BTC $64,472"
    - "bitcoin price: $97,200"
    - "500K BTC"
    """
    patterns = [
        r'at\s+\$?(\d{2,3}(?:[,.]\d{3})?)\s*[Kk]\b',
        r'BTC\s+\$?(\d{2,3}(?:[,.]\d{3})?)',
        r'[$](\d{2,3}(?:[,.]\d{3})?)\s*[Kk]?\b',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                val = float(m.group(1).replace(",", ""))
                # If under 1000, it's likely in K notation
                if val < 1000 and ("K" in m.group(0).upper() or "k" in m.group(0)):
                    val *= 1000
                if 5000 < val < 1000000:
                    return val
            except ValueError:
                continue
    return None


def detect_thesis(text: str) -> Tuple[bool, bool]:
    """Detect if the event thesis is bearish or bullish from text.
    Returns (is_bearish, is_bullish)."""
    t = text.lower()
    bearish = ["crash", "correction", "drawdown", "sell", "dump", "decline",
               "bear", "dip", "capitulation", "breakdown", "sweep", "tighten",
               "tariff", "risk-off", "liquidation cascade", "unwind",
               "expiration", "expiry", "pinning effect", "volatility window",
               "fragile", "firing", "coverage crisis", "below par",
               "forced", "restructuring"]
    bullish = ["rally", "surge", "pump", "bull", "breakout", "ath",
               "approval", "launch", "halving", "buy", "accumulation",
               "sanctions relief", "mou", "dot plot", "rate cut",
               "dovish", "easing"]

    is_bearish = any(kw in t for kw in bearish)
    is_bullish = any(kw in t for kw in bullish)
    return is_bearish, is_bullish


def parse_events_file() -> List[Dict]:
    """Extract active (unresolved) events from events_and_disruptions.md."""
    if not os.path.exists(EVENTS_PATH):
        return []

    with open(EVENTS_PATH) as f:
        text = f.read()

    events = []
    # Find all EVENT blocks
    event_blocks = re.split(r'\n## EVENT (\d+)', text)

    for i in range(1, len(event_blocks), 2):
        if i + 1 >= len(event_blocks):
            break
        evt_id = event_blocks[i]
        evt_content = event_blocks[i + 1]

        # Extract fields
        title_match = re.search(r'^\s*—?\s*(.+?)$', evt_content.strip(), re.MULTILINE)
        date_match = re.search(r'DATE:\s*(.+?)$', evt_content, re.MULTILINE)
        status_match = re.search(r'STATUS:\s*(.+?)$', evt_content, re.MULTILINE)
        economy_match = re.search(r'ECONOMY:\s*\n(.*?)(?=\n\n|\n[A-Z]|\n##|\Z)', evt_content, re.DOTALL)

        title = title_match.group(1).strip() if title_match else ""
        date_str = date_match.group(1).strip() if date_match else ""
        status = (status_match.group(1).strip() if status_match else "").upper()
        description = (economy_match.group(1).strip() if economy_match else "") + " " + title

        # Extract BTC price from description
        btc_at_event = extract_btc_price_from_event(description)
        # Detect thesis direction from full text
        is_bearish, is_bullish = detect_thesis(description)

        # Determine if active
        active_keywords = ["ACTIVE", "OPEN", "MONITORING", "UNRESOLVED", "WATCH", "ALERT", "FIRING", "ONGOING"]
        is_active = any(kw in status for kw in active_keywords) or not status

        events.append({
            "id": f"EVENT_{evt_id.zfill(3)}",
            "title": title,
            "date": date_str,
            "status": status or "UNKNOWN",
            "btc_at_event": btc_at_event,
            "description": description[:300],
            "is_active": is_active,
            "is_bearish": is_bearish,
            "is_bullish": is_bullish,
        })

    return events


def evaluate_evolution(event: Dict, current_btc: float) -> Tuple[str, str]:
    """
    Compare current BTC price vs event prediction to determine evolution state.

    Heuristic rules:
    - If bearish thesis + BTC below event price → STRENGTHENED
    - If bearish thesis + BTC recovered above → WEAKENING
    - If bearish thesis + BTC new high → FALSIFIED
    - If bullish thesis + BTC above event price → STRENGTHENED
    - If bullish thesis + BTC dropped below → WEAKENING
    - Default: MONITORING (no clear direction)
    """
    btc_event = event.get("btc_at_event")
    is_bearish = event.get("is_bearish", False)
    is_bullish = event.get("is_bullish", False)

    # If no BTC price at event but we have a thesis, use current as baseline
    if not btc_event and (is_bearish or is_bullish):
        btc_event = current_btc  # use current as reference point

    if not btc_event or (not is_bearish and not is_bullish):
        return "MONITORING", "No directional thesis detected or missing BTC price at event"

    if is_bearish:
        if current_btc < btc_event * 0.97:
            return "STRENGTHENED", f"BTC ${current_btc:.0f} below event level ${btc_event:.0f} — bearish thesis confirmed"
        elif current_btc > btc_event * 1.03:
            return "FALSIFIED", f"BTC ${current_btc:.0f} rallied above event level ${btc_event:.0f} — bearish thesis invalidated"
        elif current_btc > btc_event * 1.001:  # > 0.1% above (avoids equal-price fallthrough)
            return "WEAKENING", f"BTC ${current_btc:.0f} recovering above event level ${btc_event:.0f} — bearish pressure easing"
        else:
            return "MONITORING", f"BTC ${current_btc:.0f} at event level ${btc_event:.0f} — no clear deviation"

    if is_bullish:
        if current_btc > btc_event * 1.03:
            return "STRENGTHENED", f"BTC ${current_btc:.0f} above event level ${btc_event:.0f} — bullish thesis confirmed"
        elif current_btc < btc_event * 0.97:
            return "FALSIFIED", f"BTC ${current_btc:.0f} dropped below event level ${btc_event:.0f} — bullish thesis invalidated"
        elif current_btc < btc_event:
            return "WEAKENING", f"BTC ${current_btc:.0f} slipped below event level ${btc_event:.0f} — bullish momentum fading"
        else:
            return "STRENGTHENED", f"BTC ${current_btc:.0f} holding above event level ${btc_event:.0f} — bullish thesis intact"

    return "MONITORING", "Insufficient data for evolution assessment"


def main():
    current_btc = get_btc_price()
    if not current_btc:
        print("[signal_tracker] ERROR: Cannot get BTC price from structural.json")
        return

    events = parse_events_file()
    active_events = [e for e in events if e["is_active"]]
    print(f"[signal_tracker] Found {len(events)} events, {len(active_events)} active")

    tracked = []
    for evt in active_events:
        state, reasoning = evaluate_evolution(evt, current_btc)
        # Show effective BTC price used (may be fallback to current if event price unknown)
        effective_btc = evt["btc_at_event"] if evt["btc_at_event"] else current_btc
        tracked.append({
            "event_id": evt["id"],
            "title": evt["title"],
            "date": evt["date"],
            "btc_at_event": effective_btc,
            "btc_at_event_source": "extracted" if evt["btc_at_event"] else "fallback_current",
            "current_btc": current_btc,
            "evolution": state,
            "reasoning": reasoning,
        })
        print(f"  {evt['id']} → {state}: {reasoning[:80]}")

    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_btc": current_btc,
        "total_events": len(events),
        "active_events": len(active_events),
        "tracked_signals": tracked,
        "summary": {
            "strengthened": sum(1 for t in tracked if t["evolution"] == "STRENGTHENED"),
            "weakening": sum(1 for t in tracked if t["evolution"] == "WEAKENING"),
            "falsified": sum(1 for t in tracked if t["evolution"] == "FALSIFIED"),
            "monitoring": sum(1 for t in tracked if t["evolution"] == "MONITORING"),
        },
    }

    # Atomic write
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    tmp_path = OUTPUT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(output, f, indent=2, default=str)
    os.replace(tmp_path, OUTPUT_PATH)
    print(f"[signal_tracker] Written to {OUTPUT_PATH}")
    print(f"  Summary: {output['summary']}")


if __name__ == "__main__":
    main()
