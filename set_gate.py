#!/usr/bin/env python3
"""
CLI tool to set or clear the L-1 Manual Macro Gate.
Human geopolitical/macro events that no automated system can ingest.

Usage:
  python3 set_gate.py PAUSE "G7 Iran MOU contested, Hormuz deadline" --expires "2026-06-19T00:00" --trigger "Hormuz confirmed open + oil < $70"
  python3 set_gate.py ABORT "Exchange hack $500M+" --expires "2026-06-20T12:00"
  python3 set_gate.py CLEAR
  python3 set_gate.py STATUS
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
GATE_FILE = DATA_DIR / "manual_gate.json"

VALID_STATUSES = {"PAUSE", "ABORT", "CLEAR", "STATUS"}


def read_gate():
    """Read current gate state. Returns dict."""
    if not GATE_FILE.exists():
        return {
            "active": False,
            "status": None,
            "reason": "",
            "set_at": None,
            "set_by": "milo",
            "re_evaluate_at": None,
            "re_evaluate_trigger": "",
        }
    with open(GATE_FILE) as f:
        return json.load(f)


def write_gate(data):
    """Write gate state atomically."""
    tmp = GATE_FILE.with_name(f".{GATE_FILE.name}.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        import os
        os.fsync(f.fileno())
    os.replace(tmp, GATE_FILE)


def set_gate(status, reason, expires=None, trigger=None):
    """Activate L-1 gate with given status."""
    if status not in ("PAUSE", "ABORT"):
        print(f"ERROR: status must be PAUSE or ABORT, got '{status}'")
        sys.exit(1)

    now = datetime.now(timezone.utc)
    data = {
        "active": True,
        "status": status,
        "reason": reason,
        "set_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "set_by": "milo",
        "re_evaluate_at": expires,
        "re_evaluate_trigger": trigger or "",
    }

    write_gate(data)
    print(f"✅ L-1 Manual Macro Gate SET: {status}")
    print(f"   Reason: {reason}")
    if expires:
        print(f"   Expires: {expires}")
    if trigger:
        print(f"   Re-evaluate when: {trigger}")


def clear_gate():
    """Deactivate L-1 gate."""
    now = datetime.now(timezone.utc)
    old = read_gate()
    reason = f"[CLEARED at {now.strftime('%Y-%m-%dT%H:%M:%SZ')}] Previously: {old.get('status', '?')} — {old.get('reason', '?')}"

    data = {
        "active": False,
        "status": None,
        "reason": reason,
        "set_at": old.get("set_at"),
        "set_by": "milo",
        "re_evaluate_at": None,
        "re_evaluate_trigger": "",
    }

    write_gate(data)
    print(f"✅ L-1 Manual Macro Gate CLEARED")
    print(f"   Previous: {old.get('status')} — {old.get('reason')}")


def show_status():
    """Display current gate status."""
    gate = read_gate()
    if not gate.get("active"):
        print("L-1 Manual Macro Gate: INACTIVE — no override")
        if gate.get("reason"):
            print(f"  Last state: {gate['reason']}")
    else:
        print(f"L-1 Manual Macro Gate: ACTIVE")
        print(f"  Status:   {gate['status']}")
        print(f"  Reason:   {gate['reason']}")
        print(f"  Set at:   {gate.get('set_at', '?')}")
        if gate.get("re_evaluate_at"):
            print(f"  Expires:  {gate['re_evaluate_at']}")
        if gate.get("re_evaluate_trigger"):
            print(f"  Trigger:  {gate['re_evaluate_trigger']}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  set_gate.py PAUSE <reason> [--expires <ISO>] [--trigger <text>]")
        print("  set_gate.py ABORT <reason> [--expires <ISO>] [--trigger <text>]")
        print("  set_gate.py CLEAR")
        print("  set_gate.py STATUS")
        sys.exit(1)

    action = sys.argv[1].upper()

    if action == "CLEAR":
        clear_gate()
    elif action == "STATUS":
        show_status()
    elif action in ("PAUSE", "ABORT"):
        # Parse remaining args
        args = sys.argv[2:]
        reason_parts = []
        expires = None
        trigger = None
        i = 0
        while i < len(args):
            if args[i] == "--expires" and i + 1 < len(args):
                expires = args[i + 1]
                i += 2
            elif args[i] == "--trigger" and i + 1 < len(args):
                trigger = args[i + 1]
                i += 2
            else:
                reason_parts.append(args[i])
                i += 1

        reason = " ".join(reason_parts)
        if not reason:
            print("ERROR: reason is required for PAUSE/ABORT")
            sys.exit(1)

        set_gate(action, reason, expires, trigger)
    else:
        print(f"ERROR: unknown action '{action}'. Use PAUSE, ABORT, CLEAR, or STATUS.")
        sys.exit(1)
