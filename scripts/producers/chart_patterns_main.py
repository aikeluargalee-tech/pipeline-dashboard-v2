"""
main.py — Pattern recognition engine orchestrator.

Scans 4H and 1D candles for all 17 chart patterns,
logs detections, prints alert cards for CONFIRMED/FAILED.

Usage:
    python3 main.py              # Live scan
    python3 main.py --verbose    # Include FORMING patterns in output
"""
import sys
import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict

# Add project root and scripts dir
_ROOT = Path(__file__).parent.parent
_scripts = Path(__file__).parent
for _d in [_ROOT, _scripts]:
    if str(_d) not in sys.path:
        # sys.path fixed for V2 standalone

from state import PatternState, PatternDetection
from pivots import find_pivots_adaptive
from volume import vol_avg
from fetch import fetch_candles_4h, fetch_candles_1d, get_closing_price
from logger import log_detection, log_alert, write_active_patterns, read_active_patterns
from card import format_alert_card, format_summary_card
from config import SCAN_SKIP, TARGET_CAP, CANDLES_4H_LIMIT


# ── Config determinism guard ──────────────────────────────────
# Crashes immediately if critical config was accidentally changed
# during a patch, preventing silent regression to inflated stats.
def _validate_config():
    assert SCAN_SKIP == 3, f"SCAN_SKIP must be 3, got {SCAN_SKIP}"
    assert TARGET_CAP == 0.65, f"TARGET_CAP must be 0.65, got {TARGET_CAP}"
    assert CANDLES_4H_LIMIT >= 300, f"CANDLES_4H_LIMIT must be >= 300, got {CANDLES_4H_LIMIT}"

_validate_config()
# ──────────────────────────────────────────────────────────────

# Import all 17 detectors
from patterns.triangles import (
    detect_ascending_triangle, detect_descending_triangle,
    detect_symmetrical_triangle,
)
from patterns.reversals import (
    detect_double_top, detect_double_bottom,
    detect_head_and_shoulders, detect_inverse_head_and_shoulders,
)
from patterns.flags import (
    detect_bull_flag, detect_bear_flag,
    detect_bull_pennant, detect_bear_pennant,
)
from patterns.wedges import detect_rising_wedge, detect_falling_wedge
from patterns.channels import detect_channel_up, detect_channel_down
from patterns.complex import detect_cup_and_handle, detect_rounding_bottom


# All detectors in priority order (Tier 1 first)
DETECTORS_4H = [
    # Tier 1
    detect_ascending_triangle,
    detect_descending_triangle,
    detect_double_top,
    detect_double_bottom,
    detect_bull_flag,
    detect_bear_flag,
    # Tier 2
    detect_head_and_shoulders,
    detect_inverse_head_and_shoulders,
    detect_rising_wedge,
    detect_falling_wedge,
    detect_symmetrical_triangle,
    detect_bull_pennant,
    detect_bear_pennant,
    # Tier 3
    detect_channel_up,
    detect_channel_down,
]

DETECTORS_1D = [
    # Tier 3 (1D-only patterns)
    detect_cup_and_handle,
    detect_rounding_bottom,
]


async def scan_timeframe(
    tf: str,
    candles: List[Dict],
    detectors: List,
    verbose: bool = False,
) -> List[PatternDetection]:
    """Run all detectors on one timeframe's candles."""
    btc_price = get_closing_price(candles)

    # Pivot detection
    swing_highs, swing_lows = find_pivots_adaptive(candles)
    avg_volume = vol_avg(candles)

    # Load previous FORMING patterns for state transition tracking
    prev_active = read_active_patterns()
    prev_patterns = {}
    for p in prev_active.get("active", []):
        pid = p.get("pattern_id", "")
        if pid:
            prev_patterns[pid] = p.get("state", "")
    archived = set(prev_active.get("archived", []))

    results = []
    seen_this_run = set()  # dedup within this run

    for detector in detectors:
        try:
            detection = detector(candles, swing_highs, swing_lows, avg_volume)
            if detection is None:
                continue

            # Set current price
            detection.btc_price = btc_price
            detection.tf = tf

            # Dedup: skip if same pattern_id + same state was already logged
            pid = detection.pattern_id
            prev_state = prev_patterns.get(pid)

            # Skip entirely if already archived (resolved in previous run)
            if pid in archived:
                continue

            if prev_state == detection.state and pid in seen_this_run:
                continue  # duplicate within this run
            seen_this_run.add(pid)

            # Skip re-logging if state hasn't changed from previous run
            if prev_state == detection.state:
                continue

            # Log everything
            log_detection(detection)

            # Alert on actionable states
            if detection.is_actionable:
                log_alert(detection)
                card = format_alert_card(detection)
                print(card)
                print()  # blank line between cards

            elif verbose:
                print(f"[FORMING] {detection.pattern_name} on {tf}")

            results.append(detection)

        except Exception as e:
            print(f"[WARN] {detector.__name__} on {tf} failed: {e}", file=sys.stderr)

    return results


def _daily_alert_count() -> int:
    """Count CONFIRMED alerts in last 24 hours."""
    from logger import load_alerts
    alerts = load_alerts()
    cutoff = datetime.now(timezone.utc).isoformat()
    # Simple: count all in the file (alerts.jsonl is per-session)
    # For production, filter by timestamp
    return len(alerts)


async def run(verbose: bool = False):
    """Main scan orchestration."""
    print(f"[SCAN START] {datetime.now(timezone.utc).isoformat()}")
    print(f"[CONFIG OK] SCAN_SKIP={SCAN_SKIP} | TARGET_CAP={TARGET_CAP} | CANDLES_4H={CANDLES_4H_LIMIT}")

    # Fetch both timeframes concurrently
    candles_4h, candles_1d = await asyncio.gather(
        fetch_candles_4h(),
        fetch_candles_1d(),
    )

    all_results = []

    # 4H scan
    results_4h = await scan_timeframe("4H", candles_4h, DETECTORS_4H, verbose)
    all_results.extend(results_4h)

    # 1D scan
    results_1d = await scan_timeframe("1D", candles_1d, DETECTORS_1D, verbose)
    all_results.extend(results_1d)

    # Update active FORMING patterns + archive resolved ones
    active = [d.to_dict() for d in all_results if d.state == PatternState.FORMING]
    archived = [d.pattern_id for d in all_results if d.is_actionable]
    write_active_patterns(active, archived_ids=archived)

    # Summary
    btc_price = get_closing_price(candles_4h)
    confirmed = sum(1 for d in all_results if d.state == PatternState.CONFIRMED)
    failed = sum(1 for d in all_results if d.state == PatternState.FAILED)
    forming = sum(1 for d in all_results if d.state == PatternState.FORMING)

    summary = format_summary_card(len(all_results), confirmed, failed, forming, btc_price)
    print(f"\n{summary}")
    print(f"[SCAN COMPLETE] {len(all_results)} detections | {confirmed} ✅ | {failed} ❌ | {forming} 🔄")

    return all_results


if __name__ == "__main__":
    verbose = "--verbose" in sys.argv
    asyncio.run(run(verbose=verbose))
