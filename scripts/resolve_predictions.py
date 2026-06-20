#!/usr/bin/env python3
"""
Outcome Resolution Engine — resolve predictions and trading signals.
Runs daily in the deploy pipeline.
Checks historical prices via Binance API and updates data/predictions.json,
data/signal_stats.json, data/track-record-summary.json, and data/confidence_tracker.json.
"""
import json
import os
import urllib.request
import logging
from datetime import datetime, timezone, timedelta

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger("resolver")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(SCRIPT_DIR)
DATA_DIR = os.path.join(REPO_ROOT, "data")
PREDICTIONS_PATH = os.path.join(DATA_DIR, "predictions.json")
STATS_PATH = os.path.join(DATA_DIR, "signal_stats.json")
SUMMARY_PATH = os.path.join(DATA_DIR, "track-record-summary.json")
CONFIDENCE_PATH = os.path.join(DATA_DIR, "confidence_tracker.json")


def fetch_klines(start_ms, end_ms, interval="1h"):
    """Fetch 1h klines from Binance API for start_ms to end_ms range."""
    url = f"https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval={interval}&startTime={start_ms}&endTime={end_ms}&limit=1000"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        log.warning("Failed to fetch klines from Binance: %s", e)
        return None


def resolve_predictions():
    if not os.path.exists(PREDICTIONS_PATH):
        log.info("No predictions.json found. Nothing to resolve.")
        return

    try:
        with open(PREDICTIONS_PATH) as f:
            content = json.load(f)
            predictions = content.get("predictions", [])
    except Exception as e:
        log.error("Failed to load predictions.json: %s", e)
        return

    now = datetime.now(timezone.utc)
    updated = False

    for p in predictions:
        if p.get("resolved", False):
            continue

        created_at_str = p.get("created_at")
        if not created_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
        except Exception as e:
            log.warning("Invalid timestamp in prediction: %s", e)
            continue

        start_ms = int(created_at.timestamp() * 1000)

        if p.get("type") == "regime_change":
            # Horizons: 1d, 7d, 30d
            outcomes = p.get("outcomes", {})
            btc_price_at_call = p.get("btc_price_at_call")
            direction = p.get("direction", "neutral")

            if not btc_price_at_call:
                p["resolved"] = True
                updated = True
                continue

            all_horizons_resolved = True
            for horizon, days in [("1d", 1), ("7d", 7), ("30d", 30)]:
                if outcomes.get(horizon) is not None:
                    continue

                end_dt = created_at + timedelta(days=days)
                if now < end_dt:
                    all_horizons_resolved = False
                    continue

                end_ms = int(end_dt.timestamp() * 1000)
                # Fetch klines in window to get close, high, low
                klines = fetch_klines(start_ms, end_ms, "1h")
                if not klines or len(klines) == 0:
                    all_horizons_resolved = False
                    continue

                btc_price_then = float(klines[-1][4])
                min_price = min(float(k[3]) for k in klines)
                max_price = max(float(k[2]) for k in klines)
                price_change_pct = (btc_price_then - btc_price_at_call) / btc_price_at_call

                direction_correct = False
                if direction == "bullish":
                    direction_correct = price_change_pct > 0
                elif direction == "bearish":
                    direction_correct = price_change_pct < 0
                elif direction == "neutral":
                    # Correct if it didn't suffer a >5% drawdown
                    drawdown = (btc_price_at_call - min_price) / btc_price_at_call
                    direction_correct = drawdown < 0.05

                outcomes[horizon] = {
                    "price_then": btc_price_then,
                    "price_change_pct": round(price_change_pct * 100, 2),
                    "min_price": min_price,
                    "max_price": max_price,
                    "direction_correct": direction_correct
                }
                updated = True

            p["outcomes"] = outcomes
            if all_horizons_resolved:
                p["resolved"] = True
                updated = True

        elif p.get("type") == "trading_signal":
            # Actionable signal with entry, target, stop loss
            entry = p.get("entry")
            stop_loss = p.get("stop_loss")
            target = p.get("target")

            if not entry or not stop_loss or not target:
                p["resolved"] = True
                updated = True
                continue

            now_ms = int(now.timestamp() * 1000)
            klines = fetch_klines(start_ms, now_ms, "1h")
            if not klines or len(klines) == 0:
                continue

            # Check chronologically
            outcome = None
            exit_price = None
            resolved_at = None

            for k in klines:
                candle_time_ms = int(k[0])
                low = float(k[3])
                high = float(k[2])
                close = float(k[4])

                # Check if stop hit
                if p["direction"] == "bullish" and low <= stop_loss:
                    outcome = "loss"
                    exit_price = stop_loss
                    resolved_at = datetime.fromtimestamp(candle_time_ms / 1000, tz=timezone.utc).isoformat()
                    break
                elif p["direction"] == "bearish" and high >= stop_loss:
                    outcome = "loss"
                    exit_price = stop_loss
                    resolved_at = datetime.fromtimestamp(candle_time_ms / 1000, tz=timezone.utc).isoformat()
                    break

                # Check if target hit
                if p["direction"] == "bullish" and high >= target:
                    outcome = "win"
                    exit_price = target
                    resolved_at = datetime.fromtimestamp(candle_time_ms / 1000, tz=timezone.utc).isoformat()
                    break
                elif p["direction"] == "bearish" and low <= target:
                    outcome = "win"
                    exit_price = target
                    resolved_at = datetime.fromtimestamp(candle_time_ms / 1000, tz=timezone.utc).isoformat()
                    break

            # If not hit, check for 30d expiry
            if outcome is None:
                if now >= created_at + timedelta(days=30):
                    outcome = "expired"
                    exit_price = float(klines[-1][4])
                    resolved_at = (created_at + timedelta(days=30)).isoformat()

            if outcome is not None:
                p["outcomes"] = {
                    "outcome": outcome,
                    "exit_price": exit_price,
                    "resolved_at": resolved_at,
                    "price_change_pct": round(((exit_price - entry) / entry) * 100, 2)
                }
                p["resolved"] = True
                updated = True

    if updated:
        try:
            tmp_path = PREDICTIONS_PATH + ".tmp"
            with open(tmp_path, "w") as f:
                json.dump({"predictions": predictions}, f, indent=2)
            os.replace(tmp_path, PREDICTIONS_PATH)
            log.info("Resolved pending predictions and saved predictions.json")
        except Exception as e:
            log.error("Failed to write updated predictions.json: %s", e)

    # Re-calculate statistics and write summaries
    write_summaries(predictions)


def write_summaries(predictions):
    # 1. Write signal_stats.json (for live dashboard display)
    stats = {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "expired": 0,
        "open": 0
    }

    for p in predictions:
        if p.get("type") == "trading_signal":
            stats["total"] += 1
            if not p.get("resolved", False):
                stats["open"] += 1
            else:
                outcome = p.get("outcomes", {}).get("outcome")
                if outcome == "win":
                    stats["wins"] += 1
                elif outcome == "loss":
                    stats["losses"] += 1
                elif outcome == "expired":
                    stats["expired"] += 1

    try:
        with open(STATS_PATH, "w") as f:
            json.dump(stats, f, indent=2)
        log.info("Saved signal_stats.json: %s", stats)
    except Exception as e:
        log.error("Failed to write signal_stats.json: %s", e)

    # 2. Write confidence_tracker.json (calibration data)
    now = datetime.now(timezone.utc)
    cutoff_90d = now - timedelta(days=90)

    conf_stats = {
        "HIGH": {"wins": 0, "losses": 0, "expired": 0, "total": 0},
        "MEDIUM": {"wins": 0, "losses": 0, "expired": 0, "total": 0},
        "LOW": {"wins": 0, "losses": 0, "expired": 0, "total": 0}
    }

    for p in predictions:
        if p.get("type") == "trading_signal" and p.get("resolved", False):
            created_at_str = p.get("created_at")
            if not created_at_str:
                continue
            try:
                created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            except Exception:
                continue

            if created_at >= cutoff_90d:
                conf = p.get("confidence", "MEDIUM")
                if conf in conf_stats:
                    outcome = p.get("outcomes", {}).get("outcome")
                    conf_stats[conf]["total"] += 1
                    if outcome == "win":
                        conf_stats[conf]["wins"] += 1
                    elif outcome == "loss":
                        conf_stats[conf]["losses"] += 1
                    elif outcome == "expired":
                        conf_stats[conf]["expired"] += 1

    # Load existing tracker template
    tracker = {
        "_comment": "Confidence Calibration Tracker. Updated quarterly. Auto-downgrade triggers when HIGH label drops below 65% for 30 days. Calibration: HIGH >=70% hit rate + >=30 trades, MEDIUM 50-70% + >=15 trades, LOW <50% or <15 trades.",
        "last_updated": now.isoformat(),
        "period_days": 90,
        "summary": {
            "HIGH": { "hit_rate": None, "sample_size": 0, "status": "NO_DATA" },
            "MEDIUM": { "hit_rate": None, "sample_size": 0, "status": "NO_DATA" },
            "LOW": { "hit_rate": None, "sample_size": 0, "status": "NO_DATA" }
        },
        "alerts": [],
        "status": "NO_DATA — awaiting trade history. Requires minimum 15 trades per label over 90 days."
    }

    if os.path.exists(CONFIDENCE_PATH):
        try:
            with open(CONFIDENCE_PATH) as f:
                tracker = json.load(f)
        except Exception:
            pass

    tracker["last_updated"] = now.isoformat()
    
    # Calculate rates
    calibrated_count = 0
    total_trades_all = 0
    for label in ["HIGH", "MEDIUM", "LOW"]:
        stats_label = conf_stats[label]
        total = stats_label["total"]
        total_trades_all += total
        tracker["summary"][label]["sample_size"] = total

        if total > 0:
            hit_rate = stats_label["wins"] / total
            tracker["summary"][label]["hit_rate"] = round(hit_rate, 4)

            # Standard statuses
            if label == "HIGH":
                if total >= 30 and hit_rate >= 0.70:
                    tracker["summary"][label]["status"] = "CALIBRATED"
                    calibrated_count += 1
                elif total < 30:
                    tracker["summary"][label]["status"] = "INSUFFICIENT_SAMPLE"
                else:
                    tracker["summary"][label]["status"] = "MISCALIBRATED"
            elif label == "MEDIUM":
                if total >= 15 and 0.50 <= hit_rate < 0.70:
                    tracker["summary"][label]["status"] = "CALIBRATED"
                    calibrated_count += 1
                elif total < 15:
                    tracker["summary"][label]["status"] = "INSUFFICIENT_SAMPLE"
                else:
                    tracker["summary"][label]["status"] = "MISCALIBRATED"
            elif label == "LOW":
                tracker["summary"][label]["status"] = "MONITORING"
        else:
            tracker["summary"][label]["hit_rate"] = None
            tracker["summary"][label]["status"] = "NO_DATA"

    # Status updates
    if total_trades_all == 0:
        tracker["status"] = "NO_DATA — awaiting trade history. Requires minimum 15 trades per label over 90 days."
    else:
        high_rate = tracker["summary"]["HIGH"]["hit_rate"]
        med_rate = tracker["summary"]["MEDIUM"]["hit_rate"]
        hr_str = f"{high_rate*100:.1f}%" if high_rate is not None else "N/A"
        mr_str = f"{med_rate*100:.1f}%" if med_rate is not None else "N/A"
        tracker["status"] = f"Active calibration check. HIGH rate: {hr_str} ({tracker['summary']['HIGH']['sample_size']} trades), MEDIUM rate: {mr_str} ({tracker['summary']['MEDIUM']['sample_size']} trades)."

    try:
        with open(CONFIDENCE_PATH, "w") as f:
            json.dump(tracker, f, indent=2)
        log.info("Saved confidence_tracker.json")
    except Exception as e:
        log.error("Failed to write confidence_tracker.json: %s", e)

    # 3. Write track-record-summary.json
    total_regimes = 0
    correct_regimes = {
        "1d": {"wins": 0, "total": 0},
        "7d": {"wins": 0, "total": 0},
        "30d": {"wins": 0, "total": 0}
    }

    for p in predictions:
        if p.get("type") == "regime_change":
            total_regimes += 1
            outcomes = p.get("outcomes", {})
            for horizon in ["1d", "7d", "30d"]:
                h_data = outcomes.get(horizon)
                if h_data and isinstance(h_data, dict):
                    correct_regimes[horizon]["total"] += 1
                    if h_data.get("direction_correct", False):
                        correct_regimes[horizon]["wins"] += 1

    summary = {
        "last_updated": now.isoformat(),
        "signals": {
            "all_time": stats,
            "trailing_90d": {
                "total": sum(conf_stats[l]["total"] for l in conf_stats),
                "wins": sum(conf_stats[l]["wins"] for l in conf_stats),
                "losses": sum(conf_stats[l]["losses"] for l in conf_stats),
                "expired": sum(conf_stats[l]["expired"] for l in conf_stats)
            }
        },
        "regime_changes": {
            "total_calls": total_regimes,
            "accuracy": {
                "1d": {
                    "hit_rate": round(correct_regimes["1d"]["wins"] / correct_regimes["1d"]["total"], 4) if correct_regimes["1d"]["total"] > 0 else None,
                    "sample_size": correct_regimes["1d"]["total"]
                },
                "7d": {
                    "hit_rate": round(correct_regimes["7d"]["wins"] / correct_regimes["7d"]["total"], 4) if correct_regimes["7d"]["total"] > 0 else None,
                    "sample_size": correct_regimes["7d"]["total"]
                },
                "30d": {
                    "hit_rate": round(correct_regimes["30d"]["wins"] / correct_regimes["30d"]["total"], 4) if correct_regimes["30d"]["total"] > 0 else None,
                    "sample_size": correct_regimes["30d"]["total"]
                }
            }
        }
    }

    try:
        with open(SUMMARY_PATH, "w") as f:
            json.dump(summary, f, indent=2)
        log.info("Saved track-record-summary.json: %s", summary)
    except Exception as e:
        log.error("Failed to write track-record-summary.json: %s", e)


if __name__ == "__main__":
    resolve_predictions()
