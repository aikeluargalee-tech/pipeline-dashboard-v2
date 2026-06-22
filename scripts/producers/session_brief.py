#!/usr/bin/env python3
"""
Trading Session Killzones — DST-aware session brief for Kuching, Malaysia (UTC+8).
Auto-detects Winter/Summer mode based on US DST rules.
Generates daily session brief with Trap Zone, Golden Window, and risk checks.
"""

from datetime import datetime, timezone, timedelta
import json

# Kuching timezone (UTC+8, no DST)
MYT = timezone(timedelta(hours=8))

# US DST rules: 2nd Sunday March → 1st Sunday November
def is_us_dst(dt=None):
    """Return True if US is in Daylight Saving Time (Summer mode)."""
    if dt is None:
        dt = datetime.now(timezone.utc)
    year = dt.year
    month = dt.month
    day = dt.day

    # Find 2nd Sunday of March
    mar1 = datetime(year, 3, 1, tzinfo=timezone.utc)
    mar1_wd = mar1.weekday()  # 0=Mon, 6=Sun
    days_to_sun = (6 - mar1_wd) % 7
    second_sun_mar = 1 + days_to_sun + 7  # 8–14
    dst_start = datetime(year, 3, second_sun_mar, 7, tzinfo=timezone.utc)

    # Find 1st Sunday of November
    nov1 = datetime(year, 11, 1, tzinfo=timezone.utc)
    nov1_wd = nov1.weekday()
    days_to_sun = (6 - nov1_wd) % 7
    first_sun_nov = 1 + days_to_sun  # 1–7
    dst_end = datetime(year, 11, first_sun_nov, 6, tzinfo=timezone.utc)

    return dst_start <= dt < dst_end


def get_session_brief():
    """Generate the daily session brief for Kuching, Malaysia."""
    now_utc = datetime.now(timezone.utc)
    now_myt = now_utc.astimezone(MYT)
    dst = is_us_dst(now_utc)
    mode = "SUMMER (Daylight Savings)" if dst else "WINTER (Standard Time)"

    # NY Open in MYT
    if dst:
        ny_open = "9:30 PM"
        trap_start = "7:30 PM"
        trap_end = "9:30 PM"
        golden_start = "9:30 PM"
        golden_end = "1:00 AM"
        data_drop = "8:30 PM"
        close_time = "4:00 AM"
    else:
        ny_open = "10:30 PM"
        trap_start = "8:30 PM"
        trap_end = "10:30 PM"
        golden_start = "10:30 PM"
        golden_end = "2:00 AM"
        data_drop = "9:30 PM"
        close_time = "5:00 AM"

    # Session windows (fixed in MYT, no DST shift for these — they're local)
    sessions = {
        "ASIA": {
            "time": "07:00 – 14:59",
            "behavior": "Range building, liquidity accumulation, lower follow-through. Skeptical of early breaks.",
            "trade": "DO NOT TRADE — death by a thousand cuts",
        },
        "LONDON": {
            "time": "15:00 – 20:59",
            "behavior": "Stop-runs, fake breaks, Judas Swing. Raids of Asia highs/lows.",
            "trade": "OBSERVE ONLY — look for sweep of Asia range, wait for close-based acceptance",
        },
        "NEW YORK": {
            "time": "21:00 – 02:59",
            "behavior": "Expansion/resolution, higher follow-through. True trend established.",
            "trade": "EXECUTION WINDOW — if structure + gates permit",
        },
    }

    # Determine current session
    hour = now_myt.hour
    minute = now_myt.minute
    current_time_decimal = hour + minute / 60

    if 7 <= current_time_decimal < 15:
        current_session = "ASIA"
    elif 15 <= current_time_decimal < 21:
        current_session = "LONDON"
    elif current_time_decimal >= 21 or current_time_decimal < 3:
        current_session = "NEW YORK"
    else:
        current_session = "DEAD ZONE (3:00–7:00 AM)"

    # Risk check — weekends and major events
    weekday = now_myt.weekday()  # 0=Mon, 6=Sun
    is_weekend = weekday >= 5
    warnings = []

    if is_weekend:
        warnings.append("⚠️ WEEKEND — markets thin, no institutional flow. Skip.")

    # Check if within trap zone
    trap_start_h = int(trap_start.split(":")[0])
    trap_start_m = int(trap_start.split(":")[1].split()[0])
    trap_start_pm = "PM" in trap_start
    trap_start_dec = trap_start_h + trap_start_m / 60
    if trap_start_pm and trap_start_h != 12:
        trap_start_dec += 12
    elif not trap_start_pm and trap_start_h == 12:
        trap_start_dec = 0

    ny_open_h = int(ny_open.split(":")[0])
    ny_open_m = int(ny_open.split(":")[1].split()[0])
    ny_open_pm = "PM" in ny_open
    ny_open_dec = ny_open_h + ny_open_m / 60
    if ny_open_pm and ny_open_h != 12:
        ny_open_dec += 12
    elif not ny_open_pm and ny_open_h == 12:
        ny_open_dec = 0

    in_trap_zone = trap_start_dec <= current_time_decimal < ny_open_dec
    in_golden = ny_open_dec <= current_time_decimal < (ny_open_dec + 3)

    if in_trap_zone:
        warnings.append("🛑 TRAP ZONE ACTIVE — Do Not Execute. Watch for liquidity sweeps.")

    output = {
        "timestamp": now_utc.isoformat(),
        "location": "Kuching, Malaysia (MYT / UTC+8)",
        "local_time": now_myt.strftime("%H:%M"),
        "local_date": now_myt.strftime("%Y-%m-%d"),
        "weekday": now_myt.strftime("%A"),
        "mode": mode,
        "ny_open_myt": ny_open,
        "trap_zone": f"{trap_start} – {trap_end}",
        "golden_window": f"{golden_start} – {golden_end}",
        "data_drop": data_drop,
        "close_time": close_time,
        "current_session": current_session,
        "in_trap_zone": in_trap_zone,
        "in_golden_window": in_golden,
        "warnings": warnings if warnings else ["✅ Standard Operations — no risk flags"],
        "sessions": sessions,
        "killzone_note": (
            "London Open: 3:00–6:00 PM MYT — expect Judas Swing (fake move). "
            "NY Open: " + ny_open + " MYT — true trend begins. "
            "Trap Zone: 2 hours before NY Open — DO NOT EXECUTE. "
            "Golden Window: 3 hours after NY Open — high probability."
        ),
    }

    return output


def main():
    brief = get_session_brief()
    print(json.dumps(brief, indent=2))

    # Human-readable summary
    print("\n" + "=" * 50)
    print("TITAN 26 — DAILY SESSION BRIEF")
    print("=" * 50)
    print(f"📍 {brief['location']}")
    print(f"📅 {brief['local_date']} ({brief['weekday']}) — {brief['local_time']}")
    print(f"🌓 {brief['mode']}")
    print()
    print(f"🛑 TRAP ZONE:    {brief['trap_zone']} — DO NOT TRADE")
    print(f"🔔 DATA DROP:    {brief['data_drop']} — stand down, spreads widen")
    print(f"🚀 NY OPEN:      {brief['ny_open_myt']} — execution window begins")
    print(f"⭐ GOLDEN WINDOW: {brief['golden_window']} — high probability")
    print(f"💤 CLOSE:        {brief['close_time']} — liquidity dries up")
    print()
    print(f"📍 CURRENT: {brief['current_session']} session")
    if brief["in_trap_zone"]:
        print("   ⚠️  YOU ARE IN THE TRAP ZONE")
    elif brief["in_golden_window"]:
        print("   ✅ YOU ARE IN THE GOLDEN WINDOW")
    print()
    for w in brief["warnings"]:
        print(w)

    # Save state
    with open("/tmp/btc_session_state.json", "w") as f:
        json.dump(brief, f, indent=2)


if __name__ == "__main__":
    main()
