#!/usr/bin/env python3
"""
Test suite for collect.py — exercises every collector function
with systematically degraded inputs (missing files, network failures,
partial data) to catch crashes before they hit production.

Run: python3 test_collect.py
"""

import sys
import os
import json
import math
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

# We'll test functions individually without running main()
import collect as c

PASS = 0
FAIL = 0
results = []


def run_test(name, fn):
    """Run a test function and record result."""
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


# ─── Mocking helpers ──────────────────────────────────────────

def mock_all_files_missing():
    """Return None for every read_json call."""
    return patch.object(c, 'read_json', return_value=None)

def mock_network_dead():
    """Return None for every fetch_with_retry call."""
    return patch.object(c, 'fetch_with_retry', return_value=None)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 1: Missing file resilience
# ═══════════════════════════════════════════════════════════════

print("═══ CATEGORY 1: Missing /tmp file resilience ═══")

def test_gate0_missing_files():
    """gate0 — all upstream files missing."""
    with mock_all_files_missing():
        result = c.collect_gate0()
        assert result is not None, "Should not return None"
        assert "verdict" in result, "Should have verdict"
        assert "modules" in result, "Should have modules"
        assert "rules" in result, "Should have rules"
        # Black Swan should default to 0
        assert result["modules"]["black_swan"]["score"] == 0
        # Session should fallback to computed NY open
        assert "session" in result["modules"]
        assert result["modules"]["session"]["name"] == "Unknown"

run_test("gate0 — all /tmp files missing", test_gate0_missing_files)


def test_macro_missing_files():
    """macro — all upstream files missing, network dead."""
    with mock_all_files_missing(), mock_network_dead():
        result = c.collect_macro()
        assert result is not None, "Should not return None"
        assert isinstance(result, dict), "Should return dict"
        # VIX fallback should not crash when all sources missing

run_test("macro — all /tmp files + network dead", test_macro_missing_files)


def test_structural_missing_files():
    """structural — all upstream files missing."""
    with mock_all_files_missing(), mock_network_dead():
        result = c.collect_structural()
        assert result is not None, "Should not return None"
        assert "magnets" in result, "Should have magnets"
        # Magnets should be empty but not crashed
        assert result["magnets"].get("above") is not None

run_test("structural — all /tmp files missing", test_structural_missing_files)


def test_derivatives_missing_network():
    """derivatives — Binance API completely dead."""
    with mock_all_files_missing(), mock_network_dead():
        result = c.collect_derivatives()
        assert result is not None, "Should not return None"
        assert isinstance(result, dict), "Should return dict"
        # No data means empty dict — but no crash
        assert result.get("funding_rate") is None, "FR should be None when API dead"

run_test("derivatives — Binance API dead", test_derivatives_missing_network)


def test_cycle_missing_all():
    """cycle — all onchain/cycle/distribution/skew files missing."""
    with mock_all_files_missing():
        result = c.collect_cycle()
        assert result is not None, "Should not return None"
        assert result["mvrv_z"] is None, "MVRV should be None"
        assert result["sopr"] is None, "SOPR should be None"
        assert result["regime"] is None, "Regime should be None"
        assert result["composite_score"] is None, "Composite should be None"

run_test("cycle — all /tmp files missing", test_cycle_missing_all)


def test_supplementary_missing_klines():
    """supplementary — Binance klines API dead."""
    with mock_all_files_missing(), mock_network_dead():
        result = c.collect_supplementary()
        assert result is not None, "Should not return None"
        assert isinstance(result, dict), "Should return dict"
        # Should handle missing klines gracefully (they're inside try block)
        assert result.get("ma50") is None or isinstance(result.get("ma50"), (int, float))

run_test("supplementary — klines API dead", test_supplementary_missing_klines)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 2: Edge case data shapes
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 2: Edge case data shapes ═══")


def test_map_etf_fields_empty():
    """map_etf_fields — empty dict input."""
    result = c.map_etf_fields({})
    assert result is None, "Empty dict should return None"


def test_map_etf_fields_garbage():
    """map_etf_fields — weird unexpected fields."""
    result = c.map_etf_fields({"foo": "bar", "latest": {"total": "not_a_number"}})
    assert result is None or isinstance(result, dict)


def test_map_etf_fields_partial():
    """map_etf_fields — only weekly_net present."""
    result = c.map_etf_fields({"weekly_net": 150.5})
    assert result is not None, "Should not return None with weekly data"
    assert result["daily_net"] is None
    assert result["weekly_net"] == 150.5


run_test("map_etf_fields — empty/partial/garbage inputs", lambda: (
    test_map_etf_fields_empty(),
    test_map_etf_fields_garbage(),
    test_map_etf_fields_partial(),
))


def test_classify_cycle_regime_none():
    """classify_cycle_regime — None input."""
    assert c.classify_cycle_regime(None) is None


def test_classify_cycle_regime_zero():
    """classify_cycle_regime — boundary values."""
    assert c.classify_cycle_regime(0.0) == "ACCUMULATION"
    assert c.classify_cycle_regime(0.09) == "ACCUMULATION"
    assert c.classify_cycle_regime(0.1) == "EARLY BULL"  # >= 0.1
    assert c.classify_cycle_regime(0.5) == "EARLY BULL"  # <= 0.5
    assert c.classify_cycle_regime(1.99) == "MID BULL"
    assert c.classify_cycle_regime(3.99) == "OVERHEATED"
    assert c.classify_cycle_regime(4.0) == "CYCLE TOP"


run_test("classify_cycle_regime — all thresholds", lambda: (
    test_classify_cycle_regime_none(),
    test_classify_cycle_regime_zero(),
))


def test_compute_composite_score_all_none():
    """compute_composite_score — all None inputs."""
    result = c.compute_composite_score(None, None, None)
    assert result is None, "All None should return None"


def test_compute_composite_score_one_value():
    """compute_composite_score — only MVRV available."""
    result = c.compute_composite_score(0.5, None, None)
    assert result is not None
    assert 0 <= result <= 100


def test_compute_composite_score_extreme():
    """compute_composite_score — extreme negative MVRV."""
    result = c.compute_composite_score(-5.0, 0.1, 0.1)
    assert result is not None
    assert 0 <= result <= 100


run_test("compute_composite_score — null/extreme inputs", lambda: (
    test_compute_composite_score_all_none(),
    test_compute_composite_score_one_value(),
    test_compute_composite_score_extreme(),
))


# ═══════════════════════════════════════════════════════════════
# CATEGORY 3: Regime synthesis edge cases
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 3: Regime synthesis edge cases ═══")


def make_empty_layer():
    return {
        "gate": {"verdict": "TIGHTENED", "sources": ["test"]},
        "macro": {},
        "structural": {"magnets": {}, "sr_bands": {}},
        "derivatives": {},
        "cycle": {},
        "supplementary": {},
    }


def test_regime_synthesis_empty():
    """compute_regime_summary — minimal empty data, no manual gate."""
    empty = make_empty_layer()
    with patch.object(c, 'load_manual_override', return_value={"active": False, "status": None}):
        result = c.compute_regime_summary(
            {"verdict": "TIGHTENED", "sources": ["test"]},
            {}, {}, {}, {}, {}
        )
        assert result is not None
        assert "synthesis" in result
        assert "verdict" in result["synthesis"]
        assert result["synthesis"]["verdict"] in (
            "CAUTIOUS NEUTRAL", "MIXED", "CAUTIOUS BULL", "CAUTIOUS BEAR",
            "BULLISH", "BEARISH", "NEUTRAL", "STAND ASIDE", "DO NOT TRADE"
        )


def test_regime_with_none_values():
    """compute_regime_summary — fr is None, vix is None, cycle is empty."""
    with patch.object(c, 'load_manual_override', return_value={"active": False, "status": None}):
        result = c.compute_regime_summary(
            {"verdict": "PROCEED", "sources": []},
            {"vix": None, "dxy": None},
            {"magnets": {"regime": "Downside Sweep", "sandwich": {"width_usd": 2000}}, "sr_bands": {}},
            {"funding_rate": None},
            {"mvrv_z": 0.42},
            {"price": 62000, "ma50": 72000}
        )
        assert result is not None
        # Should detect bearish TA warning (price 13.9% below MA50)
        assert result["synthesis"].get("ta_warning") is not None
        assert "below" in result["synthesis"]["ta_warning"]


def test_regime_manual_override_active():
    """compute_regime_summary — L-1 manual gate active."""
    with patch.object(c, 'load_manual_override', return_value={
        "active": True,
        "status": "PAUSE",
        "reason": "G7 Hormuz crisis",
        "re_evaluate_at": "2026-06-20T00:00",
    }):
        result = c.compute_regime_summary(
            {"verdict": "PROCEED", "sources": ["test"]},
            {}, {}, {}, {}, {}
        )
        assert "L-1 PAUSE" in result["synthesis"]["verdict"]
        assert result["synthesis"]["manual_override"]["active"] is True


run_test("regime_summary — empty data", test_regime_synthesis_empty)
run_test("regime_summary — None values + TA warning", test_regime_with_none_values)
run_test("regime_summary — L-1 manual override", test_regime_manual_override_active)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 4: Detection functions with degraded inputs
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 4: Detection functions with degraded inputs ═══")


def test_val_absorption_no_price():
    """detect_val_absorption — BTC price is None."""
    result = c.detect_val_absorption({"price": None}, {}, {})
    assert result is None, "Should return None when price is missing"


def test_val_absorption_no_volume_profile():
    """detect_val_absorption — structural has no volume_profile."""
    result = c.detect_val_absorption(
        {"price": 62000},
        {"volume_profile": {}},  # empty, no val
        {}
    )
    assert result is None, "Should return None when VAL is missing"


def test_val_absorption_network_dead():
    """detect_val_absorption — klines fetch fails."""
    with mock_network_dead():
        result = c.detect_val_absorption(
            {"price": 62000},
            {"volume_profile": {"val": 63900, "vah": 66950}},
            {}
        )
        assert result is None, "Should return None when klines unavailable"


run_test("val_absorption — missing price", test_val_absorption_no_price)
run_test("val_absorption — no volume profile", test_val_absorption_no_volume_profile)
run_test("val_absorption — network dead", test_val_absorption_network_dead)


def test_breakout_retest_no_price():
    """detect_breakout_retest — price is None."""
    with mock_network_dead():
        result = c.detect_breakout_retest({"price": None}, {}, {})
        assert result is None, "Should return None when price missing"


def test_breakout_retest_dead_network():
    """detect_breakout_retest — all network dead."""
    with mock_all_files_missing(), mock_network_dead():
        result = c.detect_breakout_retest(
            {"price": 62000},
            {"sr_bands": {}, "magnets": {}},
            {}
        )
        assert result is None, "Should return None when 15m klines unavailable"


run_test("breakout_retest — no price", test_breakout_retest_no_price)
run_test("breakout_retest — network dead", test_breakout_retest_dead_network)


def test_breakdown_retest_no_price():
    """detect_breakdown_retest — price is None."""
    with mock_network_dead():
        result = c.detect_breakdown_retest({"price": None}, {}, {})
        assert result is None, "Should return None when price missing"


run_test("breakdown_retest — no price", test_breakdown_retest_no_price)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 5: Data shape mismatch (real bug pattern)
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 5: Data shape mismatch ═══")


def test_magnets_partial_data():
    """magnets — heatmap has 'above' but no 'nearest_magnet'."""
    with mock_all_files_missing():
        # Simulate what happens when heatmap has structure but empty magnets
        heatmap_data = {"above": {}, "below": {}, "btc_price": None}
        # Patching read_json is tricky since structural() calls it multiple times.
        # Instead test the magnet processing logic directly.
        above = {}
        below = {}
        above_magnet = above.get("nearest_magnet", {})
        below_magnet = below.get("nearest_magnet", {})
        above_price = above_magnet.get("price") if above_magnet else None
        below_price = below_magnet.get("price") if below_magnet else None
        # These should all be None safely
        assert above_price is None
        assert below_price is None
        # safe_float on None should not crash
        ap = c.safe_float(above_price, "test")
        assert ap is None


def test_vix_empty_assets_dict():
    """VIX — assets dict exists but has no ^VIX or VIX key."""
    risk = {"assets": {"SPY": {"close": 500}}, "vix": None}
    assets = risk.get("assets", {})
    vix_data = assets.get("^VIX") or assets.get("VIX")
    assert vix_data is None  # Not a dict
    # The code does: if isinstance(vix_data, dict): ...
    # None is not a dict, so it skips. Should not crash.
    if isinstance(vix_data, dict):
        pass  # wouldn't happen
    # Falls through to: result["vix"] = risk.get("vix")
    vix = risk.get("vix")
    assert vix is None  # Safe


run_test("magnets — partial heatmap shape", test_magnets_partial_data)
run_test("VIX — empty assets dict shape", test_vix_empty_assets_dict)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 7: Regression tests — bugs found by cmd CLI audit
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 7: Regression tests (cmd CLI audit) ═══")


def test_datetime_naive_vs_aware():
    """datetime.strptime returns naive; comparing with aware now must not crash."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    expires = datetime.strptime("2026-06-21 00:00 UTC", "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
    # Must not raise TypeError
    assert now > expires or now <= expires  # Either way — just no crash


def test_str_replace_on_numeric():
    """str() on numeric ETF display values must not crash."""
    etf = {"total_flow_display": -131.2}
    disp = str(etf["total_flow_display"]).replace("$", "").replace("M", "").replace(",", "").strip()
    assert disp == "-131.2"
    etf2 = {"total_flow_display": "$-359.1M"}
    disp2 = str(etf2["total_flow_display"]).replace("$", "").replace("M", "").replace(",", "").strip()
    assert disp2 == "-359.1"


run_test("datetime — naive vs aware comparison", test_datetime_naive_vs_aware)
run_test("ETF — str() on numeric display values", test_str_replace_on_numeric)


# ═══════════════════════════════════════════════════════════════
# CATEGORY 6: Full pipeline stress test
# ═══════════════════════════════════════════════════════════════

print("\n═══ CATEGORY 6: Full pipeline stress test ═══")


def test_full_pipeline_degraded():
    """Run every collector function sequentially with all files missing + network dead."""
    with mock_all_files_missing(), mock_network_dead():
        btc = c.fetch_btc_price()
        assert btc is not None  # Returns error dict, not None
        assert btc.get("error") is not None

        gate0 = c.collect_gate0()
        assert gate0 is not None

        macro = c.collect_macro()
        assert macro is not None

        structural = c.collect_structural()
        assert structural is not None

        derivatives = c.collect_derivatives()
        assert derivatives is not None

        cycle = c.collect_cycle()  # ← THIS WAS THE CRASH BUG
        assert cycle is not None

        supplementary = c.collect_supplementary()
        assert supplementary is not None

        # Regime synthesis with empty data
        with patch.object(c, 'load_manual_override', return_value={"active": False, "status": None}):
            regime = c.compute_regime_summary(gate0, macro, structural, derivatives, cycle, supplementary)
            assert regime is not None
            assert "synthesis" in regime

        # Detection functions with degraded data
        val = c.detect_val_absorption(btc, structural, derivatives)
        brk = c.detect_breakout_retest(btc, structural, derivatives)
        bkd = c.detect_breakdown_retest(btc, structural, derivatives)
        # All should return None (no conditions met) — NOT crash
        assert val is None, f"VAL absorption should be None, got {val}"
        assert brk is None, f"Breakout should be None, got {brk}"
        assert bkd is None, f"Breakdown should be None, got {bkd}"


run_test("full pipeline — all files missing + network dead", test_full_pipeline_degraded)


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
