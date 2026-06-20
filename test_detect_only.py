#!/usr/bin/env python3
"""
Test suite for detect_only.py — exercises signal detection, outcome tracking,
and alert logic with systematically degraded inputs.

Run: python3 test_detect_only.py
"""

import sys
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))

import detect_only as d

PASS = 0
FAIL = 0
results = []


def run_test(name, fn):
    global PASS, FAIL
    try:
        fn()
        results.append(f"  ✅ {name}")
        PASS += 1
    except AssertionError as e:
        results.append(f"  ❌ {name}: {e}")
        FAIL += 1
    except Exception as e:
        results.append(f"  💥 CRASH: {name} — {type(e).__name__}: {e}")
        FAIL += 1


# ═══════════════════════════════════════════════════════════════
# CATEGORY 1: track_outcomes — crash paths (regression for HIGH #1)
# ═══════════════════════════════════════════════════════════════

print("═══ CATEGORY 1: track_outcomes — crash paths ═══")


def test_track_outcomes_none_price():
    """track_outcomes — btc_price.json has price: null (the HIGH #1 crash bug)."""
    def mock_read(path):
        if "btc_price" in str(path):
            return {"price": None}
        if "signal_history" in str(path):
            return {"signals": [{"timestamp": "2026-06-19 10:00 UTC", "direction": "LONG", "level": 100, "stop_loss": 95, "target": 110, "outcome": None}]}
        return None
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json') as mock_write:
        d.track_outcomes()  # Must not crash
        mock_write.assert_not_called()  # No changes since price is None


run_test("track_outcomes — price: null (HIGH #1 regression)", test_track_outcomes_none_price)


def test_track_outcomes_missing_price_file():
    """track_outcomes — btc_price.json doesn't exist."""
    def mock_read(path):
        if "signal_history" in str(path):
            return {"signals": [{"timestamp": "2026-06-19 10:00 UTC", "direction": "LONG", "level": 100, "stop_loss": 95, "target": 110, "outcome": None}]}
        return None
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json') as mock_write:
        d.track_outcomes()
        mock_write.assert_not_called()


run_test("track_outcomes — btc_price.json missing", test_track_outcomes_missing_price_file)


def test_track_outcomes_missing_history():
    """track_outcomes — signal history file doesn't exist."""
    def mock_read(path):
        if "btc_price" in str(path):
            return {"price": 100000}
        return None
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json') as mock_write:
        d.track_outcomes()
        mock_write.assert_not_called()


run_test("track_outcomes — history file missing", test_track_outcomes_missing_history)


def test_track_outcomes_price_zero():
    """track_outcomes — price is 0 (falsy but not None)."""
    def mock_read(path):
        if "btc_price" in str(path):
            return {"price": 0}
        if "signal_history" in str(path):
            return {"signals": [{"timestamp": "2026-06-19 10:00 UTC", "direction": "LONG", "level": 100, "stop_loss": 95, "target": 110, "outcome": None}]}
        return None
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json') as mock_write:
        d.track_outcomes()  # Must not crash
        mock_write.assert_not_called()


run_test("track_outcomes — price: 0 (falsy guard)", test_track_outcomes_price_zero)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 2: track_outcomes — WIN/LOSS/EXPIRED logic
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 2: track_outcomes — outcome logic ═══")


def make_signal(direction="LONG", level=100, stop=95, target=110, age_hours=1, outcome=None):
    ts = (datetime.now(timezone.utc) - timedelta(hours=age_hours)).strftime("%Y-%m-%d %H:%M UTC")
    return {
        "timestamp": ts,
        "direction": direction,
        "level": level,
        "stop_loss": stop,
        "target": target,
        "outcome": outcome,
    }


def run_track(price, signals):
    def mock_read(path):
        if "btc_price" in str(path):
            return {"price": price}
        if "signal_history" in str(path):
            return {"signals": signals}
        return None
    written = {}
    def mock_write(path, data):
        written["data"] = data
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json', side_effect=mock_write):
        d.track_outcomes()
    return written.get("data")


def test_long_win():
    """LONG signal — price >= target → WIN."""
    sig = make_signal(direction="LONG", target=110)
    result = run_track(115, [sig])
    assert result is not None, "Should have written changes"
    assert result["signals"][0]["outcome"] == "WIN", f"Expected WIN, got {result['signals'][0]['outcome']}"


def test_long_loss():
    """LONG signal — price <= stop → LOSS."""
    sig = make_signal(direction="LONG", stop=95)
    result = run_track(90, [sig])
    assert result is not None
    assert result["signals"][0]["outcome"] == "LOSS", f"Expected LOSS, got {result['signals'][0]['outcome']}"


def test_long_open():
    """LONG signal — price between stop and target → still open."""
    sig = make_signal(direction="LONG", stop=95, target=110)
    result = run_track(100, [sig])
    assert result is None, "Should not write — no outcome change"


def test_short_win():
    """SHORT signal — price <= target → WIN."""
    sig = make_signal(direction="SHORT", level=100, stop=105, target=90)
    result = run_track(85, [sig])
    assert result is not None
    assert result["signals"][0]["outcome"] == "WIN", f"Expected WIN, got {result['signals'][0]['outcome']}"


def test_short_loss():
    """SHORT signal — price >= stop → LOSS."""
    sig = make_signal(direction="SHORT", level=100, stop=105, target=90)
    result = run_track(110, [sig])
    assert result is not None
    assert result["signals"][0]["outcome"] == "LOSS", f"Expected LOSS, got {result['signals'][0]['outcome']}"


def test_short_open():
    """SHORT signal — price between target and stop → still open."""
    sig = make_signal(direction="SHORT", level=100, stop=105, target=90)
    result = run_track(100, [sig])
    assert result is None, "Should not write — no outcome change"


def test_expired():
    """Signal older than 48h → EXPIRED."""
    sig = make_signal(age_hours=49)
    result = run_track(100, [sig])
    assert result is not None
    assert result["signals"][0]["outcome"] == "EXPIRED", f"Expected EXPIRED, got {result['signals'][0]['outcome']}"


def test_not_expired_47h():
    """Signal at 47h → not expired yet."""
    sig = make_signal(age_hours=47, stop=95, target=110)
    result = run_track(100, [sig])
    assert result is None, "Should not expire at 47h"


def test_already_tracked_skipped():
    """Signal with outcome already set → skipped."""
    sig = make_signal(outcome="WIN")
    result = run_track(50, [sig])  # Price would trigger LOSS if re-evaluated
    assert result is None, "Should not re-evaluate already-tracked signal"


def test_missing_level_skipped():
    """Signal with no level → skipped (can't evaluate)."""
    sig = make_signal(level=None, stop=95, target=110)
    result = run_track(115, [sig])
    assert result is None, "Should skip signal without level"


def test_missing_stop_skipped():
    """Signal with no stop → skipped."""
    sig = make_signal(stop=None, target=110)
    result = run_track(115, [sig])
    assert result is None, "Should skip signal without stop"


run_test("LONG — WIN (price >= target)", test_long_win)
run_test("LONG — LOSS (price <= stop)", test_long_loss)
run_test("LONG — open (between stop/target)", test_long_open)
run_test("SHORT — WIN (price <= target)", test_short_win)
run_test("SHORT — LOSS (price >= stop)", test_short_loss)
run_test("SHORT — open (between target/stop)", test_short_open)
run_test("EXPIRED after 48h", test_expired)
run_test("Not expired at 47h", test_not_expired_47h)
run_test("Already-tracked signal skipped", test_already_tracked_skipped)
run_test("Missing level → skipped", test_missing_level_skipped)
run_test("Missing stop → skipped", test_missing_stop_skipped)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 3: log_signal — direction inference (regression for HIGH #2)
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 3: log_signal — direction inference ═══")


def test_log_signal_explicit_direction():
    """log_signal — explicit direction is preserved."""
    captured = {}
    def mock_read(path):
        if "signal_history" in str(path):
            return {"signals": []}
        return None
    def mock_write(path, data):
        captured["data"] = data
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json', side_effect=mock_write):
        d.log_signal({"signal": "ENTRY_SIGNAL", "direction": "LONG", "level": 100, "price": 105, "stop_loss": 95, "target": 110})
    assert captured["data"]["signals"][0]["direction"] == "LONG", "Explicit LONG direction should be preserved"


def test_log_signal_breakout_detected_defaults_long():
    """log_signal — BREAKOUT_DETECTED without direction defaults to LONG."""
    captured = {}
    def mock_read(path):
        if "signal_history" in str(path):
            return {"signals": []}
        return None
    def mock_write(path, data):
        captured["data"] = data
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json', side_effect=mock_write):
        d.log_signal({"signal": "BREAKOUT_DETECTED", "level": 100, "price": 105})
    assert captured["data"]["signals"][0]["direction"] == "LONG", "BREAKOUT_DETECTED should default to LONG"


def test_log_signal_entry_signal_without_direction_defaults_short():
    """log_signal — ENTRY_SIGNAL without direction defaults to SHORT (known fallback).

    This is the fallback in log_signal. The REAL fix is in collect.py which now
    always provides direction='LONG' for breakout ENTRY_SIGNALs. This test documents
    the fallback behavior so we know if it changes.
    """
    captured = {}
    def mock_read(path):
        if "signal_history" in str(path):
            return {"signals": []}
        return None
    def mock_write(path, data):
        captured["data"] = data
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json', side_effect=mock_write):
        d.log_signal({"signal": "ENTRY_SIGNAL", "level": 100, "price": 105})
    assert captured["data"]["signals"][0]["direction"] == "SHORT", "ENTRY_SIGNAL without direction defaults to SHORT (fallback)"


def test_log_signal_history_cap_200():
    """log_signal — history capped at 200 entries."""
    existing = {"signals": [{"timestamp": "2026-06-19 10:00 UTC", "direction": "LONG", "level": 100, "outcome": "WIN"}] * 250}
    captured = {}
    def mock_read(path):
        if "signal_history" in str(path):
            return existing
        return None
    def mock_write(path, data):
        captured["data"] = data
    with patch.object(d, 'read_json', side_effect=mock_read), patch.object(d, 'write_json', side_effect=mock_write):
        d.log_signal({"signal": "ENTRY_SIGNAL", "direction": "LONG", "level": 100, "price": 105})
    assert len(captured["data"]["signals"]) == 200, f"Expected 200 after cap, got {len(captured['data']['signals'])}"


run_test("log_signal — explicit direction preserved", test_log_signal_explicit_direction)
run_test("log_signal — BREAKOUT_DETECTED defaults to LONG", test_log_signal_breakout_detected_defaults_long)
run_test("log_signal — ENTRY_SIGNAL without direction defaults to SHORT (fallback)", test_log_signal_entry_signal_without_direction_defaults_short)
run_test("log_signal — history capped at 200", test_log_signal_history_cap_200)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 4: get_signal_summary
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 4: get_signal_summary ═══")


def test_summary_empty():
    """get_signal_summary — no history file."""
    with patch.object(d, 'read_json', return_value=None):
        result = d.get_signal_summary()
    assert result == {"total": 0, "wins": 0, "losses": 0, "expired": 0, "open": 0}


def test_summary_mixed():
    """get_signal_summary — mixed outcomes."""
    history = {"signals": [
        {"outcome": "WIN"},
        {"outcome": "WIN"},
        {"outcome": "LOSS"},
        {"outcome": "EXPIRED"},
        {"outcome": None},
        {"outcome": None},
    ]}
    with patch.object(d, 'read_json', return_value=history):
        result = d.get_signal_summary()
    assert result["total"] == 6
    assert result["wins"] == 2
    assert result["losses"] == 1
    assert result["expired"] == 1
    assert result["open"] == 2


def test_summary_no_signals_key():
    """get_signal_summary — history exists but no 'signals' key."""
    with patch.object(d, 'read_json', return_value={"foo": "bar"}):
        result = d.get_signal_summary()
    assert result == {"total": 0, "wins": 0, "losses": 0, "expired": 0, "open": 0}


run_test("summary — empty/missing history", test_summary_empty)
run_test("summary — mixed outcomes", test_summary_mixed)
run_test("summary — no signals key", test_summary_no_signals_key)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 5: main() — lock + missing data handling
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 5: main() — lock + missing data ═══")


def test_main_missing_cached_data():
    """main() — all cached data missing → should skip gracefully."""
    with patch.object(d, 'read_json', return_value=None), \
         patch('fcntl.flock'), \
         patch('builtins.open', MagicMock()):
        d.main()  # Must not crash


def test_main_lock_contention():
    """main() — lock held by collect.py → should skip gracefully."""
    with patch('fcntl.flock', side_effect=BlockingIOError("locked")), \
         patch('builtins.open', MagicMock()):
        d.main()  # Must not crash — should print skip message and return


run_test("main() — missing cached data", test_main_missing_cached_data)
run_test("main() — lock contention (collect.py running)", test_main_lock_contention)


# ═══════════════════════════════════════════════════════════════
# RESULTS
# ═══════════════════════════════════════════════════════════════

print(f"\n{'═' * 60}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
for r in results:
    print(r)

if __name__ == '__main__':
    if FAIL > 0:
        print(f"\n🔴 {FAIL} TESTS FAILED — bugs found!")
        sys.exit(1)
    else:
        print(f"\n🟢 ALL {PASS} TESTS PASSED")
        sys.exit(0)
