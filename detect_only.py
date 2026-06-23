#!/usr/bin/env python3
"""
Pipeline Dashboard — 15-Minute Signal Detection (Lightweight)

Runs every 15 minutes. Does NOT call full collect.py — only:
1. Reads cached structural.json + derivatives.json + gate0.json + btc_price.json
2. Re-runs the 3 detection functions (VAL absorption, breakout-retest, breakdown-retest)
3. Writes updated signals into structural.json
4. Logs all signals to /tmp/btc_signal_history.json (win/loss/expired tracking)
5. Sends Telegram alert on ENTRY_SIGNAL (filtered by L0 gate)

This catches fast-moving setups between hourly full-collection cycles.
"""
import os
import sys
import json
import subprocess
import fcntl
from pathlib import Path
from datetime import datetime, timezone

BASE = Path(__file__).parent
DATA = BASE / "data"
SIGNAL_HISTORY = "/tmp/btc_signal_history.json"
LAST_ALERT = "/tmp/btc_last_alert.json"
TELEGRAM_CHAT_ID = "1273979711"  # Wilee's home channel


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def write_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, 'w') as f:
        json.dump(data, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def send_telegram_alert(text):
    """Send alert via Hermes send_message tool — not available in subprocess, so use curl fallback."""
    # We can't call Hermes tools from here. Write alert to a file that the cron wrapper picks up.
    alert_file = "/tmp/btc_pending_alert.txt"
    with open(alert_file, 'w') as f:
        f.write(text)
    print(f"📢 Alert queued: {alert_file}")


def log_signal(signal):
    """Append signal to history file for win/loss tracking."""
    history = read_json(SIGNAL_HISTORY) or {"signals": []}
    entry = {
        "timestamp": ts(),
        "signal": signal.get("signal", "unknown"),
        "direction": signal.get("direction", "LONG" if signal.get("signal", "").startswith("BREAKOUT") or signal.get("signal") == "VAL_ABSORPTION" else "SHORT"),
        "level": signal.get("level"),
        "price": signal.get("price"),
        "stop_loss": signal.get("stop_loss"),
        "target": signal.get("target"),
        "confidence": signal.get("confidence"),
        "outcome": None,  # Tracked later: WIN / LOSS / EXPIRED
        "outcome_price": None,
    }
    history["signals"].append(entry)
    # Keep last 200 signals
    history["signals"] = history["signals"][-200:]
    write_json(SIGNAL_HISTORY, history)


def track_outcomes():
    """Check if past signals hit target, stop, or expired (older than 48h)."""
    history = read_json(SIGNAL_HISTORY)
    if not history or "signals" not in history:
        return

    btc_price_data = read_json(str(DATA / "btc_price.json"))
    if not btc_price_data:
        return
    current_price = btc_price_data.get("price")
    if not current_price:
        return
    current_price = float(current_price)

    now = datetime.now(timezone.utc)
    changed = False

    for sig in history["signals"]:
        if sig.get("outcome") is not None:
            continue  # Already tracked

        # Parse timestamp
        try:
            sig_time = datetime.strptime(sig["timestamp"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except Exception:
            continue

        # Expired after 48h
        if (now - sig_time).total_seconds() > 48 * 3600:
            sig["outcome"] = "EXPIRED"
            sig["outcome_price"] = current_price
            changed = True
            continue

        level = sig.get("level") or 0
        stop = sig.get("stop_loss") or 0
        target = sig.get("target") or 0
        direction = sig.get("direction", "LONG")

        if not level or not stop:
            continue

        if direction == "LONG":
            # WIN: price >= target
            if target and current_price >= target:
                sig["outcome"] = "WIN"
                sig["outcome_price"] = current_price
                changed = True
            # LOSS: price <= stop
            elif current_price <= stop:
                sig["outcome"] = "LOSS"
                sig["outcome_price"] = current_price
                changed = True
        else:  # SHORT
            # WIN: price <= target
            if target and current_price <= target:
                sig["outcome"] = "WIN"
                sig["outcome_price"] = current_price
                changed = True
            # LOSS: price >= stop
            elif current_price >= stop:
                sig["outcome"] = "LOSS"
                sig["outcome_price"] = current_price
                changed = True

    if changed:
        write_json(SIGNAL_HISTORY, history)


def get_signal_summary():
    """Return win/loss/expired stats from history."""
    history = read_json(SIGNAL_HISTORY)
    if not history or "signals" not in history:
        return {"total": 0, "wins": 0, "losses": 0, "expired": 0, "open": 0}

    wins = sum(1 for s in history["signals"] if s.get("outcome") == "WIN")
    losses = sum(1 for s in history["signals"] if s.get("outcome") == "LOSS")
    expired = sum(1 for s in history["signals"] if s.get("outcome") == "EXPIRED")
    open_sigs = sum(1 for s in history["signals"] if s.get("outcome") is None)

    return {"total": len(history["signals"]), "wins": wins, "losses": losses, "expired": expired, "open": open_sigs}


def main():
    print(f"Signal Detection (15min) — {ts()}")
    print("=" * 40)

    # Acquire lock — skip if collect.py is running (it's the authoritative writer)
    try:
        _lock_fd = open("/tmp/pipeline-collector.lock", "w")
        fcntl.flock(_lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError):
        print("⚠️  Full collector is running — skipping signal detection")
        return

    # Read cached data from last hourly collection
    structural = read_json(str(DATA / "structural.json"))
    derivatives = read_json(str(DATA / "derivatives.json"))
    gate0 = read_json(str(DATA / "gate0.json"))
    btc_price = read_json(str(DATA / "btc_price.json"))

    if not all([structural, derivatives, btc_price]):
        print("⚠️ Missing cached data — skipping (full collect.py hasn't run yet)")
        return

    # Import detection functions from collect.py
    sys.path.insert(0, str(BASE))
    from collect import detect_val_absorption, detect_breakout_retest, detect_breakdown_retest

    # Run all 3 detectors
    val_signal = detect_val_absorption(btc_price, structural, derivatives)
    brk_signal = detect_breakout_retest(btc_price, structural, derivatives)
    bkd_signal = detect_breakdown_retest(btc_price, structural, derivatives)

    # Update structural.json with fresh signals
    if val_signal:
        structural["val_absorption"] = val_signal
        print(f"VAL Absorption: {val_signal.get('signal', 'none')}")
    if brk_signal:
        structural["breakout_retest"] = brk_signal
        print(f"Breakout-Retest: {brk_signal.get('signal', 'none')}")
    if bkd_signal:
        structural["breakdown_retest"] = bkd_signal
        print(f"Breakdown-Retest: {bkd_signal.get('signal', 'none')}")

    # Write updated structural.json
    write_json(str(DATA / "structural.json"), structural)

    # Track outcomes for past signals
    track_outcomes()
    stats = get_signal_summary()
    print(f"Signal History: {stats['wins']}W / {stats['losses']}L / {stats['expired']}E / {stats['open']} open")

    # Write signal stats to data/ for frontend display
    write_json(str(DATA / "signal_stats.json"), stats)

    # ─── Telegram Alerts ────────────────────────────────────────
    gate_verdict = gate0.get("verdict", "UNKNOWN") if gate0 else "UNKNOWN"
    alert_signals = []  # Collect all alert-worthy signals

    for name, sig in [("VAL Absorption", val_signal), ("Breakout-Retest", brk_signal), ("Breakdown-Retest", bkd_signal)]:
        if not sig:
            continue
        sig_type = sig.get("signal", "")

        # Alert on ENTRY_SIGNAL, BREAKOUT_DETECTED, BREAKDOWN_DETECTED
        if sig_type in ("ENTRY_SIGNAL", "BREAKOUT_DETECTED", "BREAKDOWN_DETECTED"):
            # Check if we already alerted for this exact signal
            last = read_json(LAST_ALERT) or {}
            this_key = f"{sig_type}_{sig.get('level', 0)}_{sig.get('timestamp', '')}"

            if this_key not in last.get("keys", []):
                # New signal — build alert text
                direction = sig.get("direction", "LONG" if "BREAKOUT" in sig_type or sig_type == "VAL_ABSORPTION" else "SHORT")
                level = sig.get("level", 0)
                price = sig.get("price", 0)
                stop = sig.get("stop_loss")
                target = sig.get("target")
                confidence = sig.get("confidence", "?")

                # L0 filter
                if gate_verdict in ("PAUSE", "ABORT"):
                    l0_tag = f"\n⛔ L0 = {gate_verdict} — DISPLAY ONLY, no entry"
                elif gate_verdict == "TIGHTENED":
                    l0_tag = f"\n🟡 L0 = TIGHTENED — max 10x, tight stops"
                else:
                    l0_tag = f"\n🟢 L0 = {gate_verdict}"

                if sig_type == "ENTRY_SIGNAL":
                    icon = "🚀" if direction == "LONG" else "🔻"
                    alert_text = (
                        f"{icon} **{name} — ENTRY SIGNAL**\n"
                        f"Direction: {direction} | Confidence: {confidence}\n"
                        f"Level: ${level:,.0f} | Price: ${price:,.0f}\n"
                        f"Stop: ${stop:,.0f}" + (f" | Target: ${target:,.0f}" if target else "") +
                        l0_tag
                    )
                elif "BREAKOUT" in sig_type:
                    alert_text = (
                        f"💥 **{name} — Breakout Detected**\n"
                        f"Resistance broken: ${level:,.0f} | Price: ${price:,.0f}\n"
                        f"Watching for retest entry." +
                        l0_tag
                    )
                else:  # BREAKDOWN_DETECTED
                    alert_text = (
                        f"💥 **{name} — Breakdown Detected**\n"
                        f"Support broken: ${level:,.0f} | Price: ${price:,.0f}\n"
                        f"Watching for retest rejection." +
                        l0_tag
                    )

                alert_signals.append(alert_text)
                # Record this alert — keep recent keys for multi-signal dedup
                recent_keys = last.get("keys", [])
                recent_keys.append(this_key)
                write_json(LAST_ALERT, {"keys": recent_keys[-20:], "timestamp": ts()})

                # Log to signal history
                log_signal(sig)

    # Send all alerts
    if alert_signals:
        combined = "\n\n".join(alert_signals)
        send_telegram_alert(combined)

    print("✅ Signal detection complete")


if __name__ == "__main__":
    main()
