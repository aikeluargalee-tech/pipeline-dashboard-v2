"""
card.py — Alert card formatter.

Produces structured alert cards in the format defined by the spec.
FORMING patterns are NOT carded — those go to active_patterns.json only.
Only CONFIRMED and FAILED get alert cards.
"""
from datetime import datetime, timezone, timedelta
from typing import Optional

# MYT = UTC+8
MYT = timezone(timedelta(hours=8))


def _format_price(price: float) -> str:
    """Format price with commas and no decimals for BTC."""
    return f"${price:,.0f}"


def _state_emoji(state: str) -> str:
    if state == "CONFIRMED":
        return "✅"
    elif state == "FAILED":
        return "❌"
    return "🔄"


def _direction_emoji(direction: str) -> str:
    return "📈" if direction == "bullish" else "📉"


def _vol_check(confirmed: bool) -> str:
    return "YES" if confirmed else "NO"


def _counter_direction(direction: str) -> str:
    return "BEARISH" if direction == "bullish" else "BULLISH"


def format_alert_card(detection) -> str:
    """
    Format a PatternDetection into a human-readable alert card.

    Returns the card as a string for delivery to Wilee.
    """
    now = datetime.now(MYT)
    ts = now.strftime("%Y-%m-%d %H:%M")

    # Pattern name prettier
    pretty_name = detection.pattern_name.replace("_", " ").title()

    card = f"""**BTC PATTERN ALERT — {ts} CST**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
**PATTERN:** {pretty_name}
**STATE:** {detection.state} {_state_emoji(detection.state)}
**DIRECTION:** {detection.direction.upper()} {_direction_emoji(detection.direction)}
**TIMEFRAME:** {detection.tf}
**CONFIDENCE:** {detection.confidence}%
**SPAN:** {detection.candles_span} candles

── KEY LEVELS ───────────────────────────────"""

    # Format key levels
    for key, value in detection.key_levels.items():
        label = key.replace("_", " ").title()
        card += f"\n**{label}:** {_format_price(value)}"

    card += f"""

── VOLUME ───────────────────────────────────
**Confirmed:** {_vol_check(detection.volume_confirmed)}

── DESCRIPTION ──────────────────────────────
{detection.description}

**INVALIDATION:** {_format_price(detection.invalidation_price)} — {'pattern invalid if breached' if detection.state == 'CONFIRMED' else 'signal invalid if reversed'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    # FAILED pattern adds counter-signal block
    if detection.state == "FAILED":
        card += f"""

⚠️ **FAILED PATTERN — CONTRARIAN SIGNAL**
Original direction: {detection.direction.upper()}
Counter-signal: {_counter_direction(detection.direction)}
Failed patterns often precede sharp reversals."""

    return card


def format_summary_card(
    total: int,
    confirmed: int,
    failed: int,
    forming: int,
    btc_price: float,
) -> str:
    """Format a scan summary card."""
    now = datetime.now(MYT).strftime("%Y-%m-%d %H:%M CST")
    return (
        f"**PATTERN SCAN — {now}**\n"
        f"BTC: {_format_price(btc_price)}\n"
        f"Detections: {total} | "
        f"✅ {confirmed} confirmed | "
        f"❌ {failed} failed | "
        f"🔄 {forming} forming"
    )


def format_backtest_summary(results: dict) -> str:
    """Format a backtest results summary."""
    lines = [
        "**📊 PATTERN BACKTEST RESULTS**",
        f"Period: {results.get('start_date', '?')} → {results.get('end_date', '?')}",
        f"Total detections: {results.get('total', 0)}",
        f"CONFIRMED: {results.get('confirmed', 0)}",
        f"FAILED: {results.get('failed', 0)}",
        f"FORMING: {results.get('forming', 0)}",
        "",
        "**Per-Pattern Precision:**",
    ]

    for pattern_name, stats in sorted(results.get("patterns", {}).items()):
        pct = stats.get("precision_pct", 0)
        total_p = stats.get("total", 0)
        correct = stats.get("correct", 0)
        symbol = "✅" if pct >= 65 else ("⚠️" if pct >= 50 else "❌")
        lines.append(
            f"  {symbol} **{pattern_name}**: {correct}/{total_p} = {pct:.1f}%"
        )

    return "\n".join(lines)
