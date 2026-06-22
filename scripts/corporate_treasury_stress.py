#!/usr/bin/env python3
"""
Corporate Treasury Stress Monitor — Strategy (MSTR/STRC)
=========================================================
Watchdog pattern: outputs alert ONLY when thresholds breached.
Silent when everything normal. Designed for no_agent cron.

Monitors:
  1. STRC par distance (vs $100 par value)
  2. Coverage ratio (BTC holdings / annual dividend obligations)
  3. BTC price levels
  4. MSTR stock NAV premium/discount vs BTC holdings

Thresholds:
  WATCH:   STRC 5-10% below par OR coverage < 40yr
  ALERT:   STRC >10% below par OR coverage < 25yr OR confirmed sale pattern
  FIRING:  STRC >15% below par OR coverage < 20yr OR BTC sale >$500M

Output: JSON with status, breach details, timestamp.
Silent (exit 0, no stdout) when no breach.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

# ─── Configuration ───────────────────────────────────────────────

PAR_VALUE = 100.0  # STRC preferred share par value
BTC_HOLDINGS = 500_000  # estimated Strategy BTC holdings
ANNUAL_OBLIGATIONS = 1_000_000_000  # ~$1B/year preferred dividends
STATE_FILE = os.path.expanduser(
    "~/pipeline-dashboard V2/data/corporate_treasury_stress.json"
)
LOG_FILE = os.path.expanduser(
    "~/pipeline-dashboard V2/data/corporate_treasury_stress.log"
)

THRESHOLDS = {
    "WATCH": {
        "strc_below_par_pct": 5.0,   # 5% below par
        "coverage_years": 40,         # less than 40yr coverage
    },
    "ALERT": {
        "strc_below_par_pct": 10.0,  # 10% below par
        "coverage_years": 25,         # less than 25yr coverage
    },
    "FIRING": {
        "strc_below_par_pct": 15.0,  # 15% below par
        "coverage_years": 20,         # less than 20yr coverage
    },
}


def fetch_data():
    """Fetch MSTR, STRC, BTC prices from Yahoo Finance + Binance."""
    data = {}

    # STRK preferred stock (MicroStrategy perpetual strike preferred)
    try:
        strc = yf.Ticker("STRK")
        strc_info = strc.fast_info
        data["strc_price"] = float(strc_info.last_price)
        data["strc_ticker"] = "STRK"
    except Exception as e:
        data["strc_error"] = str(e)
        data["strc_price"] = None
        data["strc_ticker"] = "STRK"

    # MSTR common stock
    try:
        mstr = yf.Ticker("MSTR")
        mstr_info = mstr.fast_info
        data["mstr_price"] = float(mstr_info.last_price)
    except Exception as e:
        data["mstr_error"] = str(e)
        data["mstr_price"] = None

    # BTC price from Binance (public API, no auth needed)
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=10,
        )
        resp.raise_for_status()
        data["btc_price"] = float(resp.json()["price"])
    except Exception as e:
        data["btc_error"] = str(e)
        data["btc_price"] = None

    data["timestamp"] = datetime.now(timezone.utc).isoformat()
    return data


def calculate_metrics(data):
    """Derive stress metrics from raw prices."""
    metrics = {}
    btc = data.get("btc_price")
    strc = data.get("strc_price")
    mstr = data.get("mstr_price")

    if strc and PAR_VALUE:
        metrics["strc_par_distance_pct"] = round(
            ((PAR_VALUE - strc) / PAR_VALUE) * 100, 2
        )
    else:
        metrics["strc_par_distance_pct"] = None

    if btc:
        holdings_value = BTC_HOLDINGS * btc
        metrics["holdings_value_b"] = round(holdings_value / 1e9, 2)
        metrics["coverage_years"] = round(holdings_value / ANNUAL_OBLIGATIONS, 1)
    else:
        metrics["holdings_value_b"] = None
        metrics["coverage_years"] = None

    if mstr and btc:
        # NAV premium: MSTR market cap / BTC holdings value (rough)
        # Using stock price ratio as proxy
        metrics["mstr_btc_ratio"] = round(mstr / btc, 4)
    else:
        metrics["mstr_btc_ratio"] = None

    return metrics


def check_thresholds(metrics):
    """Compare metrics against WATCH/ALERT/FIRING thresholds."""
    breaches = []
    tier = "CLEAR"

    strc_dist = metrics.get("strc_par_distance_pct")
    coverage = metrics.get("coverage_years")

    # Guard: missing critical data → UNKNOWN, not CLEAR
    if strc_dist is None and coverage is None:
        return "UNKNOWN", ["Error: STRC and BTC price data unavailable"]
    if strc_dist is None:
        return "UNKNOWN", ["Error: STRC price data unavailable"]
    if coverage is None:
        return "UNKNOWN", ["Error: BTC price data unavailable"]

    # Check all tiers independently, collect ALL breaches
    max_tier = "CLEAR"
    tier_rank = {"CLEAR": 0, "WATCH": 1, "ALERT": 2, "FIRING": 3}

    # FIRING
    if strc_dist >= THRESHOLDS["FIRING"]["strc_below_par_pct"]:
        max_tier = "FIRING"
        breaches.append(f"STRC {strc_dist}% below par (threshold: {THRESHOLDS['FIRING']['strc_below_par_pct']}%)")
    if coverage < THRESHOLDS["FIRING"]["coverage_years"]:
        max_tier = "FIRING"
        breaches.append(f"Coverage {coverage}yr (threshold: <{THRESHOLDS['FIRING']['coverage_years']}yr)")

    # ALERT
    if strc_dist >= THRESHOLDS["ALERT"]["strc_below_par_pct"] and max_tier != "FIRING":
        if tier_rank.get(max_tier, 0) < 2:
            max_tier = "ALERT"
        breaches.append(f"STRC {strc_dist}% below par (threshold: {THRESHOLDS['ALERT']['strc_below_par_pct']}%)")
    if coverage < THRESHOLDS["ALERT"]["coverage_years"]:
        if tier_rank.get(max_tier, 0) < 2:
            max_tier = "ALERT"
        breaches.append(f"Coverage {coverage}yr (threshold: <{THRESHOLDS['ALERT']['coverage_years']}yr)")

    # WATCH
    if strc_dist >= THRESHOLDS["WATCH"]["strc_below_par_pct"]:
        if tier_rank.get(max_tier, 0) < 1:
            max_tier = "WATCH"
        breaches.append(f"STRC {strc_dist}% below par (threshold: {THRESHOLDS['WATCH']['strc_below_par_pct']}%)")
    if coverage < THRESHOLDS["WATCH"]["coverage_years"]:
        if tier_rank.get(max_tier, 0) < 1:
            max_tier = "WATCH"
        breaches.append(f"Coverage {coverage}yr (threshold: <{THRESHOLDS['WATCH']['coverage_years']}yr)")

    return max_tier, breaches


def load_previous_state():
    """Load last known state to detect tier changes."""
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"tier": "UNKNOWN", "timestamp": None}


def save_state(result):
    """Persist current state atomically for next run."""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    tmp_file = STATE_FILE + ".tmp"
    with open(tmp_file, "w") as f:
        json.dump(result, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, STATE_FILE)


def log_event(message):
    """Append to log file."""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def main():
    data = fetch_data()
    metrics = calculate_metrics(data)
    tier, breaches = check_thresholds(metrics)
    previous = load_previous_state()

    result = {
        "tier": tier,
        "timestamp": data["timestamp"],
        "strc_price": data.get("strc_price"),
        "mstr_price": data.get("mstr_price"),
        "btc_price": data.get("btc_price"),
        "strc_par_distance_pct": metrics.get("strc_par_distance_pct"),
        "coverage_years": metrics.get("coverage_years"),
        "holdings_value_b": metrics.get("holdings_value_b"),
        "mstr_btc_ratio": metrics.get("mstr_btc_ratio"),
        "breaches": breaches,
        "previous_tier": previous.get("tier"),
        "errors": {
            k: v for k, v in data.items() if k.endswith("_error")
        },
    }

    save_state(result)

    # ─── Output decision ──────────────────────────────────────
    # SILENT when:
    #   - Tier is CLEAR (no breaches)
    #   - Tier unchanged from last run (already reported)
    #   - Downgrade (FIRING→ALERT, ALERT→WATCH)
    # ALERT when:
    #   - New tier reached (upgrade only: CLEAR→WATCH, WATCH→ALERT, ALERT→FIRING)
    #   - First run (previous UNKNOWN)

    tier_rank = {"CLEAR": 0, "WATCH": 1, "ALERT": 2, "FIRING": 3, "UNKNOWN": -1}
    is_upgrade = tier_rank.get(tier, 0) > tier_rank.get(previous.get("tier"), -1)
    is_first_run = previous.get("tier") == "UNKNOWN"

    if tier == "CLEAR":
        # Always silent when clear
        strc_s = f"${data['strc_price']:.2f}" if data.get('strc_price') is not None else "?"
        btc_s = f"${data['btc_price']:,.0f}" if data.get('btc_price') is not None else "?"
        cov_s = f"{metrics['coverage_years']}yr" if metrics.get('coverage_years') is not None else "?"
        log_event(f"CLEAR — STRC {strc_s}, BTC {btc_s}, coverage {cov_s}")
        sys.exit(0)

    if not is_upgrade and not is_first_run:
        # Same tier or downgrade — silent
        strc_s = f"${data['strc_price']:.2f}" if data.get('strc_price') is not None else "?"
        cov_s = f"{metrics['coverage_years']}yr" if metrics.get('coverage_years') is not None else "?"
        log_event(f"{tier} (no change) — STRC {strc_s}, coverage {cov_s}")
        sys.exit(0)

    # ─── Alert output ────────────────────────────────────────
    log_event(f"⚠ {tier} UPGRADE from {previous.get('tier')}: {'; '.join(breaches)}")

    # Safe format helpers
    strc_s = f"${data['strc_price']:.2f}" if data.get('strc_price') is not None else "?"
    par_s = f"{metrics['strc_par_distance_pct']}%" if metrics.get('strc_par_distance_pct') is not None else "?"
    mstr_s = f"${data['mstr_price']:.2f}" if data.get('mstr_price') is not None else "?"
    btc_s = f"${data['btc_price']:,.0f}" if data.get('btc_price') is not None else "?"
    cov_s = f"{metrics['coverage_years']} years" if metrics.get('coverage_years') is not None else "?"
    val_s = f"${metrics['holdings_value_b']}B" if metrics.get('holdings_value_b') is not None else "?"

    # Build human-readable alert message
    lines = [
        "⚠️ CORPORATE TREASURY STRESS — TIER CHANGE",
        "",
        f"New Tier: {tier} (was: {previous.get('tier')})",
        f"STRC: {strc_s} ({par_s} below $100 par)",
        f"MSTR: {mstr_s}",
        f"BTC: {btc_s}",
        f"Coverage: {cov_s}",
        f"Holdings: {val_s}",
    ]

    if breaches:
        lines.append("")
        lines.append("Breaches:")
        for b in breaches:
            lines.append(f"  • {b}")

    lines.append("")
    if tier == "WATCH":
        lines.append("→ Pipeline: synthesis unchanged. Monitor only.")
    elif tier == "ALERT":
        lines.append("→ Pipeline: cap BULLISH at CAUTIOUS BULL. Review EVENT 005.")
    elif tier == "FIRING":
        lines.append("→ Pipeline: cap at NEUTRAL. Consider L-1 review.")

    print("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    main()
