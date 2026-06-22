"""
config.py — Central configuration for btc-chart-patterns.
All thresholds, paths, and constants live here. Nothing hardcoded in detectors.
"""
from pathlib import Path

# --- Paths ---
ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
SCRIPTS_DIR = ROOT / "scripts"
PATTERNS_DIR = SCRIPTS_DIR / "patterns"

# --- Data Sources ---
EXCHANGE = "bitget"
SYMBOL = "BTC/USDT:USDT"
TF_4H = "4H"
TF_1D = "1d"
CANDLES_4H_LIMIT = 750
CANDLES_1D_LIMIT = 200

# --- Pivot Detection ---
PIVOT_WINDOWS = [5, 7, 10]          # adaptive multi-window
PIVOT_MIN_AGREEMENT = 2             # must be confirmed by >= this many windows
MIN_PIVOT_SEPARATION = 5            # candles between pivots

# --- Pattern Global Constraints ---
MIN_PATTERN_CANDLES = 10            # minimum pattern span
MAX_PATTERN_CANDLES = 200           # maximum lookback
MIN_PATTERN_AMPLITUDE = 0.03        # pattern range >= 3% of price

# --- Volume ---
VOL_LOOKBACK = 20                   # candles for average volume
VOL_BREAKOUT_MULTIPLIER = 1.5       # breakout vol must be >= 1.5x avg

# --- Tier 1 Thresholds ---
# Ascending / Descending Triangle
FLAT_TOLERANCE = 0.015              # 1.5% flat zone
MIN_TOUCHES = 3                     # touches of trendline
TRIANGLE_MIN_SPAN = 15
TRIANGLE_MAX_SPAN = 150

# Double Top / Bottom
PEAK_TOLERANCE = 0.02               # peaks within 2%
DOUBLE_MIN_SEPARATION = 10          # candles between peaks/troughs
VALLEY_DEPTH = 0.03                 # 3% from peak level

# Bull / Bear Flag
POLE_MIN_RETURN = 0.05              # pole >= 5% move
POLE_MAX_CANDLES = 15               # pole forms in max 15 candles
FLAG_MIN_CANDLES = 5
FLAG_MAX_CANDLES = 25
FLAG_MAX_RETRACE = 0.50             # flag cannot retrace > 50% of pole

# --- Tier 2 Thresholds ---
SHOULDER_HEIGHT_TOLERANCE = 0.10    # R shoulder within 10% of L
SHOULDER_TIME_TOLERANCE = 0.40      # time symmetry within 40%

# Pennant (tighter than flag)
PENNANT_MIN_CANDLES = 5
PENNANT_MAX_CANDLES = 15

# --- Tier 3 Thresholds ---
RIM_TOLERANCE = 0.03                # cup rims within 3%
CUP_MIN_DEPTH = 0.10                # cup >= 10% deep
HANDLE_RETRACE = 0.50               # handle retrace max 50%
CUP_MIN_SPAN = 30                   # candles (1D only)

# --- Confirmation Buffers ---
CONFIRM_BUFFER_ABOVE = 1.005        # close > level * 1.005
CONFIRM_BUFFER_BELOW = 0.995        # close < level * 0.995
CONFIRM_BUFFER_HALF = 0.5           # 0.5% buffer for some patterns

# --- Backtest ---
SCAN_SKIP = 3                      # candles between re-evaluation (dedup guard)
TARGET_CAP = 0.65                  # 65% of measured move for continuation targets
OUTCOME_HOURS = 48                  # look-forward window for outcome
OUTCOME_MIN_MOVE = 0.005            # minimum 0.5% move to count as resolved

# --- Precision Gates ---
PRECISION_PAUSE_THRESHOLD = 0.60    # pause detector if rolling 7-day precision < 60%
PRECISION_WINDOW_DAYS = 7
MAX_DAILY_ALERTS = 5                # throttle if >5 confirmed alerts/day
