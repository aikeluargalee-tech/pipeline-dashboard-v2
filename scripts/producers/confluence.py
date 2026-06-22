"""
confluence.py — Confluence scoring + final bias/confidence computation.
"""
from dataclasses import dataclass
from candles import ThreeCandlePattern
from regime import RegimeState


BULLISH_LABELS = {"MOMENTUM", "ENGULF", "ABSORPTION"}
BEARISH_LABELS = {"REVERSAL_RISK", "MOMENTUM", "ENGULF"}  # MOMENTUM/ENGULF direction depends on candle dir


def is_bullish_pattern(p: ThreeCandlePattern) -> bool:
    """Check if pattern leans bullish based on directional consistency."""
    if p.pattern_label in {"POST_EXP_COIL", "COIL", "MIXED"}:
        return False
    return p.dir_score >= 20 and p.c1.direction == "BULL"


def is_bearish_pattern(p: ThreeCandlePattern) -> bool:
    """Check if pattern leans bearish."""
    if p.pattern_label in {"POST_EXP_COIL", "COIL", "MIXED"}:
        return False
    return p.dir_score >= 20 and p.c1.direction == "BEAR"


def is_reversal_risk(p: ThreeCandlePattern) -> bool:
    """Pattern suggests reversal risk: high wick + counter-direction close."""
    return p.wick_score >= 10


def confluence_score(
    pattern_15m: ThreeCandlePattern,
    pattern_4h: ThreeCandlePattern,
    regime: RegimeState,
) -> int:
    """
    Compute confluence score from -100 to +100.
    
    Revised approach (v3 — regime-gated):
    - Directional signals ONLY when regime is BULL or BEAR
    - RANGE regime → neutral (no directional call, only range_signal)
    - 15m pattern is primary, 4H confirms
    """
    p15_dir = 1 if pattern_15m.c1.direction == "BULL" else (-1 if pattern_15m.c1.direction == "BEAR" else 0)
    p4h_dir = 1 if pattern_4h.c1.direction == "BULL" else (-1 if pattern_4h.c1.direction == "BEAR" else 0)
    
    # RANGE regime: neutral, but show pattern strength for range_signal
    if regime.state == "RANGE":
        return 0
    
    # Directional regimes only below
    base = p15_dir * (pattern_15m.confidence - 40)
    
    # 4H confirmation
    if p15_dir != 0 and p4h_dir == p15_dir:
        base += 15
    elif p15_dir != 0 and p4h_dir != 0 and p4h_dir != p15_dir:
        base -= 15
    
    # Regime bias
    if regime.state == "BULL":
        base += 25
    elif regime.state == "BEAR":
        base -= 25
    elif regime.state == "REVERSAL":
        # Amplify counter-direction
        base += 15 if p15_dir == 1 else (-15 if p15_dir == -1 else 0)
    
    # Only return signal if regime and 15m agree on direction
    if (regime.state == "BULL" and p15_dir == -1) or (regime.state == "BEAR" and p15_dir == 1):
        return 0  # Contrarian pattern — neutral
    
    return max(-100, min(100, int(base)))


def final_bias(
    confluence: int,
    pattern_15m_conf: int,
    pattern_4h_conf: int,
    regime_conf: int,
) -> tuple:
    """
    Compute final bias and confidence from confluence score and component confidences.
    Returns (bias: str, confidence: int, range_signal: dict or None)
    """
    # Adjust raw score with component confidence bonuses
    # Higher confidence in components shifts the bias
    raw_score = confluence
    raw_score += (pattern_15m_conf - 50) / 5  # ±10 max from 15m
    raw_score += (pattern_4h_conf - 50) / 5   # ±10 max from 4h
    
    if raw_score > 15:
        bias = "BULLISH"
        confidence = min(100, int(raw_score))
    elif raw_score < -15:
        bias = "BEARISH"
        confidence = min(100, int(abs(raw_score)))
    else:
        bias = "NEUTRAL"
        # Map -30..+30 to confidence 20..80
        confidence = int(50 + raw_score / 2)
        confidence = max(20, min(80, confidence))
    
    return bias, confidence


def compute_range_signal(
    bias: str,
    confidence: int,
    regime_state: str,
    support: float,
    resistance: float,
) -> dict:
    """
    Emit range_signal only when:
    - bias == NEUTRAL
    - confidence > 70
    - regime is explicitly RANGE
    
    Per DeepSeek V4 Pro approval.
    """
    if bias == "NEUTRAL" and confidence > 70 and regime_state == "RANGE":
        return {
            "active": True,
            "strategy": "mean_reversion",
            "buy_near": support,
            "sell_near": resistance,
        }
    return {"active": False}
