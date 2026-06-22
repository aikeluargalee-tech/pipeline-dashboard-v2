#!/usr/bin/env python3
"""Capture V7 Coinglass heatmap images (long + short, 3-day) and copy to assets/."""
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = "/tmp/btc_v7_images.json"
CAPTURE_SCRIPT = os.path.expanduser("~/scripts/capture_coinglass_3day.py")
ASSETS_DIR = os.path.expanduser("~/pipeline-dashboard V2/assets")
PYTHON312 = "/usr/bin/python3.12"

def capture_side(side, output_path):
    """Capture one side (long or short). Returns dict with status."""
    if not os.path.exists(CAPTURE_SCRIPT):
        return {"error": f"Script not found: {CAPTURE_SCRIPT}"}
    if not os.path.exists(PYTHON312):
        return {"error": f"Python 3.12 not found at {PYTHON312}"}
    
    try:
        proc = subprocess.run(
            [PYTHON312, CAPTURE_SCRIPT, "-o", output_path] + (["--short"] if side == "short" else []),
            capture_output=True, text=True, timeout=120
        )
        if proc.returncode != 0:
            return {"error": proc.stderr[:200] if proc.stderr else f"exit {proc.returncode}"}
        
        if os.path.exists(output_path):
            size_kb = round(os.path.getsize(output_path) / 1024, 1)
            return {"file": output_path, "size_kb": size_kb, "timestamp": datetime.now(timezone.utc).isoformat()}
        return {"error": "No output file produced"}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout (120s)"}
    except Exception as e:
        return {"error": str(e)[:200]}

def main():
    os.makedirs(ASSETS_DIR, exist_ok=True)
    result = {"timestamp": datetime.now(timezone.utc).isoformat()}
    
    for side in ["long", "short"]:
        dest = os.path.join(ASSETS_DIR, f"v7_{side}_3day.png")
        s = capture_side(side, dest)
        result[side] = s
        if "error" in s:
            print(f"[v7] {side.upper()}: ERROR — {s['error'][:60]}")
        else:
            print(f"[v7] {side.upper()}: {s['size_kb']}KB → {dest}")
    
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
