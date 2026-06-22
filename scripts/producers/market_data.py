"""
market_data.py — Shared async market data service for BTC skills.
All skills import from here to avoid duplicate fetch logic, rate limits, and timestamp misalignment.
"""
import time
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from collections import OrderedDict

import ccxt
import pandas as pd
import numpy as np

logger = logging.getLogger("market_data")

# --- Cache ---
# Simple in-memory TTL cache (no Redis needed for single-skill use)
_cache: Dict[str, Any] = OrderedDict()
_CACHE_TTL: Dict[str, int] = {
    "15m": 60,
    "4H": 300,
    "taker": 0,      # no cache — always fresh
    "funding": 300,
}


def _cache_key(endpoint: str, pair: str, timeframe: str, limit: int) -> str:
    return f"{endpoint}:{pair}:{timeframe}:{limit}"


def _cache_get(key: str) -> Optional[Any]:
    entry = _cache.get(key)
    if entry and time.time() < entry["expires"]:
        return entry["data"]
    if entry:
        del _cache[key]
    return None


def _cache_set(key: str, data: Any, ttl: int):
    _cache[key] = {"data": data, "expires": time.time() + ttl}


# --- Exchange Setup ---
_bitget: Optional[ccxt.bitget] = None


def _get_exchange() -> ccxt.bitget:
    global _bitget
    if _bitget is None:
        _bitget = ccxt.bitget({
            "enableRateLimit": True,
            "options": {"defaultType": "swap"},
        })
    return _bitget


# --- OHLCV Fetch ---

def _normalize_tf(timeframe: str) -> str:
    """Normalize timeframe for Bitget: '4H' -> '4h', '1H' -> '1h', etc."""
    return timeframe.lower()


def fetch_candles(
    pair: str = "BTC/USDT:USDT",
    timeframe: str = "15m",
    limit: int = 100,
    force_fresh: bool = False,
) -> pd.DataFrame:
    """Fetch OHLCV candles with caching. Returns DataFrame with columns [timestamp, open, high, low, close, volume]."""
    key = _cache_key("ohlcv", pair, timeframe, limit)
    if not force_fresh:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    ex = _get_exchange()
    tf = _normalize_tf(timeframe)
    try:
        raw = ex.fetch_ohlcv(pair, tf, limit=limit)
    except Exception as e:
        logger.error(f"OHLCV fetch failed: {e}")
        raise

    df = pd.DataFrame(
        raw, columns=["timestamp", "open", "high", "low", "close", "volume"]
    )
    df["timestamp"] = df["timestamp"].astype(np.int64)
    df = df.sort_values("timestamp").reset_index(drop=True)

    ttl = _CACHE_TTL.get(timeframe, 60)
    _cache_set(key, df, ttl)
    logger.debug(f"OHLCV {timeframe}: {len(df)} candles fetched")
    return df


# --- Taker Buy/Sell Ratio ---

def get_taker_for_candle(
    candle_close_ts: int,
    granularity_seconds: int,
    pair: str = "BTC/USDT:USDT",
) -> float:
    """
    Fetch taker buy/sell ratio for the period that started at (close_ts - granularity_seconds).
    
    NOTE: Bitget V1 taker-stats API was decommissioned (May 2026). 
    This function uses fetch_trades as a live proxy for recent candles.
    For historical candles (backtest), returns 1.0 (neutral).
    
    candle_close_ts: timestamp in MILLISECONDS of candle close
    granularity_seconds: e.g. 900 for 15m, 14400 for 4H
    
    Returns ratio (buyVol/sellVol), or 1.0 on failure/not available.
    """
    import time as _time
    now = int(_time.time() * 1000)
    
    # If the candle is recent (within last 5 minutes), use live trades
    if now - candle_close_ts < 300_000:
        ex = _get_exchange()
        try:
            start_ts = candle_close_ts - (granularity_seconds * 1000)
            trades = ex.fetch_trades(pair, limit=500)
            window_trades = [t for t in trades if start_ts <= t["timestamp"] < candle_close_ts]
            
            if window_trades:
                buy_vol = sum(t["amount"] for t in window_trades if t["side"] == "buy")
                sell_vol = sum(t["amount"] for t in window_trades if t["side"] == "sell")
                if sell_vol > 0:
                    return buy_vol / sell_vol
        except Exception as e:
            logger.debug(f"Live taker fetch failed: {e}")
    
    # Historical or unavailable: return neutral default
    logger.debug(f"Taker ratio default 1.0 for ts={candle_close_ts}")
    return 1.0


def get_funding_rate(pair: str = "BTC/USDT:USDT") -> float:
    """Fetch current funding rate. Returns float (e.g. 0.0001 = 0.01%), or 0.0 on failure."""
    key = _cache_key("funding", pair, "", 0)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    ex = _get_exchange()
    try:
        info = ex.fetch_funding_rate(pair)
        rate = float(info.get("fundingRate", 0))
    except Exception as e:
        logger.warning(f"Funding rate fetch failed: {e}")
        rate = 0.0

    _cache_set(key, rate, _CACHE_TTL["funding"])
    return rate


# --- Indicators ---

def compute_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """Compute RSI on a pandas Series of close prices. Returns Series of same length."""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> dict:
    """Compute MACD. Returns dict with macd_line, signal_line, histogram as Series."""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return {
        "macd_line": macd_line,
        "signal_line": signal_line,
        "histogram": histogram,
    }


def compute_ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


# --- Convenience: Fetch 4H indicators ---

def fetch_indicators_4h(pair: str = "BTC/USDT:USDT", limit: int = 55) -> dict:
    """
    Fetch 4H candles and compute RSI, MACD, EMA50.
    Returns dict with latest values and full series.
    """
    df = fetch_candles(pair, "4H", limit=limit)
    close = df["close"]
    
    rsi_series = compute_rsi(close, 14)
    macd = compute_macd(close)
    ema50_series = compute_ema(close, 50)
    
    return {
        "rsi": round(float(rsi_series.iloc[-1]), 2),
        "macd_line": round(float(macd["macd_line"].iloc[-1]), 2),
        "signal_line": round(float(macd["signal_line"].iloc[-1]), 2),
        "histogram": round(float(macd["histogram"].iloc[-1]), 2),
        "macd_cross": "BEAR" if macd["histogram"].iloc[-1] < 0 else "BULL",
        "ema50": round(float(ema50_series.iloc[-1]), 2),
        "price": round(float(close.iloc[-1]), 2),
        "df": df,
    }


# --- Cache info ---
def cache_stats() -> dict:
    return {
        "entries": len(_cache),
        "keys": list(_cache.keys()),
    }
