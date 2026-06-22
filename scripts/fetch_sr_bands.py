#!/usr/bin/env python3
"""Fetch S/R bands for 1H, 4H, 1D from btc_sr_bands.py."""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

OUTPUT = "/tmp/btc_sr_bands.json"
SR_SCRIPT = os.path.join(os.path.dirname(__file__), "producers", "btc_sr_bands.py")

def fetch_tf(tf):
    """Run btc_sr_bands.py for a given timeframe, return parsed JSON."""
    if not os.path.exists(SR_SCRIPT):
        return {"error": f"Script not found: {SR_SCRIPT}"}
    
    try:
        proc = subprocess.run(
            [sys.executable, SR_SCRIPT, "--timeframe", tf, "--json"],
            capture_output=True, text=True, timeout=60
        )
        if proc.returncode != 0:
            return {"error": proc.stderr[:200] if proc.stderr else f"exit code {proc.returncode}"}
        
        if proc.stdout.strip():
            return json.loads(proc.stdout)
        return {"error": "No output produced"}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout (60s)"}
    except json.JSONDecodeError as e:
        return {"error": f"JSON parse error: {e}"}
    except Exception as e:
        return {"error": str(e)[:200]}

def main():
    result = {"timestamp": datetime.now(timezone.utc).isoformat()}
    
    for tf in ["1h", "4h", "1d"]:
        data = fetch_tf(tf)
        result[tf] = data
        if "error" in data:
            print(f"[sr_bands] {tf.upper()}: ERROR — {data['error'][:60]}")
        else:
            sups = len(data.get("supports", []))
            ress = len(data.get("resistances", []))
            print(f"[sr_bands] {tf.upper()}: {sups} supports, {ress} resistances")
    
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
