#!/usr/bin/env python3
"""
Synthesis Engine — combines Gate 0, S/R bands, market state, cycle, risk, and onchain
into a single directional bias verdict for the B22 card.

Output: /tmp/btc_synthesis.json
Format: {bias, confidence, regime, key_factors, action, timestamp}
"""
import json
import os
import sys
from datetime import datetime, timezone

OUTPUT = "/tmp/btc_synthesis.json"

# Data sources
SOURCES = {
    "gate0": "/tmp/btc_gate0.json",
    "sr_bands": "/tmp/btc_sr_bands.json",
    "market": "/tmp/btc_market_state.json",
    "cycle": "/tmp/btc_cycle_state.json",
    "risk": "/tmp/btc_risk_state.json",
    "onchain": "/tmp/btc_onchain_state.json",
}


def load_json(path):
    """Load a JSON file, return None on failure."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def score_gate0(data):
    """Gate 0: threat level. Higher level = more dangerous."""
    if not data:
        return 0, "Gate 0: No data"
    level = data.get("level", 0)
    if level >= 3:
        return -3, "Gate 0: HARD ABORT — pipeline halted"
    elif level == 2:
        return -2, "Gate 0: PAUSE — review required"
    elif level == 1:
        return 0, "Gate 0: All clear (Level 1)"
    return 0, "Gate 0: Nominal"


def score_market(data):
    """Market state: MA regime, funding, taker ratio, OI."""
    if not data or data.get("error"):
        return 0, "Market: No data"

    signals = []
    score = 0

    # MA regime
    ma_regime = data.get("ma_regime", "neutral")
    if ma_regime == "bullish":
        score += 1
        signals.append("MA bullish (above 50/200)")
    elif ma_regime == "bearish":
        score -= 1
        signals.append("MA bearish (below 50/200)")
    else:
        signals.append("MA neutral")

    # Funding rate
    funding = data.get("funding_rate", 0)
    if funding > 0.01:
        score -= 0.5  # Overleveraged longs = bearish contrarian
        signals.append(f"funding high ({funding:.4f})")
    elif funding < -0.01:
        score += 0.5  # Shorts paying = bullish contrarian
        signals.append(f"funding negative ({funding:.4f})")
    else:
        signals.append(f"funding neutral ({funding:.4f})")

    # Taker buy ratio
    taker = data.get("taker_buy_ratio", 0.5)
    taker_label = data.get("taker_label", "")
    if taker > 0.55 or "aggressive_buy" in taker_label:
        score += 1
        signals.append(f"taker buy dominant ({taker:.3f})")
    elif taker < 0.45 or "aggressive_sell" in taker_label:
        score -= 1
        signals.append(f"taker sell dominant ({taker:.3f})")

    # OI delta
    oi_delta = data.get("oi_delta_pct", 0)
    if oi_delta > 5:
        score += 0.5  # Rising OI with price = conviction
        signals.append(f"OI rising +{oi_delta:.1f}%")
    elif oi_delta < -5:
        score -= 0.5
        signals.append(f"OI falling {oi_delta:.1f}%")

    label = "; ".join(signals)
    return score, f"Market: {label}"


def score_sr_bands(data):
    """S/R bands: where is price relative to support/resistance?"""
    if not data:
        return 0, "S/R: No data"

    # Use 1h timeframe if available
    tf = data.get("1h", data.get("4h", {}))
    if not tf:
        return 0, "S/R: No timeframe data"

    price = tf.get("current_price", 0)
    resistances = tf.get("resistances", [])
    supports = tf.get("supports", [])

    if not resistances and not supports:
        return 0, "S/R: No levels detected"

    # Find nearest R and S
    nearest_r = None
    nearest_s = None
    for r in resistances:
        if r.get("status") == "ACTIVE":
            if nearest_r is None or r.get("center", 999999) < nearest_r.get("center", 999999):
                nearest_r = r
    for s in supports:
        if s.get("status") == "ACTIVE":
            if nearest_s is None or s.get("center", 0) > nearest_s.get("center", 0):
                nearest_s = s

    score = 0
    parts = []

    if nearest_r and price > 0:
        r_dist = (nearest_r["center"] - price) / price * 100
        if r_dist < 1.0:
            score -= 1  # Very close to resistance = bearish pressure
            parts.append(f"near R ${nearest_r['center']:,.0f} ({r_dist:.1f}%)")
        elif r_dist < 3.0:
            parts.append(f"R ahead ${nearest_r['center']:,.0f} ({r_dist:.1f}%)")
        else:
            parts.append(f"R distant ${nearest_r['center']:,.0f}")

    if nearest_s and price > 0:
        s_dist = (price - nearest_s["center"]) / price * 100
        if s_dist < 1.0:
            score -= 0.5  # Very close to support = could break
            parts.append(f"near S ${nearest_s['center']:,.0f} ({s_dist:.1f}%)")
        elif s_dist < 3.0:
            score += 0.5  # Comfortable above support
            parts.append(f"S below ${nearest_s['center']:,.0f} ({s_dist:.1f}%)")
        else:
            score += 0.5
            parts.append(f"S far ${nearest_s['center']:,.0f}")

    return score, f"S/R: {'; '.join(parts) if parts else 'no active levels'}"


def score_cycle(data):
    """Cycle indicators: composite score."""
    if not data:
        return 0, "Cycle: No data"

    composite = data.get("composite", 50)
    cycle_class = data.get("composite_class", "unknown")

    if composite < 20:
        return 1, f"Cycle: Deeply undervalued ({composite})"
    elif composite < 40:
        return 0.5, f"Cycle: Low/accumulation zone ({composite})"
    elif composite < 60:
        return 0, f"Cycle: Medium ({composite})"
    elif composite < 80:
        return -0.5, f"Cycle: Elevated/caution ({composite})"
    else:
        return -1, f"Cycle: Overheated/distribution ({composite})"


def score_risk(data):
    """Risk assets: VIX, equity correlation."""
    if not data:
        return 0, "Risk: No data"

    regime = data.get("risk_regime", "neutral")
    vix = data.get("vix", 20)

    score = 0
    parts = []

    if regime == "risk_on":
        score += 1
        parts.append("risk-on regime")
    elif regime == "risk_off":
        score -= 1
        parts.append("risk-off regime")
    else:
        parts.append("neutral regime")

    if vix > 30:
        score -= 1
        parts.append(f"VIX elevated ({vix})")
    elif vix < 15:
        score += 0.5
        parts.append(f"VIX low ({vix})")
    else:
        parts.append(f"VIX normal ({vix})")

    return score, f"Risk: {'; '.join(parts)}"


def score_onchain(data):
    """Onchain: MVRV, netflow, regime."""
    if not data:
        return 0, "Onchain: No data"

    score = 0
    parts = []

    regime = data.get("onchain_regime", "")
    if regime == "accumulation":
        score += 1
        parts.append("accumulation phase")
    elif regime == "distribution":
        score -= 1
        parts.append("distribution phase")
    elif regime:
        parts.append(regime)

    # Netflow
    netflow = data.get("exchange_netflow_7d_btc")
    if netflow is not None:
        if netflow < -2000:
            score += 0.5
            parts.append(f"7d netflow {netflow:+,.0f} BTC (outflow)")
        elif netflow > 2000:
            score -= 0.5
            parts.append(f"7d netflow {netflow:+,.0f} BTC (inflow)")

    # MVRV
    mvrv = data.get("mvrv")
    if mvrv is not None:
        if mvrv < 1.0:
            score += 0.5
            parts.append(f"MVRV {mvrv:.2f} (undervalued)")
        elif mvrv > 3.5:
            score -= 0.5
            parts.append(f"MVRV {mvrv:.2f} (overheated)")
        else:
            parts.append(f"MVRV {mvrv:.2f}")

    return score, f"Onchain: {'; '.join(parts) if parts else 'no signals'}"


def determine_action(total_score, confidence_pct, gate0_level, bias):
    """Determine recommended action based on synthesis."""
    if gate0_level >= 3:
        return "STAND DOWN — Gate 0 Hard Abort active. No new positions."
    if gate0_level >= 2:
        return "CAUTION — Gate 2 review required. Reduce size or wait."
    if confidence_pct >= 65:
        if bias == "BULL":
            return "Look for LONG entries at support. Full size per plan."
        elif bias == "BEAR":
            return "Look for SHORT entries at resistance. Full size per plan."
    if confidence_pct >= 40:
        if bias == "BULL":
            return "Lean long — enter at support with tight stops. Reduced size."
        elif bias == "BEAR":
            return "Lean short — enter at resistance with tight stops. Reduced size."
    if bias != "NEUTRAL":
        return f"Bias is {bias} but conviction is low. Wait for more alignment before acting."
    return "NEUTRAL — conflicting signals. Wait for alignment or stay flat."


def determine_regime(market_data, sr_data):
    """Determine market regime label."""
    if not market_data:
        return "unknown"

    atr_label = market_data.get("atr_label", "moderate")
    bbw_label = market_data.get("bbw_label", "normal")

    if bbw_label == "tight" or atr_label == "low":
        return "Range-bound / Consolidating"
    elif market_data.get("ma_regime") == "bullish" and market_data.get("oi_delta_pct", 0) > 2:
        return "Trending Up (conviction building)"
    elif market_data.get("ma_regime") == "bearish" and market_data.get("oi_delta_pct", 0) > 2:
        return "Trending Down (conviction building)"
    elif market_data.get("ma_regime") == "bullish":
        return "Bullish structure, moderate conviction"
    elif market_data.get("ma_regime") == "bearish":
        return "Bearish structure, moderate conviction"
    return "Neutral / Transitional"


def main():
    # Load all data sources
    data = {}
    for key, path in SOURCES.items():
        data[key] = load_json(path)

    # Score each dimension
    scores = []
    factors = []

    gate0_score, gate0_text = score_gate0(data["gate0"])
    scores.append(gate0_score)
    factors.append({"label": "Gate 0", "value": gate0_text})

    market_score, market_text = score_market(data["market"])
    scores.append(market_score)
    factors.append({"label": "Market Structure", "value": market_text})

    sr_score, sr_text = score_sr_bands(data["sr_bands"])
    scores.append(sr_score)
    factors.append({"label": "S/R Positioning", "value": sr_text})

    cycle_score, cycle_text = score_cycle(data["cycle"])
    scores.append(cycle_score)
    factors.append({"label": "Cycle Position", "value": cycle_text})

    risk_score, risk_text = score_risk(data["risk"])
    scores.append(risk_score)
    factors.append({"label": "Risk Environment", "value": risk_text})

    onchain_score, onchain_text = score_onchain(data["onchain"])
    scores.append(onchain_score)
    factors.append({"label": "Onchain", "value": onchain_text})

    # Calculate total
    total_score = sum(scores)
    max_possible = len(scores) * 3  # Rough max magnitude

    # Determine bias
    if total_score > 1.5:
        bias = "BULL"
    elif total_score < -1.5:
        bias = "BEAR"
    else:
        bias = "NEUTRAL"

    # Confidence: how many factors agree with the majority direction
    if total_score == 0:
        confidence_pct = 20
    else:
        direction = 1 if total_score > 0 else -1
        agreeing = sum(1 for s in scores if (s * direction) > 0)
        confidence_pct = int((agreeing / len(scores)) * 100)
        # Weight by magnitude too
        magnitude = min(abs(total_score) / max_possible * 100, 100)
        confidence_pct = int((confidence_pct * 0.6 + magnitude * 0.4))
        confidence_pct = max(10, min(95, confidence_pct))

    # Gate 0 level for action determination
    gate0_level = 0
    if data["gate0"]:
        gate0_level = data["gate0"].get("level", 0)

    regime = determine_regime(data["market"], data["sr_bands"])
    action = determine_action(total_score, confidence_pct, gate0_level, bias)

    # Build output
    result = {
        "bias": bias,
        "confidence": confidence_pct,
        "regime": regime,
        "key_factors": factors,
        "action": action,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "score_raw": round(total_score, 2),
        "sources_loaded": sum(1 for v in data.values() if v is not None),
        "sources_total": len(SOURCES),
    }

    # Write output
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)

    print(f"[synthesis] Bias: {bias} | Confidence: {confidence_pct}% | Regime: {regime}")
    print(f"[synthesis] Score: {total_score:.1f} | Sources: {result['sources_loaded']}/{result['sources_total']}")
    print(f"[synthesis] Action: {action}")
    print(f"[synthesis] Written to {OUTPUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
