"""
state.py — Pattern state machine and detection dataclass.
Three states: FORMING, CONFIRMED, FAILED. Non-negotiable.
"""
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, Optional


class PatternState:
    FORMING = "FORMING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    LATE = "LATE"  # confirmed but breakout stale — log only, no alert


@dataclass
class PatternDetection:
    """Every detection has all fields populated — no optionals in the core fields."""
    pattern_name: str           # e.g. "ASCENDING_TRIANGLE"
    tf: str                     # "4H" or "1D"
    direction: str              # "bullish" or "bearish"
    state: str                  # FORMING / CONFIRMED / FAILED
    confidence: int             # 0-100
    candles_span: int           # number of candles pattern spans
    volume_confirmed: bool      # did volume signature check pass?
    key_levels: Dict[str, float]  # resistance, support, target, stop, etc.
    description: str            # one-line human description
    invalidation_price: float   # price at which pattern is invalidated
    # Auto-populated
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    btc_price: float = 0.0      # current BTC price at detection time
    # Stable pattern identity — used to match FORMING patterns across runs
    pattern_id: str = ""        # deterministic: pattern_tf_firstPivotIdx
    # Outcome tracking (populated later by reconciliation job)
    outcome: Optional[Dict] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        # Drop None outcome from JSONL if not set
        if d.get("outcome") is None:
            del d["outcome"]
        return d

    @property
    def is_actionable(self) -> bool:
        """Only CONFIRMED and FAILED patterns trigger alerts. LATE does not."""
        return self.state in (PatternState.CONFIRMED, PatternState.FAILED)

    @property
    def counter_direction(self) -> str:
        """For FAILED patterns, the counter-signal direction."""
        return "bearish" if self.direction == "bullish" else "bullish"
