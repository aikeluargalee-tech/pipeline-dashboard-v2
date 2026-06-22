#!/usr/bin/env python3
"""Fetch Gate 0 threat monitoring data from trading-workflow."""
import json
import os
import sys
import time
from datetime import datetime, timezone

OUTPUT = "/tmp/btc_gate0.json"

def main():
    # Import trading-workflow modules
    tw_path = os.path.expanduser("~/trading-workflow")
    if tw_path not in sys.path:
        sys.path.insert(0, tw_path)
    
    try:
        from gate0.gate0_orchestrator import run_all
    except ImportError as e:
        result = {"error": f"Cannot import run_all from gate0_orchestrator: {e}", "timestamp": datetime.now(timezone.utc).isoformat()}
        with open(OUTPUT, "w") as f:
            json.dump(result, f, indent=2)
        print(f"[gate0] Import failed: {e}")
        return 1
    
    start = time.time()
    result = run_all()
    elapsed = round(time.time() - start, 1)
    
    result["elapsed_seconds"] = elapsed
    result["timestamp"] = datetime.now(timezone.utc).isoformat()
    
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    
    level = result.get("level", "?")
    modules = len(result.get("triggers", []))
    print(f"[gate0] Level {level}, {modules} modules, {elapsed}s")
    return 0

if __name__ == "__main__":
    sys.exit(main())
