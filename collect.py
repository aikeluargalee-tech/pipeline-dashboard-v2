#!/usr/bin/env python3
"""
Pipeline Dashboard — Unified Data Collector
Reads /tmp/btc_*.json files + AI-3 state → writes structured layer data.
Designed to be called by cron every 1H.

Architecture (GetClaw-approved):
  Layer 0: Gatekeeper (PROCEED/TIGHTENED/PAUSE/ABORT)
  Layer 1: Macro & Speculation (primary driver)
  Layer 2: Structural Liquidity (S/R, magnets, volume profile)
  Layer 3: Derivatives (funding, OI, L/S, order flow)
  Layer 4: Cycle Context (MVRV, netflow, options skew)
  Supplementary: Chart patterns, MA, signal accuracy (collapsed)
"""
import os
import sys
import json
import math
import re
import shutil
import subprocess
import logging
import urllib.request
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', datefmt='%H:%M:%S')
log = logging.getLogger("collector")

BASE = Path(__file__).parent
DATA = BASE / "data"
SCRIPTS = BASE / "scripts"
ASSETS = BASE / "assets"
DATA.mkdir(exist_ok=True)
ASSETS.mkdir(exist_ok=True)

# Paths
HOME = Path.home()
FREE_MCP = HOME / "pipeline-dashboard V2" / "scripts" / "producers"
AI3_STATE = HOME / ".gemini/antigravity/scratch/sigma_trading_engine/ai3_watch_state.json"
HEATMAP_JSON = Path("/tmp/btc_heatmap_clusters.json")
V7_IMAGES = Path("/tmp/btc_v7_images.json")
GATE_FILE = DATA / "manual_gate.json"


def ts():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def read_json(path):
    """Read a JSON file, return None if unavailable or invalid."""
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        log.info("JSON file not found: %s", path)
    except json.JSONDecodeError as e:
        log.warning("Invalid JSON in %s: %s", path, e)
    except Exception as e:
        log.warning("Failed to read JSON %s: %s", path, e)
    return None


def append_prediction(prediction_type, data):
    """
    Append a prediction to data/predictions.json.
    - regime_change: maps to synthesis verdict change.
    - trading_signal: maps to val_absorption, breakout_retest, breakdown_retest ENTRY_SIGNAL.
    
    De-duplicates entries to avoid duplicate predictions on consecutive hourly runs.
    """
    pred_file = DATA / "predictions.json"
    
    predictions = []
    if pred_file.exists():
        try:
            with open(pred_file) as f:
                content = json.load(f)
                if isinstance(content, dict) and "predictions" in content:
                    predictions = content["predictions"]
                elif isinstance(content, list):
                    predictions = content
        except Exception as e:
            log.warning("Failed to read predictions.json: %s", e)
            
    now_utc = datetime.now(timezone.utc).isoformat()
    
    if prediction_type == "regime_change":
        # Check if the last logged regime matches this one
        last_regime = None
        for p in reversed(predictions):
            if p.get("type") == "regime_change":
                last_regime = p
                break
        
        new_verdict = data.get("synthesis", {}).get("verdict")
        if last_regime and last_regime.get("regime_label") == new_verdict:
            # Duplicate, do not append
            return
            
        direction = "neutral"
        if new_verdict:
            if "BULL" in new_verdict.upper():
                direction = "bullish"
            elif "BEAR" in new_verdict.upper():
                direction = "bearish"
            
        entry = {
            "id": f"regime_{uuid.uuid4().hex[:8]}",
            "type": "regime_change",
            "created_at": now_utc,
            "btc_price_at_call": data.get("btc_price"),
            "direction": direction,
            "gate0_status": data.get("gate", {}).get("verdict", "UNKNOWN"),
            "regime_label": new_verdict,
            "rationale_snapshot": data,
            "outcomes": {"1d": None, "7d": None, "30d": None},
            "resolved": False
        }
        predictions.append(entry)
        log.info("Appended new regime change prediction: %s", new_verdict)
        
    elif prediction_type == "trading_signal":
        # Data is a signal dict from val_absorption, breakout_retest, or breakdown_retest
        sig_name = data.get("signal")
        level = data.get("level") or data.get("val")
        direction = "neutral"
        if data.get("direction") == "LONG" or "ABSORPTION" in sig_name or "BREAKOUT" in sig_name:
            direction = "bullish"
        elif data.get("direction") == "SHORT" or "BREAKDOWN" in sig_name or "BREAK" in sig_name:
            direction = "bearish"
            
        # De-duplicate: check if same level & type logged in last 24h
        for p in reversed(predictions):
            if p.get("type") == "trading_signal" and p.get("signal_name") == sig_name:
                try:
                    p_time = datetime.fromisoformat(p["created_at"])
                    now_dt = datetime.fromisoformat(now_utc)
                    if now_dt - p_time < timedelta(hours=24):
                        p_level = p.get("entry")
                        if p_level and level and abs(p_level - level) / level < 0.005:
                            # Duplicate signal within 24h
                            return
                except Exception:
                    pass
                        
        entry = {
            "id": f"signal_{uuid.uuid4().hex[:8]}",
            "type": "trading_signal",
            "signal_name": sig_name,
            "created_at": now_utc,
            "btc_price_at_call": data.get("btc_price") or data.get("price"),
            "direction": direction,
            "entry": level,
            "stop_loss": data.get("stop_loss"),
            "target": data.get("target"),
            "confidence": data.get("confidence", "MEDIUM"),
            "gate0_status": data.get("gate0_status", "UNKNOWN"),
            "regime_label": data.get("regime_label", "UNKNOWN"),
            "rationale_snapshot": data,
            "outcomes": {"1d": None, "7d": None, "30d": None},
            "resolved": False
        }
        predictions.append(entry)
        log.info("Appended new trading signal prediction: %s at %s", sig_name, level)
        
    # Write back atomically
    try:
        tmp_file = DATA / ".predictions.json.tmp"
        with open(tmp_file, "w") as f:
            json.dump({"predictions": predictions}, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, pred_file)
    except Exception as e:
        log.error("Failed to write predictions.json: %s", e)


def safe_float(value, context, default=None):
    """Convert API numeric fields without letting malformed payloads crash collection."""
    try:
        return float(value)
    except (TypeError, ValueError) as e:
        log.warning("Invalid float for %s: %r (%s)", context, value, e)
        return default


def valid_tmp_png(path):
    """Return a resolved PNG path from allowed directories, or None if unsafe."""
    try:
        resolved = Path(path).resolve()
        if resolved.suffix.lower() != ".png":
            log.warning("Rejected V7 image with non-png extension: %s", path)
            return None
        # Allow /tmp and V2 assets/ as safe source dirs
        v2_assets = HOME / "pipeline-dashboard V2" / "assets"
        allowed_roots = [Path("/tmp").resolve(), v2_assets.resolve()]
        if not any(root in resolved.parents or root == resolved.parent for root in allowed_roots):
            log.warning("Rejected V7 image outside allowed dirs: %s", path)
            return None
        if not resolved.is_file():
            log.warning("Rejected V7 image missing source file: %s", path)
            return None
        return resolved
    except (OSError, TypeError, ValueError) as e:
        log.warning("Rejected invalid V7 image path %r: %s", path, e)
        return None


def sanitize(obj):
    """Remove NaN/Infinity values that break JSON parsing."""
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize(v) for v in obj]
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def write_json(name, data):
    """Atomically write data to data/<name>.json."""
    data = sanitize({**data, "_collected": ts()})
    target = DATA / name
    tmp = target.with_name(f".{target.name}.tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)


def write_sitemap():
    """Regenerate sitemap.xml with current timestamp for AI crawler freshness signals."""
    from datetime import datetime, timezone
    today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    
    base = "https://aikeluargalee-tech.github.io/pipeline-dashboard-v2"
    try:
        remote_url = subprocess.check_output(["git", "remote", "get-url", "origin"], text=True, stderr=subprocess.DEVNULL).strip()
        match = re.search(r'/([^/]+?)(?:\.git)?$', remote_url)
        if match:
            base = f"https://aikeluargalee-tech.github.io/{match.group(1)}"
    except Exception:
        pass

    # Static pages with their relative paths and priorities
    pages = [
        ("", 1.0, "always"),           # Homepage
        ("dashboard/", 0.9, "always"),  # Live dashboard
        ("methodology/", 0.8, "weekly"),
        ("research/", 0.8, "weekly"),
        ("glossary/", 0.7, "weekly"),
        ("verdicts/", 0.8, "daily"),
        ("track-record/", 0.8, "daily"),
        ("events-and-disruptions/", 0.7, "weekly"),
        ("compare/", 0.7, "monthly"),
        ("compare/gate0-vs-glassnode/", 0.6, "monthly"),
        ("compare/gate0-vs-cryptoquant/", 0.6, "monthly"),
        ("compare/gate0-vs-coinglass/", 0.6, "monthly"),
        ("faq/", 0.6, "monthly"),
        ("about/", 0.5, "monthly"),
        ("contact/", 0.4, "yearly"),
        ("privacy/", 0.3, "yearly"),
        ("terms/", 0.3, "yearly"),
    ]

    # Research articles (6 pillars + 30 supporting)
    research_articles = [
        "research/mvrv-z-score/",
        "research/liquidation-magnets/",
        "research/gate0-framework/",
        "research/derivatives-positioning/",
        "research/bitcoin-macro-correlation/",
        "research/trading-sessions/",
        "research/sopr-spending-behavior/",
        "research/puell-multiple-miner-revenue/",
        "research/exchange-netflow-interpretation/",
        "research/bitcoin-cycle-phases/",
        "research/composite-cycle-score-methodology/",
        "research/volume-profile-poc-vah-val/",
        "research/atr-weighted-support-resistance/",
        "research/vice-grip-trapped-between-magnets/",
        "research/squeeze-vs-sweep-regimes/",
        "research/val-absorption-smart-money-detection/",
        "research/black-swan-detection-scoring/",
        "research/position-sizing-proceed-to-abort/",
        "research/vix-bitcoin-spillover/",
        "research/stablecoin-health-monitoring/",
        "research/l1-manual-gate-human-override/",
        "research/funding-rate-sentiment-gauge/",
        "research/open-interest-accumulation-unwinding/",
        "research/cvd-cumulative-volume-delta/",
        "research/long-short-ratio-top-traders/",
        "research/taker-buy-sell-ratio/",
        "research/dxy-bitcoin-inverse-correlation/",
        "research/treasury-yields-risk-free-pressure/",
        "research/bitcoin-etf-flow-tracking/",
        "research/m2-money-supply-liquidity/",
        "research/risk-asset-correlation-spy-qqq/",
        "research/breakout-retest-lifecycle/",
        "research/breakdown-retest-bearish-mirror/",
        "research/weekend-trading-noisier-signals/",
        "research/signal-tracking-win-loss-expired/",
        "research/golden-window-ny-open/",
    ]
    for p in research_articles:
        pages.append((p, 0.7, "weekly"))

    urls = []
    # Dynamic pages get today's date; static pages get their actual file modification date
    dynamic_paths = {"", "dashboard/", "verdicts/"}
    for path, priority, freq in pages:
        loc = f"{base}/{path}" if path else f"{base}/"
        if path in dynamic_paths or path.startswith("verdicts/"):
            lastmod = today_iso
        else:
            # Use actual file modification date for static pages
            file_path = BASE / path / "index.html" if path else BASE / "index.html"
            if file_path.exists():
                mtime = file_path.stat().st_mtime
                lastmod = datetime.fromtimestamp(mtime, timezone.utc).strftime("%Y-%m-%d")
            else:
                lastmod = today_iso
        urls.append(f"""  <url>
    <loc>{loc}</loc>
    <lastmod>{lastmod}</lastmod>
    <changefreq>{freq}</changefreq>
    <priority>{priority}</priority>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{chr(10).join(urls)}
</urlset>
"""
    target = BASE / "sitemap.xml"
    tmp = target.with_name(f".{target.name}.tmp")
    with open(tmp, "w") as f:
        f.write(sitemap)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    log.info("Sitemap updated → %s (%d pages)", today_iso, len(pages))


def inject_timestamps_into_html():
    """Inject current ISO timestamp + live verdict + BTC price into static HTML.

    AI crawlers that skip JavaScript see real timestamps and verdict data —
    no empty content='' gaps or 'LOADING' placeholders.
    This is the cold-DOM fix: data baked in at build time, refreshed by JS after.
    """
    from datetime import datetime, timezone
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")

    # Read current verdict and price for cold-DOM injection
    regime = read_json(str(DATA / "regime.json"))
    btc = read_json(str(DATA / "btc_price.json"))
    verdict = "UNKNOWN"
    verdict_detail = ""
    btc_price_str = "—"
    if regime and regime.get("synthesis"):
        verdict = regime["synthesis"].get("verdict", "UNKNOWN")
        verdict_detail = regime["synthesis"].get("detail", "")
    if btc and btc.get("price"):
        btc_price_str = f"${btc['price']:,.0f}"

    # --- Inject into dashboard/index.html ---
    target = BASE / "dashboard" / "index.html"
    tmp = target.with_name(f".{target.name}.tmp")

    with open(target, "r") as f:
        html = f.read()

    # Replace timestamp meta tags
    html = re.sub(
        r'<meta property="og:updated_time" id="og-updated" content="[^"]*">',
        f'<meta property="og:updated_time" id="og-updated" content="{now_iso}">',
        html
    )
    html = re.sub(
        r'<meta property="article:modified_time" id="article-modified" content="[^"]*">',
        f'<meta property="article:modified_time" id="article-modified" content="{now_iso}">',
        html
    )
    html = re.sub(
        r'<meta name="DC.date" id="dc-date" content="[^"]*">',
        f'<meta name="DC.date" id="dc-date" content="{now_iso}">',
        html
    )
    html = re.sub(
        r'"dateModified": "[^"]*"',
        f'"dateModified": "{now_iso}"',
        html
    )

    # Replace LOADING placeholder in regime verdict with actual verdict
    html = re.sub(
        r'<div class="regime-verdict" id="regime-verdict">[^<]*</div>',
        f'<div class="regime-verdict" id="regime-verdict">{verdict}</div>',
        html
    )
    # Replace empty regime detail with actual detail
    html = re.sub(
        r'<div class="regime-detail" id="regime-detail">[^<]*</div>',
        f'<div class="regime-detail" id="regime-detail">{verdict_detail}</div>',
        html
    )
    # Replace gate badge LOADING
    html = re.sub(
        r'<span class="gate-badge" id="gate-badge">[^<]*</span>',
        f'<span class="gate-badge" id="gate-badge">{verdict}</span>',
        html
    )
    # Replace BTC price placeholder
    html = re.sub(
        r'<span class="btc-price" id="btc-price">[^<]*</span>',
        f'<span class="btc-price" id="btc-price">{btc_price_str}</span>',
        html
    )

    with open(tmp, "w") as f:
        f.write(html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, target)
    log.info("Timestamps + verdict injected into dashboard/index.html → %s (%s, %s)", now_iso, verdict, btc_price_str)

    # --- Inject into homepage index.html ---
    home_target = BASE / "index.html"
    home_tmp = home_target.with_name(f".{home_target.name}.tmp")

    with open(home_target, "r") as f:
        home_html = f.read()

    # Replace homepage verdict placeholder
    home_html = re.sub(
        r'<div class="regime-verdict" id="home-verdict">[^<]*</div>',
        f'<div class="regime-verdict" id="home-verdict">{verdict}</div>',
        home_html
    )
    # Replace homepage verdict detail placeholder
    home_html = re.sub(
        r'<div class="regime-detail" id="home-verdict-detail">[^<]*</div>',
        f'<div class="regime-detail" id="home-verdict-detail">{btc_price_str} · {verdict_detail}</div>',
        home_html
    )

    with open(home_tmp, "w") as f:
        f.write(home_html)
        f.flush()
        os.fsync(f.fileno())
    os.replace(home_tmp, home_target)
    log.info("Verdict injected into homepage index.html → %s (%s, %s)", now_iso, verdict, btc_price_str)


def fetch_with_retry(url, timeout=10, max_attempts=3, delay=2):
    """Fetch URL with retry and exponential backoff."""
    for attempt in range(max_attempts):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception as e:
            if attempt == max_attempts - 1:
                log.warning(f"fetch_with_retry failed after {max_attempts} attempts: {url} — {e}")
                return None
            import time
            time.sleep(delay * (2 ** attempt))
    return None


# ─── Layer 0: Gatekeeper ──────────────────────────────────────

def collect_gate0():
    """Compute Layer 0 verdict with 4 states."""
    gate0_raw = read_json("/tmp/btc_gate0.json")
    risk = read_json("/tmp/btc_risk_state.json")
    session = read_json("/tmp/btc_session_state.json")
    stablecoins = read_json("/tmp/btc_stablecoin_state.json")
    ai3 = read_json(str(AI3_STATE))

    # Determine individual module states
    modules = {}

    # Black Swan
    bs_score = 0
    if gate0_raw:
        bs_score = safe_float(gate0_raw.get("black_swan_score"), "black_swan_score", 0) or 0
    if bs_score >= 12:
        modules["black_swan"] = {"state": "ABORT", "score": bs_score}
    elif bs_score >= 8:
        modules["black_swan"] = {"state": "PAUSE", "score": bs_score}
    elif bs_score >= 5:
        modules["black_swan"] = {"state": "TIGHTENED", "score": bs_score}
    else:
        modules["black_swan"] = {"state": "PROCEED", "score": bs_score}

    # VIX from risk state (yfinance real-time)
    vix_val = None
    vix_weekly_chg = None
    spx_chg = None
    if risk:
        vix_val = risk.get("vix")
        assets = risk.get("assets") or {}
        vix_asset = assets.get("^VIX", {})
        if vix_val is None and isinstance(vix_asset, dict):
            vix_val = vix_asset.get("close")
        # SPX change from SPY or QQQ
        spy = assets.get("SPY", {})
        qqq = assets.get("QQQ", {})
        if isinstance(spy, dict) and spy.get("change_pct") is not None and not (isinstance(spy["change_pct"], float) and math.isnan(spy["change_pct"])):
            spx_chg = spy.get("change_pct")
        elif isinstance(qqq, dict) and qqq.get("change_pct") is not None and not (isinstance(qqq["change_pct"], float) and math.isnan(qqq["change_pct"])):
            spx_chg = qqq.get("change_pct")
    # Fallback: fetch SPY change directly from Yahoo
    if spx_chg is None:
        spy_yahoo = fetch_yahoo_price("SPY")
        if spy_yahoo.get("change_pct") is not None:
            spx_chg = spy_yahoo["change_pct"]

    # VIX weekly regime from 5-day chart
    try:
        vix_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=5d"
        req = urllib.request.Request(vix_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            vix_chart = json.loads(resp.read())
        closes = vix_chart["chart"]["result"][0]["indicators"]["quote"][0]["close"]
        closes = [c for c in closes if c is not None]
        if len(closes) >= 2:
            vix_weekly_chg = round((closes[-1] - closes[0]) / closes[0] * 100, 1)
    except Exception:
        pass

    vix_state = "PROCEED"
    vix_val_num = safe_float(vix_val, "vix_value")
    if vix_val_num is not None:
        if vix_val_num > 40:
            vix_state = "ABORT"
        elif vix_val_num > 30:
            vix_state = "PAUSE"
        elif vix_val_num > 22:
            vix_state = "TIGHTENED"
    modules["vix_spx"] = {"state": vix_state, "vix": vix_val, "spx_change": spx_chg, "vix_weekly_chg": vix_weekly_chg}

    # AI-3 Wave
    ai3_active = False
    if ai3:
        ai3_active = ai3.get("spacex_s1_active", False)
    modules["ai3_wave"] = {"state": "TIGHTENED" if ai3_active else "PROCEED", "active": ai3_active}

    # Stablecoins
    stablecoin_state = "PROCEED"
    if stablecoins:
        for coin in stablecoins.get("coins", []):
            dev = abs(safe_float(coin.get("deviation_pct"), "stablecoin deviation", 0) or 0)
            if dev > 2.0:
                stablecoin_state = "ABORT"
                break
            elif dev > 0.5:
                stablecoin_state = "PAUSE"
    modules["stablecoins"] = {"state": stablecoin_state}

    # Session — always emit, with fallback when upstream is missing
    if session is None:
        session = {}
    ny_open_time = session.get("ny_open_time")
    # Compute NY open if upstream is null (9:30 AM ET → 13:30 UTC summer / 14:30 UTC winter)
    if ny_open_time is None:
        now_utc = datetime.now(timezone.utc)
        # Proper DST: 2nd Sunday March, 1st Sunday November
        # weekday(): Monday=0, Sunday=6. Formula finds first Sunday.
        mar1 = now_utc.replace(month=3, day=1, hour=0, minute=0, second=0, microsecond=0)
        first_sunday_mar = (6 - mar1.weekday()) % 7 + 1
        dst_start = mar1.replace(day=first_sunday_mar + 7)
        nov1 = now_utc.replace(month=11, day=1, hour=0, minute=0, second=0, microsecond=0)
        first_sunday_nov = (6 - nov1.weekday()) % 7 + 1
        dst_end = nov1.replace(day=first_sunday_nov)
        is_edt = dst_start <= now_utc < dst_end
        ny_open_hour_utc = 13 if is_edt else 14
        ny_open_dt = now_utc.replace(hour=ny_open_hour_utc, minute=30, second=0, microsecond=0)
        if now_utc.hour >= ny_open_hour_utc + 7:
            ny_open_dt += timedelta(days=1)
        ny_open_time = ny_open_dt.strftime("%H:%M UTC")
    session_info = {
        "name": session.get("current_session", "Unknown"),
        "ny_open": ny_open_time,
        "golden_window": session.get("golden_window"),
        "is_weekend": session.get("is_weekend", False),
    }
    if session.get("is_weekend"):
        modules["session"] = {"state": "TIGHTENED", **session_info}
    else:
        modules["session"] = {"state": "PROCEED", **session_info}

    # Compute overall verdict (most restrictive wins)
    state_priority = {"ABORT": 4, "PAUSE": 3, "TIGHTENED": 2, "PROCEED": 1}
    verdict = "PROCEED"
    sources = []
    for name, mod in modules.items():
        mod_state = mod.get("state", "PROCEED")
        if state_priority.get(mod_state, 0) > state_priority.get(verdict, 0):
            verdict = mod_state
            sources = [name]
        elif state_priority.get(mod_state, 0) == state_priority.get(verdict, 0):
            sources.append(name)

    # Active rules based on verdict
    rules = {}
    if verdict == "TIGHTENED":
        rules = {"action": "Reduce position size. Tight stops. Wait for conditions to clear."}
    elif verdict == "PAUSE":
        rules = {"action": "No new positions. Reduce open size. Monitor only."}
    elif verdict == "ABORT":
        rules = {"action": "No new positions. Evaluate existing for emergency close."}

    return {
        "verdict": verdict,
        "sources": sources,
        "rules": rules,
        "modules": modules,
        "timestamp": ts(),
    }


# ─── Layer 1: Macro & Speculation ─────────────────────────────

def fetch_yahoo_price(symbol):
    """Fetch current price from Yahoo Finance v8 API (free, no key)."""
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=1d"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        result = data["chart"]["result"][0]
        meta = result.get("meta", {})
        price = meta.get("regularMarketPrice")
        prev_close = meta.get("chartPreviousClose") or meta.get("previousClose")
        change_pct = None
        if price and prev_close and prev_close > 0:
            change_pct = round((price - prev_close) / prev_close * 100, 2)
        return {"price": price, "change_pct": change_pct}
    except Exception:
        return {"price": None, "change_pct": None}


def fetch_etf_flow():
    """Fetch BTC ETF flow data from Farside (free, no API key)."""
    try:
        # Try Farside.co.uk RSS/JSON-like endpoint
        url = "https://farside.co.uk/btc/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")

        # Parse the table from HTML to extract daily flows
        # Look for table rows with dates and flow values
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.DOTALL)
        flows = []
        for row in rows:
            cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.DOTALL)
            if len(cells) >= 2:
                date_cell = re.sub(r'<[^>]+>', '', cells[0]).strip()
                total_cell = re.sub(r'<[^>]+>', '', cells[-1]).strip()
                # Try to parse the total value
                cleaned = total_cell.replace(",", "").replace("(", "-").replace(")", "").replace("$", "").strip()
                if cleaned and cleaned not in ("", "-", "Total"):
                    try:
                        val = safe_float(cleaned, "ETF flow total")
                        if val is None:
                            continue
                        # Check if date looks like a valid entry
                        if re.match(r'\d{1,2}\s+\w+', date_cell):
                            flows.append({"date": date_cell, "total": val})
                    except (ValueError, TypeError):
                        pass

        if flows:
            daily_net = flows[-1]["total"] if flows else None
            weekly_net = sum(f["total"] for f in flows[-5:]) if len(flows) >= 5 else sum(f["total"] for f in flows)

            # Determine trend
            if len(flows) >= 3:
                recent = sum(f["total"] for f in flows[-3:])
                if recent > 0:
                    trend = "inflow"
                elif recent < -200:
                    trend = "heavy_outflow"
                else:
                    trend = "mild_outflow"
            else:
                trend = "unknown"

            return {
                "daily_net": round(daily_net, 1) if daily_net is not None else None,
                "weekly_net": round(weekly_net, 1) if weekly_net is not None else None,
                "trend": trend,
            }
    except Exception:
        pass

    # Fallback: try reading the existing /tmp file with correct field mapping
    etf = read_json("/tmp/btc_etf_flow.json")
    if etf:
        return map_etf_fields(etf)
    return None


def map_etf_fields(etf):
    """Map ETF flow fields from various source formats."""
    daily_net = None
    weekly_net = None
    trend = None

    # Try multiple possible field names for daily net
    for key in ["daily_net_flow_usd", "daily_net"]:
        if etf.get(key) is not None:
            daily_net = etf[key]
            break
    # Parse from display string like "$-131.2M"
    if daily_net is None and etf.get("total_flow_display"):
        disp = str(etf["total_flow_display"]).replace("$", "").replace("M", "").replace(",", "").strip()
        try:
            daily_net = safe_float(disp, "ETF total_flow_display")
        except (ValueError, TypeError):
            pass
    # Try from latest.total
    if daily_net is None and isinstance(etf.get("latest"), dict):
        daily_net = etf["latest"].get("total")

    # Try multiple possible field names for weekly net
    for key in ["weekly_net_flow_usd", "weekly_net", "streak_7d"]:
        if etf.get(key) is not None:
            val = etf[key]
            if isinstance(val, (int, float)):
                weekly_net = val
                break
    # Parse from display string like "$-359.1M"
    if weekly_net is None and etf.get("streak_7d_display"):
        disp = str(etf["streak_7d_display"]).replace("$", "").replace("M", "").replace(",", "").strip()
        try:
            weekly_net = safe_float(disp, "ETF streak_7d_display")
        except (ValueError, TypeError):
            pass

    # Trend
    trend = etf.get("trend") or etf.get("direction")
    if not trend:
        if isinstance(daily_net, (int, float)) and daily_net is not None:
            if daily_net > 0:
                trend = "inflow"
            elif daily_net < -200:
                trend = "heavy_outflow"
            else:
                trend = "mild_outflow"

    if daily_net is not None or weekly_net is not None:
        return {
            "daily_net": round(daily_net, 1) if isinstance(daily_net, (int, float)) else None,
            "weekly_net": round(weekly_net, 1) if isinstance(weekly_net, (int, float)) else None,
            "trend": trend,
        }
    return None


def classify_macro_regime(dxy, vix, yield_10y, etf_trend):
    """Classify macro regime from available signals."""
    bullish = 0
    bearish = 0
    
    if dxy is not None:
        if dxy < 100: bullish += 1
        elif dxy > 104: bearish += 1
    
    if vix is not None:
        if vix < 18: bullish += 1
        elif vix > 25: bearish += 1
    
    if yield_10y is not None:
        if yield_10y < 4.0: bullish += 1
        elif yield_10y > 5.0: bearish += 1
    
    if etf_trend:
        if "inflow" in etf_trend: bullish += 1
        elif "outflow" in etf_trend: bearish += 1
    
    if bullish >= 3: return "risk-on"
    elif bearish >= 3: return "risk-off"
    elif bullish > bearish: return "mild-risk-on"
    elif bearish > bullish: return "mild-risk-off"
    return "mixed"


def collect_macro():
    """Layer 1 — primary driver."""
    macro = read_json("/tmp/btc_macro_state.json")
    risk = read_json("/tmp/btc_risk_state.json")
    news = read_json("/tmp/btc_news_state.json")
    etf = read_json("/tmp/btc_etf_flow.json")
    poly = read_json("/tmp/btc_polymarket.json")

    result = {}

    # DXY, yields, M2
    if macro:
        result["dxy"] = macro.get("dxy")
        result["us_10y_yield"] = macro.get("us_10y_yield_percent")
        result["m2_supply"] = macro.get("us_m2_billions")
        result["regime"] = macro.get("regime")

    # Risk assets — with Yahoo Finance fallback for NaN/missing prices
    if risk:
        assets = risk.get("assets") or {}
        risk_items = {}
        for ticker in ["SPY", "QQQ", "GLD"]:
            if ticker in assets:
                a = assets[ticker]
                if isinstance(a, dict):
                    price = a.get("close")
                    change = a.get("change_pct")
                    # Fallback: if price is NaN/None, fetch directly from Yahoo
                    if price is None or (isinstance(price, float) and math.isnan(price)):
                        yahoo = fetch_yahoo_price(ticker)
                        price = yahoo.get("price")
                        change = yahoo.get("change_pct")
                    risk_items[ticker] = {
                        "price": price,
                        "change_pct": change,
                    }
            else:
                # Ticker not in risk state at all — fetch from Yahoo
                yahoo = fetch_yahoo_price(ticker)
                if yahoo.get("price"):
                    risk_items[ticker] = yahoo
        result["risk_assets"] = risk_items

        # VIX — key is "^VIX" in risk state, also try "VIX"
        vix_data = assets.get("^VIX") or assets.get("VIX")
        if isinstance(vix_data, dict):
            vix_close = vix_data.get("close")
            if vix_close and not (isinstance(vix_close, float) and math.isnan(vix_close)):
                result["vix"] = vix_close
            else:
                result["vix"] = risk.get("vix")  # Top-level vix field
        else:
            result["vix"] = risk.get("vix")

        # Final VIX fallback: direct Yahoo fetch if still null
        if result.get("vix") is None:
            try:
                vix_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=1d"
                req = urllib.request.Request(vix_url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    vix_chart = json.loads(resp.read())
                vix_meta = vix_chart["chart"]["result"][0].get("meta", {})
                result["vix"] = vix_meta.get("regularMarketPrice")
            except Exception:
                pass

    # ETF flows — map fields correctly from /tmp file, or fetch fresh
    etf_mapped = None
    if etf:
        etf_mapped = map_etf_fields(etf)
    if etf_mapped is None:
        # Try fetching fresh from Farside
        etf_mapped = fetch_etf_flow()
    if etf_mapped:
        result["etf_flow"] = etf_mapped

    # Polymarket
    if poly:
        result["polymarket"] = poly

    # News (last 5 macro-relevant headlines)
    if news and "headlines" in news:
        result["news"] = news["headlines"][:5]

    # Macro regime — compute from available signals if upstream is null
    if result.get("regime") is None:
        etf_trend = result.get("etf_flow", {}).get("trend") if result.get("etf_flow") else None
        result["regime"] = classify_macro_regime(
            result.get("dxy"),
            result.get("vix"),
            result.get("us_10y_yield"),
            etf_trend,
        )

    # ── Fallback: fetch risk assets directly from Yahoo when /tmp files are missing ──
    if not result.get("risk_assets") or len(result.get("risk_assets", {})) == 0:
        fallback_assets = {}
        for ticker in ["SPY", "QQQ", "GLD"]:
            yahoo = fetch_yahoo_price(ticker)
            if yahoo.get("price"):
                fallback_assets[ticker] = yahoo
        if fallback_assets:
            result["risk_assets"] = fallback_assets
            log.info("Risk assets fallback (Yahoo direct): %s", list(fallback_assets.keys()))

    # ── Fallback: fetch VIX directly from Yahoo when /tmp files are missing ──
    if result.get("vix") is None:
        try:
            vix_url = "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX?interval=1d&range=1d"
            req = urllib.request.Request(vix_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                vix_chart = json.loads(resp.read())
            vix_meta = vix_chart["chart"]["result"][0].get("meta", {})
            vix_price = vix_meta.get("regularMarketPrice")
            if vix_price is not None:
                result["vix"] = vix_price
                log.info("VIX fallback (Yahoo direct): %s", vix_price)
        except Exception:
            pass

    # ── Fallback: fetch DXY, yields, M2 directly from FRED when /tmp files are missing ──
    if result.get("dxy") is None:
        try:
            # DXY from Yahoo (DX-Y.NYB)
            dxy_url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=1d"
            req = urllib.request.Request(dxy_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                dxy_data = json.loads(resp.read())
            dxy_price = dxy_data["chart"]["result"][0]["meta"].get("regularMarketPrice")
            if dxy_price is not None:
                result["dxy"] = dxy_price
                log.info("DXY fallback (Yahoo direct): %s", dxy_price)
        except Exception:
            pass

    return result


# ─── Layer 2: Structural Liquidity ────────────────────────────

def generate_volume_profile():
    """Build volume profile from 7 days of 1h Binance klines → /tmp/btc_volume_profile.json"""
    klines = fetch_with_retry(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=168"
    )
    if not klines or len(klines) < 48:
        log.warning("Volume profile: insufficient kline data (%d candles)", len(klines) if klines else 0)
        return

    # Build price bins (step = $50)
    step = 50
    bins = {}  # price_level → total volume
    for k in klines:
        try:
            high, low, vol = float(k[2]), float(k[3]), float(k[5])
        except (IndexError, ValueError, TypeError):
            continue
        # Guard against anomalous data where high < low
        if high < low:
            high, low = low, high
        # Distribute candle volume evenly across price range it covers
        lo_bin = int(low // step) * step
        hi_bin = int(high // step) * step
        if hi_bin == lo_bin:
            bins[lo_bin] = bins.get(lo_bin, 0) + vol
        else:
            n_bins = (hi_bin - lo_bin) // step + 1
            vol_per_bin = vol / n_bins
            for lvl in range(lo_bin, hi_bin + step, step):
                bins[lvl] = bins.get(lvl, 0) + vol_per_bin

    if not bins:
        return

    sorted_bins = sorted(bins.items(), key=lambda x: x[1], reverse=True)
    total_vol = sum(bins.values())

    # POC = price level with highest volume
    poc = sorted_bins[0][0]

    # Value Area = 70% of total volume, centered on POC
    va_target = total_vol * 0.7
    va_vol = bins[poc]
    va_low, va_high = poc, poc
    sorted_prices = sorted(bins.keys())
    poc_idx = sorted_prices.index(poc)
    lo_i, hi_i = poc_idx, poc_idx

    while va_vol < va_target:
        expand_lo = bins.get(sorted_prices[lo_i - 1], 0) if lo_i > 0 else 0
        expand_hi = bins.get(sorted_prices[hi_i + 1], 0) if hi_i < len(sorted_prices) - 1 else 0
        if expand_lo == 0 and expand_hi == 0:
            break
        if expand_lo >= expand_hi:
            lo_i -= 1
            va_low = sorted_prices[lo_i]
            va_vol += expand_lo
        else:
            hi_i += 1
            va_high = sorted_prices[hi_i]
            va_vol += expand_hi

    # HVNs = top 5 volume nodes (excluding POC)
    hvns = [{"price": b[0], "volume": round(b[1])} for b in sorted_bins[1:6]]

    # LVNs = bottom 3 volume nodes (above 0)
    lvns_all = sorted(bins.items(), key=lambda x: x[1])
    lvns = [{"price": b[0], "volume": round(b[1])} for b in lvns_all[:3] if b[1] > 0]

    result = {
        "poc": poc,
        "vah": va_high + step,  # upper edge of VAH bin
        "val": va_low,          # lower edge of VAL bin
        "hvns": hvns,
        "lvns": lvns,
        "bins": [{"price": p, "volume": round(v)} for p, v in sorted(bins.items())],
        "candles_used": len(klines),
        "total_volume": round(total_vol),
        "bin_step": step,
    }

    # Atomic write
    tmp = "/tmp/btc_volume_profile.json.tmp"
    with open(tmp, "w") as f:
        json.dump(result, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, "/tmp/btc_volume_profile.json")
    log.info("Volume profile: POC=$%s VAH=$%s VAL=$%s (%d candles)", poc, va_high + step, va_low, len(klines))


def collect_structural():
    """Layer 2 — physics, not opinion."""
    generate_volume_profile()
    heatmap = read_json("/tmp/btc_heatmap_clusters.json")
    vol_profile = read_json("/tmp/btc_volume_profile.json")

    result = {}

    # S/R Bands — run for all 3 timeframes in parallel (was sequential: 3×30s = 90s worst case)
    sr_bands = {}
    sr_script = str(FREE_MCP / "btc_sr_bands.py")
    if Path(sr_script).exists():
        from concurrent.futures import ThreadPoolExecutor, as_completed
        def _run_sr(tf):
            try:
                proc = subprocess.run(
                    ["python3", sr_script, "--timeframe", tf, "--json"],
                    capture_output=True, text=True, timeout=30
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    return tf, json.loads(proc.stdout.strip())
                return tf, {"error": proc.stderr[:200] if proc.stderr else "No output"}
            except Exception as e:
                return tf, {"error": str(e)[:200]}
        with ThreadPoolExecutor(max_workers=3) as ex:
            futures = {ex.submit(_run_sr, tf): tf for tf in ["1h", "4h", "1d"]}
            for fut in as_completed(futures, timeout=35):
                tf, data = fut.result()
                sr_bands[tf] = data
    if sr_bands:
        result["sr_bands"] = sr_bands

    # Liquidation magnets — always emit, with fallback when upstream is missing
    if heatmap is None:
        heatmap = {}
    above = (heatmap.get("above") or {})
    below = (heatmap.get("below") or {})
    above_magnet = above.get("nearest_magnet", {})
    below_magnet = below.get("nearest_magnet", {})
    above_price = above_magnet.get("price") if above_magnet else None
    below_price = below_magnet.get("price") if below_magnet else None
    btc_price = heatmap.get("btc_price")

    sandwich = None
    regime = None
    above_price = safe_float(above_price, "liquidation above magnet price")
    below_price = safe_float(below_price, "liquidation below magnet price")
    btc_price = safe_float(btc_price, "liquidation btc price")
    if above_price is not None and below_price is not None and btc_price is not None:
        if above_price <= below_price:
            log.warning("Invalid magnet geometry: above_price=%s below_price=%s", above_price, below_price)
        else:
            width = above_price - below_price
            above_dist = above_price - btc_price
            below_dist = btc_price - below_price
            sandwich = {
                "width_usd": width,
                "above_dist": above_dist,
                "below_dist": below_dist,
            }
            if width <= 500:
                regime = "Vice Grip ⚡"
            elif above_dist < below_dist * 0.5:
                regime = "Upside Squeeze"
            elif below_dist < above_dist * 0.5:
                regime = "Downside Sweep"
            else:
                regime = "Balanced"

    result["magnets"] = {
        "above": above,
        "below": below,
        "sandwich": sandwich,
        "regime": regime,
        "btc_price": btc_price,
        "confidence": heatmap.get("confidence"),
        "timestamp": heatmap.get("timestamp"),
        "stale": not bool(heatmap),
    }

    # Volume Profile
    if vol_profile:
        result["volume_profile"] = {
            "poc": vol_profile.get("poc"),
            "vah": vol_profile.get("vah"),
            "val": vol_profile.get("val"),
            "hvns": vol_profile.get("hvns", [])[:5],
            "lvns": vol_profile.get("lvns", [])[:3],
            "bins": vol_profile.get("bins", []),
            "candles_used": vol_profile.get("candles_used"),
            "total_volume": vol_profile.get("total_volume"),
            "bin_step": vol_profile.get("bin_step"),
        }

    # Copy V7 heatmap images and write v7_captures.json
    v7_data = read_json(str(V7_IMAGES))
    v7_captures = {"timestamp": ts()}
    if v7_data:
        for side in ["long", "short"]:
            # Support both nested object format and flat path format
            side_data = v7_data.get(side)
            if isinstance(side_data, dict):
                src = side_data.get("file")
                src_path = valid_tmp_png(src)
                if not src_path:
                    v7_captures[side] = {"error": side_data.get("error", "File not found or missing")}
                else:
                    dst = ASSETS / f"v7_{side}.png"
                    shutil.copy2(src_path, dst)
                    v7_captures[side] = {"file": f"../assets/v7_{side}.png", "size_kb": round(Path(dst).stat().st_size / 1024, 1)}
            elif isinstance(side_data, str):
                # Flat path format: "long_path": "/path/to/file.png"
                src_path = valid_tmp_png(side_data)
                if src_path:
                    dst = ASSETS / f"v7_{side}.png"
                    shutil.copy2(src_path, dst)
                    v7_captures[side] = {"file": f"../assets/v7_{side}.png", "size_kb": round(Path(dst).stat().st_size / 1024, 1)}
                else:
                    v7_captures[side] = {"error": f"Rejected invalid {side} V7 image source"}
            else:
                # Also try {side}_path key (legacy format)
                src = v7_data.get(f"{side}_path")
                src_path = valid_tmp_png(src) if src else None
                if src_path:
                    dst = ASSETS / f"v7_{side}.png"
                    shutil.copy2(src_path, dst)
                    v7_captures[side] = {"file": f"../assets/v7_{side}.png", "size_kb": round(Path(dst).stat().st_size / 1024, 1)}
                else:
                    v7_captures[side] = {"error": f"Failed — no {side} data in v7_images.json (keys: {list(v7_data.keys()) if v7_data else 'none'})"}
    else:
        v7_captures["long"] = {"error": f"No v7 data source at {V7_IMAGES}"}
        v7_captures["short"] = {"error": f"No v7 data source at {V7_IMAGES}"}

    write_json("v7_captures.json", v7_captures)

    return result


# ─── Layer 3: Derivatives ─────────────────────────────────────

def collect_derivatives():
    """Layer 3 — real-time positioning. Pulls funding/OI from Binance Futures API."""
    result = {}

    # Binance Futures — funding rate (with retry)
    pi = fetch_with_retry("https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT")
    if pi:
        result["funding_rate"] = safe_float(pi.get("lastFundingRate"), "funding_rate", 0)
        result["next_funding_time"] = pi.get("nextFundingTime")
        result["mark_price"] = safe_float(pi.get("markPrice"), "mark_price", 0)
    else:
        log.warning("Funding rate fetch failed after retries")

    # Open Interest (with retry)
    oi = fetch_with_retry("https://fapi.binance.com/fapi/v1/openInterest?symbol=BTCUSDT")
    if oi:
        result["open_interest_btc"] = safe_float(oi.get("openInterest"), "open_interest", 0)
        mark = result.get("mark_price")
        if mark:
            result["open_interest_usd"] = result["open_interest_btc"] * mark
    else:
        log.warning("Open interest fetch failed after retries")

    # OI History (24h hourly) for trend + chart
    oi_hist = fetch_with_retry("https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=24")
    if oi_hist and isinstance(oi_hist, list) and len(oi_hist) >= 6:
        history = []
        for h in oi_hist:
            val = safe_float(h.get("sumOpenInterest"), "oi_hist", 0)
            usd = safe_float(h.get("sumOpenInterestValue"), "oi_hist_usd", 0)
            ts_val = h.get("timestamp")
            if val:
                history.append({"btc": round(val, 1), "usd": round(usd or 0), "ts": ts_val})
        if len(history) >= 6:
            result["oi_history"] = history
            # OI change % (first vs last)
            first_oi = history[0]["btc"]
            last_oi = history[-1]["btc"]
            if first_oi > 0:
                oi_chg = ((last_oi - first_oi) / first_oi) * 100
                result["oi_change_24h"] = round(oi_chg, 2)
            # Trend detection: compare last 6h avg vs first 6h avg
            early_avg = sum(h["btc"] for h in history[:6]) / 6
            late_avg = sum(h["btc"] for h in history[-6:]) / 6
            if late_avg > early_avg * 1.02:
                result["oi_trend"] = "accumulating"
            elif late_avg < early_avg * 0.98:
                result["oi_trend"] = "unwinding"
            else:
                result["oi_trend"] = "stable"

    # Long/Short ratio (with retry)
    ls = fetch_with_retry("https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol=BTCUSDT&period=1h&limit=1")
    if ls and isinstance(ls, list) and len(ls) > 0:
        result["long_short_ratio"] = safe_float(ls[0].get("longShortRatio"), "ls_ratio", 0)
        result["long_pct"] = safe_float(ls[0].get("longAccount"), "long_pct", 0) * 100
        result["short_pct"] = safe_float(ls[0].get("shortAccount"), "short_pct", 0) * 100

    # Taker buy/sell volume (with retry)
    ts_data = fetch_with_retry("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1h&limit=1")
    if ts_data and isinstance(ts_data, list) and len(ts_data) > 0:
        result["taker_buy_ratio"] = safe_float(ts_data[0].get("buySellRatio"), "taker_ratio", 0)

    # CVD — Cumulative Volume Delta (24h of taker buy/sell)
    taker_24h = fetch_with_retry("https://fapi.binance.com/futures/data/takerlongshortRatio?symbol=BTCUSDT&period=1h&limit=24")
    if taker_24h and isinstance(taker_24h, list) and len(taker_24h) >= 12:
        # Validate buyVol/sellVol fields exist in at least 80% of candles
        valid_candles = [c for c in taker_24h if "buyVol" in c and "sellVol" in c]
        if len(valid_candles) >= len(taker_24h) * 0.8:
            # CVD = cumulative(buyVol - sellVol) over 24h
            cvd = 0
            for candle in valid_candles:
                buy_vol = safe_float(candle.get("buyVol"), "cvd_buy", 0) or 0
                sell_vol = safe_float(candle.get("sellVol"), "cvd_sell", 0) or 0
                cvd += (buy_vol - sell_vol)
            # Only report if CVD is non-zero (sanity check)
            if abs(cvd) > 0:
                result["cvd_24h"] = round(cvd, 2)
                # CVD trend: use delta to avoid sign-multiplication artifacts with negative baselines
                recent_cvd = sum((safe_float(c.get("buyVol"), "cvd_recent_buy", 0) or 0) - (safe_float(c.get("sellVol"), "cvd_recent_sell", 0) or 0) for c in valid_candles[-4:])
                earlier_cvd = sum((safe_float(c.get("buyVol"), "cvd_early_buy", 0) or 0) - (safe_float(c.get("sellVol"), "cvd_early_sell", 0) or 0) for c in valid_candles[:4])
                delta = recent_cvd - earlier_cvd
                if earlier_cvd != 0 and abs(delta / earlier_cvd) < 0.2:
                    result["cvd_trend"] = "flat"
                elif delta > 0:
                    result["cvd_trend"] = "strengthening"
                elif delta < 0:
                    result["cvd_trend"] = "weakening"
                else:
                    result["cvd_trend"] = "flat"
            else:
                log.warning("CVD computed as 0 — data may be missing buyVol/sellVol fields")
        else:
            log.warning(f"CVD: only {len(valid_candles)}/{len(taker_24h)} candles have buyVol/sellVol — skipping")
    else:
        log.warning("CVD fetch failed or insufficient data")

    # Coinbase Premium — from market_state (fetch_market_data.py)
    market = read_json("/tmp/btc_market_state.json")
    if market:
        result["coinbase_premium"] = market.get("coinbase_premium")
        result["cb_label"] = market.get("cb_label")

    return result


# ─── Layer 4: Cycle Context ───────────────────────────────────

def classify_cycle_regime(mvrv_z):
    """Classify cycle regime from MVRV Z-score using simple thresholds."""
    if mvrv_z is None:
        return None
    if mvrv_z < 0.1:
        return "ACCUMULATION"
    elif mvrv_z <= 0.5:
        return "EARLY BULL"
    elif mvrv_z < 2.0:
        return "MID BULL"
    elif mvrv_z < 4.0:
        return "OVERHEATED"
    else:
        return "CYCLE TOP"


def compute_composite_score(mvrv_z, sopr, puell):
    """Normalize MVRV Z, SOPR, Puell into a 0-100 composite score.

    MVRV Z: range roughly -1 to 7. Map: <0 → 0, 0-2 → 20-50, 2-4 → 50-80, >4 → 80-100
    SOPR: range roughly 0.7 to 2.0. Map: <1 → 20-40, 1-1.5 → 40-70, >1.5 → 70-100
    Puell: range roughly 0.2 to 6. Map: <0.5 → 10-30, 0.5-2 → 30-60, 2-4 → 60-80, >4 → 80-100
    """
    scores = []

    if mvrv_z is not None:
        if mvrv_z < 0:
            s = max(0, 20 + mvrv_z * 20)  # Negative Z → low score
        elif mvrv_z < 2:
            s = 20 + (mvrv_z / 2) * 30  # 0-2 → 20-50
        elif mvrv_z < 4:
            s = 50 + ((mvrv_z - 2) / 2) * 30  # 2-4 → 50-80
        else:
            s = min(100, 80 + ((mvrv_z - 4) / 3) * 20)  # 4-7 → 80-100
        scores.append(max(0, min(100, s)))

    if sopr is not None:
        if sopr < 0.8:
            s = max(0, (sopr - 0.6) / 0.2 * 20)  # 0.6-0.8 → 0-20
        elif sopr < 1.0:
            s = 20 + (sopr - 0.8) / 0.2 * 20  # 0.8-1.0 → 20-40
        elif sopr < 1.5:
            s = 40 + (sopr - 1.0) / 0.5 * 30  # 1.0-1.5 → 40-70
        else:
            s = min(100, 70 + (sopr - 1.5) / 0.5 * 30)  # 1.5-2.0 → 70-100
        scores.append(max(0, min(100, s)))

    if puell is not None:
        if puell < 0.5:
            s = 10 + (puell / 0.5) * 20  # 0-0.5 → 10-30
        elif puell < 2.0:
            s = 30 + ((puell - 0.5) / 1.5) * 30  # 0.5-2 → 30-60
        elif puell < 4.0:
            s = 60 + ((puell - 2) / 2) * 20  # 2-4 → 60-80
        else:
            s = min(100, 80 + ((puell - 4) / 2) * 20)  # 4-6 → 80-100
        scores.append(max(0, min(100, s)))

    if not scores:
        return None
    return round(sum(scores) / len(scores), 1)


def collect_cycle():
    """Layer 4 — weekly/monthly, not per-session."""
    onchain = read_json("/tmp/btc_onchain_state.json")
    cycle = read_json("/tmp/btc_cycle_state.json")
    distribution = read_json("/tmp/btc_distribution.json")
    skew = read_json("/tmp/btc_skew.json")

    result = {
        "mvrv_z": None,
        "sopr": None,
        "puell_multiple": None,
        "netflow_7d": None,
        "regime": None,
        "composite_score": None,
        "cycle_phase": None,
    }

    mvrv_z = None
    sopr = None
    puell = None
    if onchain:
        mvrv_z = onchain.get("mvrv_z_score")
        sopr = onchain.get("sopr")
        puell = onchain.get("puell_multiple")
        result["mvrv_z"] = mvrv_z
        result["sopr"] = sopr
        result["puell_multiple"] = puell
        result["netflow_7d"] = onchain.get("exchange_netflow_7d_btc")
        result["regime"] = onchain.get("regime") or onchain.get("onchain_regime")

    # Compute regime from MVRV Z if not provided upstream
    if result.get("regime") is None and mvrv_z is not None:
        result["regime"] = classify_cycle_regime(mvrv_z)

    if cycle:
        # Try multiple field names for composite score
        composite = cycle.get("composite_score") or cycle.get("composite")
        result["composite_score"] = composite
        result["cycle_phase"] = cycle.get("phase") or cycle.get("composite_class")

    # Compute composite_score if not provided upstream
    if result.get("composite_score") is None:
        result["composite_score"] = compute_composite_score(mvrv_z, sopr, puell)

    if distribution:
        result["distribution"] = distribution

    if skew:
        result["options_skew"] = skew

    return result


# ─── Supplementary ────────────────────────────────────────────

def collect_supplementary():
    """TA cards — chart patterns, MA, RSI, options, gamma. Lagging but useful context."""

    # Fetch klines for MA/RSI/BB (with retry)
    klines_data = fetch_with_retry("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=60") or []

    result = {}
    if klines_data and len(klines_data) >= 20:
        try:
            closes = [float(k[4]) for k in klines_data]
            highs = [float(k[2]) for k in klines_data]
            lows = [float(k[3]) for k in klines_data]
        except (ValueError, TypeError, IndexError) as e:
            log.warning("Klines data contains non-numeric fields: %s", e)
            closes, highs, lows = [], [], []

        # MA50 / MA200
        if len(closes) >= 50:
            result["ma50"] = round(sum(closes[-50:]) / 50, 2)
        if len(closes) >= 60:
            # Use available as MA60 proxy
            result["ma60"] = round(sum(closes[-60:]) / 60, 2)

        # RSI 14
        if len(closes) >= 15:
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]
            avg_gain = sum(gains[-14:]) / 14
            avg_loss = sum(losses[-14:]) / 14
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                result["rsi_14"] = round(100 - (100 / (1 + rs)), 1)
            else:
                result["rsi_14"] = 100.0

        # Bollinger Bands
        if len(closes) >= 20:
            bb_mean = sum(closes[-20:]) / 20
            bb_std = math.sqrt(sum((c - bb_mean)**2 for c in closes[-20:]) / 20)
            result["bb_upper"] = round(bb_mean + 2 * bb_std, 2)
            result["bb_lower"] = round(bb_mean - 2 * bb_std, 2)
            result["bb_width"] = round(((bb_mean + 2*bb_std) - (bb_mean - 2*bb_std)) / bb_mean * 100, 2) if bb_mean != 0 else 0
            result["bb_mid"] = round(bb_mean, 2)

        # ATR 14
        if len(closes) >= 15:
            trs = []
            for i in range(1, len(closes)):
                tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
                trs.append(tr)
            if len(trs) >= 14:
                atr = sum(trs[-14:]) / 14
                result["atr_14"] = round(atr, 2)
                result["atr_pct"] = round(atr / closes[-1] * 100, 2) if closes[-1] != 0 else 0

        # 7d / 30d change
        if len(closes) >= 8:
            result["change_7d"] = round((closes[-1] - closes[-8]) / closes[-8] * 100, 2) if closes[-8] != 0 else 0
        if len(closes) >= 31:
            result["change_30d"] = round((closes[-1] - closes[-31]) / closes[-31] * 100, 2) if closes[-31] != 0 else 0

        result["price"] = closes[-1]

    # Options skew
    skew = read_json("/tmp/btc_skew.json")
    if skew:
        result["options_skew"] = skew

    # Gamma
    gamma = read_json("/tmp/btc_gamma.json")
    if gamma:
        result["gamma"] = gamma

    return result


# ─── AlphaEar-Derived Collectors ─────────────────────────────────

def collect_news_feed():
    """Run news aggregator (AlphaEar-derived: Google News RSS + Polymarket)."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "news_aggregator.py")],
            capture_output=True, text=True, timeout=45
        )
        return {"status": "ok", "output": result.stdout.strip()[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": ""}
    except Exception as e:
        return {"status": "error", "output": str(e)[:200]}


def collect_social_pulse():
    """Run social pulse collector (Reddit, Twitter, Xueqiu via Agent Reach)."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "social_pulse.py")],
            capture_output=True, text=True, timeout=30
        )
        return {"status": "ok", "output": result.stdout.strip()[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": ""}
    except Exception as e:
        return {"status": "error", "output": str(e)[:200]}


def collect_signal_tracker():
    """Run signal tracker (3-state evolution)."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "signal_tracker.py")],
            capture_output=True, text=True, timeout=30
        )
        return {"status": "ok", "output": result.stdout.strip()[:200]}
    except subprocess.TimeoutExpired:
        return {"status": "timeout", "output": ""}
    except Exception as e:
        return {"status": "error", "output": str(e)[:200]}


# ─── BTC Price ────────────────────────────────────────────────

def fetch_btc_price():
    """BTC spot price + 24H stats."""
    d = fetch_with_retry("https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT")
    if not d:
        log.warning("BTC price fetch failed after retries")
        return {"price": None, "error": "All retries exhausted", "timestamp": ts()}
    # Validate required fields
    required = ["lastPrice", "priceChangePercent", "highPrice", "lowPrice", "volume"]
    for field in required:
        if field not in d:
            return {"price": None, "error": f"Missing field: {field}", "timestamp": ts()}
    try:
        return {
            "price": float(d["lastPrice"]),
            "change_pct": float(d["priceChangePercent"]),
            "high": float(d["highPrice"]),
            "low": float(d["lowPrice"]),
            "volume": float(d["volume"]),
            "timestamp": ts(),
        }
    except (ValueError, TypeError) as e:
        return {"price": None, "error": f"Non-numeric field in BTC price response: {e}", "timestamp": ts()}


# ─── Regime Summary ───────────────────────────────────────────

def load_manual_override():
    """Read L-1 Manual Macro Gate. Returns override dict.
    
    Handles: missing file, auto-expiry, parse errors.
    Never raises — collect.py must not crash on a missing gate file.
    """
    default = {
        "active": False,
        "status": None,
        "reason": "",
        "set_at": None,
        "set_by": "default",
        "re_evaluate_at": None,
        "re_evaluate_trigger": "",
    }
    
    if not GATE_FILE.exists():
        return default
    
    try:
        with open(GATE_FILE) as f:
            gate = json.load(f)
        
        # Auto-expire: if re_evaluate_at is in the past, deactivate
        if gate.get("re_evaluate_at"):
            try:
                expiry_raw = gate["re_evaluate_at"]
                expiry_str = str(expiry_raw).strip()
                # Handle various ISO formats
                if expiry_str.endswith("Z"):
                    expiry_str = expiry_str[:-1] + "+00:00"
                expiry = datetime.fromisoformat(expiry_str)
                # If naive, assume UTC
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                now_utc = datetime.now(timezone.utc)
                if now_utc > expiry:
                    gate["active"] = False
                    gate["status"] = None
                    gate["reason"] = f"[AUTO-EXPIRED at {gate['re_evaluate_at']}] {gate.get('reason', '')}"
                    # Write back expired state atomically
                    tmp_gate = GATE_FILE.with_name(f".{GATE_FILE.name}.tmp")
                    with open(tmp_gate, "w") as fw:
                        json.dump(gate, fw, indent=2)
                        fw.write("\n")
                        fw.flush()
                        os.fsync(fw.fileno())
                    os.replace(tmp_gate, GATE_FILE)
                    log.info("L-1 manual gate auto-expired at %s", gate["re_evaluate_at"])
            except (ValueError, TypeError) as e:
                log.warning("L-1 manual gate: invalid expiry format — %s", e)
        
        return gate
    
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        log.warning("L-1 manual gate parse error: %s — using safe default", e)
        return default


def compute_regime_summary(gate0, macro, structural, derivatives, cycle, supplementary):
    """Synthesize all layers into one verdict card — GetClaw's #1 request."""
    result = {}

    # Gate
    result["gate"] = {
        "verdict": gate0.get("verdict", "PROCEED"),
        "emoji": {"PROCEED": "🟢", "TIGHTENED": "🟡", "PAUSE": "🟠", "ABORT": "🔴"}.get(gate0.get("verdict"), "⚪"),
        "detail": gate0.get("sources", []),
    }

    # Macro
    macro_verdict = "NEUTRAL"
    macro_detail = ""
    vix = safe_float(macro.get("vix"), "vix")
    dxy = safe_float(macro.get("dxy"), "dxy")
    if vix is not None:
        if vix > 30:
            macro_verdict = "RISK-OFF"
            macro_detail = f"VIX {vix:.1f} stress"
        elif vix < 15:
            macro_verdict = "RISK-ON"
            macro_detail = f"VIX {vix:.1f} calm"
        else:
            macro_detail = f"VIX {vix:.1f} normal"
    if dxy and dxy < 100:
        macro_detail += ", DXY weak (BTC tailwind)"
    elif dxy and dxy > 105:
        macro_detail += ", DXY strong (BTC headwind)"
    result["macro"] = {
        "verdict": macro_verdict,
        "emoji": {"RISK-ON": "🟢", "NEUTRAL": "🟡", "RISK-OFF": "🔴"}.get(macro_verdict, "🟡"),
        "detail": macro_detail.strip(", "),
    }

    # Structure
    magnets = structural.get("magnets", {})
    regime = magnets.get("regime", "Unknown")
    sr = structural.get("sr_bands", {})
    # Count valid timeframes
    valid_tf = sum(1 for tf in ["1h","4h","1d"] if tf in sr and "error" not in sr.get(tf, {}))
    struct_verdict = "HOLDING" if regime in ("Balanced", None) else regime
    struct_detail = f"{valid_tf}/3 timeframes active"
    if magnets.get("sandwich"):
        sw = magnets["sandwich"]
        struct_detail += f", sandwich ${sw.get('width_usd', '?')}"
    result["structure"] = {
        "verdict": struct_verdict,
        "emoji": "🟢" if struct_verdict == "Upside Squeeze" else "🔴" if struct_verdict == "Downside Sweep" else "🟡",
        "detail": struct_detail,
    }

    # Derivatives
    fr = derivatives.get("funding_rate")
    ls = derivatives.get("long_short_ratio")
    deriv_verdict = "NEUTRAL"  # FIX: neutral FR is NOT bullish — defaults to 🟡
    deriv_detail = ""
    if fr is not None:
        fr_pct = fr * 100
        if fr < -0.0003:
            deriv_verdict = "BULLISH"
            deriv_detail = f"FR {fr_pct:.4f}% shorts paying"
        elif fr > 0.0003:
            deriv_verdict = "OVERHEATED"
            deriv_detail = f"FR {fr_pct:.4f}% longs crowded"
        else:
            deriv_detail = f"FR {fr_pct:.4f}% neutral"
    if ls:
        deriv_detail += f", L/S {ls:.2f}"
    cvd = derivatives.get("cvd_24h")
    if cvd is not None:
        deriv_detail += f", CVD {cvd:+.0f}"
    result["derivatives"] = {
        "verdict": deriv_verdict,
        "emoji": "🟢" if deriv_verdict == "BULLISH" else "🔴" if deriv_verdict == "OVERHEATED" else "🟡",
        "detail": deriv_detail.strip(", "),
    }

    # Cycle
    mvrv = cycle.get("mvrv_z")
    cycle_verdict = "MID"
    cycle_detail = ""
    if mvrv is not None:
        if mvrv < 0:
            cycle_verdict = "BUY ZONE"
            cycle_detail = f"MVRV-Z {mvrv:.2f} historic buy"
        elif mvrv < 1:
            cycle_verdict = "UNDERVALUED"
            cycle_detail = f"MVRV-Z {mvrv:.2f} undervalued"
        elif mvrv > 3:
            cycle_verdict = "SELL ZONE"
            cycle_detail = f"MVRV-Z {mvrv:.2f} cycle top"
        else:
            cycle_detail = f"MVRV-Z {mvrv:.2f} mid-cycle"
    netflow = cycle.get("netflow_7d")
    if netflow is not None:
        cycle_detail += f", netflow {netflow:+,.0f} BTC"
    result["cycle"] = {
        "verdict": cycle_verdict,
        "emoji": "🟢" if cycle_verdict in ("BUY ZONE", "UNDERVALUED") else "🔴" if cycle_verdict == "SELL ZONE" else "🟡",
        "detail": cycle_detail.strip(", "),
    }

    # TA warning (MA50 distance)
    ta_warning = None
    price = supplementary.get("price")
    ma50 = supplementary.get("ma50")
    if price and ma50 and ma50 > 0:
        ma_dist = (price - ma50) / ma50 * 100
        if abs(ma_dist) > 5:
            direction = "above" if ma_dist > 0 else "below"
            ta_warning = f"Price {abs(ma_dist):.1f}% {direction} MA50 — medium-term structure {'bullish' if ma_dist > 0 else 'bearish'}"

    # ── SYNTHESIS ──
    # L-1 Manual Macro Gate — human geopolitical/macro events above all automation
    manual = load_manual_override()
    if manual.get("active") and manual.get("status") in ("PAUSE", "ABORT"):
        synthesis = f"L-1 {manual['status']} — MANUAL OVERRIDE"
        synthesis_detail = f"Manual macro gate active: {manual.get('reason', '')}"
        if manual.get("re_evaluate_at"):
            synthesis_detail += f" | Re-evaluate: {manual.get('re_evaluate_trigger', manual['re_evaluate_at'])}"
        if ta_warning:
            synthesis_detail += f" | TA: {ta_warning}"
        result["synthesis"] = {
            "verdict": synthesis,
            "detail": synthesis_detail,
            "bull_count": 0,
            "bear_count": 0,
            "ta_warning": ta_warning,
            "manual_override": {
                "active": True,
                "status": manual["status"],
                "reason": manual["reason"],
                "set_at": manual.get("set_at"),
                "re_evaluate_at": manual.get("re_evaluate_at"),
                "re_evaluate_trigger": manual.get("re_evaluate_trigger"),
            },
        }
        result["manual_gate"] = manual
        log.info("L-1 manual gate ACTIVE: %s — %s", manual["status"], manual["reason"])
        return result

    # Normal automated synthesis
    # Count bullish vs bearish signals with TIMESCALE-WEIGHTED scoring
    # FIX: Cycle layer (months-scale) gets 0.5x weight — cannot outvote live structural events
    # FIX: Neutral derivatives (🟡) contributes 0 to both counts — no longer inflates bull
    bull = 0.0
    bear = 0.0
    bull_raw = 0  # unweighted count for display
    bear_raw = 0
    for layer_name, layer in [("macro", result["macro"]), ("structure", result["structure"]),
                                ("derivatives", result["derivatives"]), ("cycle", result["cycle"])]:
        if layer["emoji"] == "🟢":
            weight = 0.5 if layer_name == "cycle" else 1.0
            bull += weight
            bull_raw += 1
        elif layer["emoji"] == "🔴":
            weight = 0.5 if layer_name == "cycle" else 1.0
            bear += weight
            bear_raw += 1
    gate_v = gate0.get("verdict", "PROCEED")

    # ── Monitor Ceiling Enforcement ──
    # Active structural events (Downside Sweep, Upside Squeeze) are live, time-sensitive.
    # They MUST gate the synthesis ceiling — bullish verdicts cannot coexist with an
    # active downside event, just as bearish verdicts cannot coexist with an active
    # upside squeeze. Monitors tell the truth; synthesis now listens.
    struct_verdict = result["structure"]["verdict"]
    monitor_active = struct_verdict in ("Downside Sweep", "Upside Squeeze")

    if gate_v == "ABORT":
        synthesis = "DO NOT TRADE"
        synthesis_detail = "Gate 0 ABORT active. Emergency monitoring only."
    elif gate_v == "PAUSE":
        synthesis = "STAND ASIDE"
        synthesis_detail = "Gate 0 PAUSE active. No new positions."
    elif gate_v == "TIGHTENED" and bull > bear + 0.5:
        synthesis = "CAUTIOUS BULL"
        synthesis_detail = f"Tightened rules active. {bull_raw} bullish / {bear_raw} bearish signals."
        if monitor_active and struct_verdict == "Downside Sweep":
            synthesis = "NEUTRAL"
            synthesis_detail += f" ⚠️ Monitor active ({struct_verdict}) — verdict capped at NEUTRAL."
    elif gate_v == "TIGHTENED" and bear > bull + 0.5:
        synthesis = "CAUTIOUS BEAR"
        synthesis_detail = f"Tightened rules active. {bear_raw} bearish / {bull_raw} bullish signals."
        if monitor_active and struct_verdict == "Upside Squeeze":
            synthesis = "NEUTRAL"
            synthesis_detail += f" ⚠️ Monitor active ({struct_verdict}) — verdict capped at NEUTRAL."
    elif gate_v == "TIGHTENED":
        synthesis = "CAUTIOUS NEUTRAL"
        synthesis_detail = f"Tightened rules active. {bull_raw} bullish / {bear_raw} bearish signals."
    elif bull > bear + 1:
        synthesis = "BULLISH"
        synthesis_detail = f"{bull_raw} bullish signals. Full rules."
        if monitor_active and struct_verdict == "Downside Sweep":
            synthesis = "NEUTRAL"
            synthesis_detail += f" ⚠️ Monitor active ({struct_verdict}) — verdict capped at NEUTRAL."
    elif bear > bull + 1:
        synthesis = "BEARISH"
        synthesis_detail = f"{bear_raw} bearish signals. Full rules."
        if monitor_active and struct_verdict == "Upside Squeeze":
            synthesis = "NEUTRAL"
            synthesis_detail += f" ⚠️ Monitor active ({struct_verdict}) — verdict capped at NEUTRAL."
    else:
        synthesis = "MIXED"
        synthesis_detail = f"{bull:.1f} bull / {bear:.1f} bear signals. Wait for clarity."

    if ta_warning:
        synthesis_detail += f" | TA: {ta_warning}"

    result["synthesis"] = {
        "verdict": synthesis,
        "detail": synthesis_detail,
        "bull_count": round(bull, 1),
        "bear_count": round(bear, 1),
        "ta_warning": ta_warning,
    }

    return result


# ─── VAL Absorption Detection ─────────────────────────────────

def detect_val_absorption(btc, structural, derivatives):
    """Detect VAL absorption setup: price near/below VAL + declining volume + CVD holding.

    Returns a signal dict or None if conditions not met.
    """
    price = safe_float(btc.get("price"), "val_abs_price", 0)
    if not price:
        return None

    vp = structural.get("volume_profile", {})
    val = safe_float(vp.get("val"), "val_abs_val", 0)
    vah = safe_float(vp.get("vah"), "val_abs_vah", 0)
    if not val:
        return None

    # Only activate when price is within 3% of VAL or below it
    threshold = val * 1.03
    if price > threshold:
        return None  # Too far above VAL — no signal

    # Fetch last 8 hourly candles for volume comparison
    klines = fetch_with_retry(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=8"
    )
    if not klines or len(klines) < 8:
        log.warning("VAL absorption: insufficient hourly klines (%d)", len(klines) if klines else 0)
        return None

    volumes = [safe_float(k[5], "val_abs_vol", 0) for k in klines]
    early_vol = sum(volumes[:4])
    late_vol = sum(volumes[4:])
    vol_declining = late_vol < early_vol * 0.85  # 15% threshold
    vol_expanding = late_vol > early_vol * 1.15

    # CVD from derivatives
    cvd = derivatives.get("cvd_24h")
    cvd_trend = derivatives.get("cvd_trend", "flat")
    cvd_holding = cvd is not None and cvd >= 0  # CVD non-negative = buyers still present
    cvd_falling = cvd is not None and cvd < 0 and cvd_trend == "weakening"

    # Distance from VAL
    dist_pct = ((price - val) / val) * 100
    position = "below_val" if price <= val else "approaching_val"

    # Build signal
    signal = {
        "timestamp": ts(),
        "btc_price": price,
        "val": val,
        "vah": vah,
        "distance_pct": round(dist_pct, 2),
        "position": position,
        "volume_declining": vol_declining,
        "volume_expanding": vol_expanding,
        "cvd_holding": cvd_holding,
        "cvd_value": cvd,
        "cvd_trend": cvd_trend,
        "target": vah,
        "early_vol_4h": round(early_vol, 1),
        "late_vol_4h": round(late_vol, 1),
    }

    # Determine signal type
    if price <= val or (price <= threshold and vol_declining):
        if vol_declining and cvd_holding:
            signal["signal"] = "VAL_ABSORPTION"
            signal["action"] = "Watch for reclaim inside VA → Long entry"
            signal["stop"] = "Below swing low"
            signal["stop_loss"] = round(val * 0.99, 2)  # 1% below VAL (numeric for outcome tracker)
            signal["confidence"] = "HIGH" if cvd_trend == "strengthening" else "MEDIUM"
        elif vol_expanding and cvd_falling:
            signal["signal"] = "VAL_BREAK"
            signal["action"] = "Real distribution — structure failed"
            signal["confidence"] = "HIGH"
        else:
            signal["signal"] = "VAL_TEST"
            signal["action"] = "Price testing VAL — waiting for volume/CVD confirmation"
            signal["confidence"] = "LOW"
    else:
        # Approaching but no volume signal yet
        signal["signal"] = "VAL_APPROACH"
        signal["action"] = "Price nearing VAL — monitoring volume and CVD"
        signal["confidence"] = "LOW"

    return signal


# ─── Breakout-Retest Detection ─────────────────────────────────

def detect_breakout_retest(btc, structural, derivatives):
    """Detect breakout-retest setups: resistance break + volume confirmation + retest monitoring.

    Returns a signal dict or None if conditions not met.
    """
    from datetime import datetime, timedelta, timezone

    price = safe_float(btc.get("price"), "brk_price", 0)
    if not price:
        return None

    # Load persistent retest zone state
    state_file = "/tmp/btc_retest_zones.json"
    try:
        with open(state_file, 'r') as f:
            zones = json.load(f)
    except Exception:
        zones = {"active": [], "history": []}

    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")

    # Fetch 15min klines for breakout detection
    klines_15m = fetch_with_retry(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=20"
    )
    if not klines_15m or len(klines_15m) < 10:
        log.warning("Breakout-retest: insufficient 15m klines (%d)", len(klines_15m) if klines_15m else 0)
        return None

    # Get 4H resistance levels from Layer 2
    sr_bands = structural.get("sr_bands", {})
    resistances_4h = []
    if "4h" in sr_bands and "resistances" in sr_bands["4h"]:
        for r in sr_bands["4h"]["resistances"]:
            level = safe_float(r.get("center"), "resistance_4h", 0)
            if level > 0:
                resistances_4h.append(level)

    # Get liquidation magnets above current price
    magnets = structural.get("magnets", {})
    above_magnet = magnets.get("above", {})
    nearest = above_magnet.get("nearest_magnet", {})
    magnet_level = safe_float(nearest.get("price"), "magnet_above", 0)

    # Check for new breakouts above 4H resistance
    new_breakout = None
    if resistances_4h:
        for resistance in sorted(resistances_4h):
            # Check if price just broke above this level in last few 15m candles
            recent_closes = [safe_float(k[4], "close", 0) for k in klines_15m[-6:]]
            if any(c > resistance for c in recent_closes) and price > resistance:
                # Potential breakout — check volume confirmation
                # Get taker ratio and CVD from derivatives
                taker_ratio = safe_float(derivatives.get("taker_buy_ratio"), "taker", 1.0)
                cvd = safe_float(derivatives.get("cvd_24h"), "cvd", 0)

                # Volume confirmation: Taker > 1.2 AND CVD > 0
                vol_confirmed = taker_ratio > 1.2 and cvd > 0

                # Edge case 1: Magnet cluster above within 0.5%
                if magnet_level and magnet_level < resistance * 1.005:
                    log.info(f"Breakout-retest: magnet cluster at ${magnet_level:.0f} above resistance ${resistance:.0f} — may be sweep")
                    continue

                # Edge case 2: Minimum absolute volume during thin hours (00:00-06:00 UTC)
                hour = now.hour
                if hour < 6:
                    # Check if recent 15m volume is above minimum threshold
                    recent_vols = [safe_float(k[5], "vol", 0) for k in klines_15m[-4:]]
                    avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
                    if avg_vol < 50:  # Minimum 50 BTC per 15m candle
                        log.info(f"Breakout-retest: thin hours ({hour}:00 UTC), low volume ({avg_vol:.1f} BTC) — skipping")
                        continue

                # Edge case 3: Space above (> 0.5x ATR)
                atr_1d = safe_float(sr_bands.get("1d", {}).get("atr"), "atr_1d", 0)
                if atr_1d and magnet_level:
                    space_above = magnet_level - resistance
                    if space_above < 0.5 * atr_1d:
                        log.info(f"Breakout-retest: limited space above (${space_above:.0f} < 0.5x ATR ${atr_1d*0.5:.0f})")
                        continue

                if vol_confirmed:
                    # New breakout detected
                    zone = {
                        "level": resistance,
                        "broken_at": now_str,
                        "expires_at": (now + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M UTC"),
                        "status": "waiting_retest",
                        "retested": False,
                        "bounce_confirmed": False,
                    }
                    zones["active"].append(zone)
                    new_breakout = {
                        "signal": "BREAKOUT_DETECTED",
                        "level": resistance,
                        "price": price,
                        "timestamp": now_str,
                        "volume_confirmed": True,
                        "taker_ratio": taker_ratio,
                        "cvd": cvd,
                    }
                    break  # Only track first breakout

    # Monitor existing retest zones
    active_signal = None
    for zone in zones["active"]:
        try:
            expires = datetime.strptime(zone["expires_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            zone["status"] = "expired"
            continue
        if now > expires:
            # Zone expired
            zone["status"] = "expired"
            continue

        level = zone.get("level", 0)
        if not level or level <= 0:
            zone["status"] = "expired"
            continue

        # Check if price closed back through the level (kill zone)
        if price < level * 0.995:  # 0.5% below level
            zone["status"] = "failed"
            continue

        # Check for retest (price within 0.3% of level)
        if not zone["retested"] and abs(price - level) / level < 0.003:
            zone["retested"] = True
            zone["retest_at"] = now_str
            active_signal = {
                "signal": "RETEST_ACTIVE",
                "level": level,
                "price": price,
                "timestamp": now_str,
                "status": "retest_in_progress",
            }
            break

        # Check for bounce confirmation (price back above level after retest)
        if zone["retested"] and not zone["bounce_confirmed"] and price > level * 1.003:
            # Fetch hourly candle to confirm close above level
            klines_1h = fetch_with_retry(
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=2"
            )
            if klines_1h and len(klines_1h) >= 1:
                last_close = safe_float(klines_1h[-1][4], "close_1h", 0)
                if last_close > level:
                    zone["bounce_confirmed"] = True
                    zone["bounce_at"] = now_str
                    zone["status"] = "entry_signal"
                    # Compute target: next resistance above, or VAH, or 1% above level
                    next_target = None
                    for r in sorted(resistances_4h):
                        if r > level * 1.005:
                            next_target = r
                            break
                    if not next_target:
                        vp_vah = structural.get("volume_profile", {}).get("vah")
                        if vp_vah and vp_vah > level:
                            next_target = vp_vah
                    if not next_target:
                        next_target = level * 1.02  # fallback: 2% above level
                    active_signal = {
                        "signal": "ENTRY_SIGNAL",
                        "direction": "LONG",
                        "level": level,
                        "price": price,
                        "timestamp": now_str,
                        "status": "bounce_confirmed",
                        "action": "Long entry above broken resistance",
                        "stop_loss": level * 0.99,  # 1% below level
                        "target": round(next_target, 2),
                        "confidence": "HIGH" if price > level * 1.01 else "MEDIUM",
                    }
                    break

    # Clean up expired/failed zones (keep last 10 in history)
    expired_failed = [z for z in zones["active"] + zones.get("history", [])
                      if z["status"] in ["expired", "failed"]]
    zones["active"] = [z for z in zones["active"] if z["status"] not in ["expired", "failed"]]
    zones["history"] = expired_failed[-10:]

    # Save state atomically
    try:
        tmp_state = state_file + ".tmp"
        with open(tmp_state, 'w') as f:
            json.dump(zones, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_state, state_file)
    except Exception as e:
        log.warning(f"Failed to save retest zone state: {e}")

    # Return signal: new breakout > active retest > monitoring status
    if new_breakout:
        return new_breakout
    elif active_signal:
        return active_signal
    elif zones["active"]:
        # Monitoring mode — show active zones
        return {
            "signal": "MONITORING",
            "active_zones": len(zones["active"]),
            "levels": [z["level"] for z in zones["active"]],
            "timestamp": now_str,
        }
    else:
        return None


# ─── Breakdown-Retest Detection ────────────────────────────────

def detect_breakdown_retest(btc, structural, derivatives):
    """Detect breakdown-retest setups: support break + volume confirmation + retest monitoring.

    Bearish mirror of breakout-retest:
    - Price breaks below 4H support
    - Volume spike (Taker < 0.8) + CVD negative = real sellers
    - Retest from below (old support now resistance)
    - CVD stays negative on retest = rejection confirmed → SHORT entry
    - If CVD goes positive on retest → skip (VAL Absorption territory)

    Returns a signal dict or None if conditions not met.
    """
    from datetime import datetime, timedelta, timezone

    price = safe_float(btc.get("price"), "brk_price", 0)
    if not price:
        return None

    # Load persistent breakdown zone state
    state_file = "/tmp/btc_breakdown_zones.json"
    try:
        with open(state_file, 'r') as f:
            zones = json.load(f)
    except Exception:
        zones = {"active": [], "history": []}

    now = datetime.now(timezone.utc)
    now_str = now.strftime("%Y-%m-%d %H:%M UTC")

    # Fetch 15min klines for breakdown detection
    klines_15m = fetch_with_retry(
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=15m&limit=20"
    )
    if not klines_15m or len(klines_15m) < 10:
        log.warning("Breakdown-retest: insufficient 15m klines (%d)", len(klines_15m) if klines_15m else 0)
        return None

    # Get 4H support levels from Layer 2
    sr_bands = structural.get("sr_bands", {})
    supports_4h = []
    if "4h" in sr_bands and "supports" in sr_bands["4h"]:
        for s in sr_bands["4h"]["supports"]:
            level = safe_float(s.get("center"), "support_4h", 0)
            if level > 0:
                supports_4h.append(level)

    # Get liquidation magnets below current price
    magnets = structural.get("magnets", {})
    below_magnet = magnets.get("below", {})
    nearest = below_magnet.get("nearest_magnet", {})
    magnet_below = safe_float(nearest.get("price"), "magnet_below", 0)

    # Check for new breakdowns below 4H support
    new_breakdown = None
    if supports_4h:
        for support in sorted(supports_4h, reverse=True):  # Check nearest supports first
            # Check if price just broke below this level in last few 15m candles
            recent_closes = [safe_float(k[4], "close", 0) for k in klines_15m[-6:]]
            if any(c < support for c in recent_closes) and price < support:
                # Potential breakdown — check volume confirmation
                taker_ratio = safe_float(derivatives.get("taker_buy_ratio"), "taker", 1.0)
                cvd = safe_float(derivatives.get("cvd_24h"), "cvd", 0)

                # Volume confirmation: Taker < 0.8 AND CVD < 0 (sellers dominating)
                vol_confirmed = taker_ratio < 0.8 and cvd < 0

                # Edge case 1: Magnet cluster below within 0.5% — may cause sweep bounce
                if magnet_below and magnet_below > support * 0.995:
                    log.info(f"Breakdown-retest: magnet cluster at ${magnet_below:.0f} below support ${support:.0f} — likely sweep")
                    continue

                # Edge case 2: Minimum absolute volume during thin hours (00:00-06:00 UTC)
                hour = now.hour
                if hour < 6:
                    recent_vols = [safe_float(k[5], "vol", 0) for k in klines_15m[-4:]]
                    avg_vol = sum(recent_vols) / len(recent_vols) if recent_vols else 0
                    if avg_vol < 50:  # Minimum 50 BTC per 15m candle
                        log.info(f"Breakdown-retest: thin hours ({hour}:00 UTC), low volume ({avg_vol:.1f} BTC) — skipping")
                        continue

                # Edge case 3: Space below (> 0.5x ATR to next support or magnet)
                atr_1d = safe_float(sr_bands.get("1d", {}).get("atr"), "atr_1d", 0)
                next_support = None
                for s in sorted(supports_4h):
                    if s < support:
                        next_support = s
                        break
                if next_support and atr_1d:
                    space_below = support - next_support
                    if space_below < 0.5 * atr_1d:
                        log.info(f"Breakdown-retest: limited space below (${space_below:.0f} < 0.5x ATR ${atr_1d*0.5:.0f})")
                        continue

                # Edge case 4: Skip supports very close to VAL (VAL Absorption handles that zone)
                val_price = safe_float(structural.get("volume_profile", {}).get("val"), "val", 0)
                if val_price and abs(support - val_price) / val_price < 0.01:  # Within 1% of VAL
                    log.info(f"Breakdown-retest: support ${support:.0f} too close to VAL ${val_price:.0f} — VAL Absorption handles this zone")
                    continue

                if vol_confirmed:
                    # New breakdown detected
                    zone = {
                        "level": support,
                        "broken_at": now_str,
                        "expires_at": (now + timedelta(hours=48)).strftime("%Y-%m-%d %H:%M UTC"),
                        "status": "waiting_retest",
                        "retested": False,
                        "rejection_confirmed": False,
                    }
                    zones["active"].append(zone)
                    new_breakdown = {
                        "signal": "BREAKDOWN_DETECTED",
                        "level": support,
                        "price": price,
                        "timestamp": now_str,
                        "volume_confirmed": True,
                        "taker_ratio": taker_ratio,
                        "cvd": cvd,
                    }
                    break  # Only track first breakdown

    # Monitor existing retest zones
    active_signal = None
    for zone in zones["active"]:
        try:
            expires = datetime.strptime(zone["expires_at"], "%Y-%m-%d %H:%M UTC").replace(tzinfo=timezone.utc)
        except (ValueError, KeyError):
            zone["status"] = "expired"
            continue
        if now > expires:
            zone["status"] = "expired"
            continue

        level = zone.get("level", 0)
        if not level or level <= 0:
            zone["status"] = "expired"
            continue

        # Check if price closed back above the level (kill zone — support reclaimed)
        if price > level * 1.005:  # 0.5% above level
            zone["status"] = "failed"
            continue

        # Check for retest (price within 0.3% of level from below)
        if not zone["retested"] and abs(price - level) / level < 0.003 and price <= level:
            zone["retested"] = True
            zone["retest_at"] = now_str
            active_signal = {
                "signal": "RETEST_ACTIVE",
                "level": level,
                "price": price,
                "timestamp": now_str,
                "status": "retest_in_progress",
            }
            break

        # Check for rejection confirmation (price stays below level after retest)
        if zone["retested"] and not zone["rejection_confirmed"] and price < level * 0.997:
            # Fetch hourly candle to confirm close below level
            klines_1h = fetch_with_retry(
                "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=2"
            )
            if klines_1h and len(klines_1h) >= 1:
                last_close = safe_float(klines_1h[-1][4], "close_1h", 0)
                if last_close < level:
                    # KEY FILTER: CVD must stay negative — if CVD went positive, this is VAL Absorption territory
                    cvd_now = safe_float(derivatives.get("cvd_24h"), "cvd_now", 0)
                    if cvd_now >= 0:
                        log.info(f"Breakdown-retest: CVD turned positive ({cvd_now:.0f}) — not a short, skipping")
                        zone["status"] = "cvd_flip_skip"
                        continue

                    zone["rejection_confirmed"] = True
                    zone["rejection_at"] = now_str
                    zone["status"] = "entry_signal"

                    # Calculate stop loss (1% above level)
                    stop_loss = level * 1.01
                    # Calculate target: next support below
                    next_target = None
                    for s in sorted(supports_4h):
                        if s < level * 0.99:
                            next_target = s
                            break
                    if not next_target and magnet_below:
                        next_target = magnet_below

                    active_signal = {
                        "signal": "ENTRY_SIGNAL",
                        "direction": "SHORT",
                        "level": level,
                        "price": price,
                        "timestamp": now_str,
                        "status": "rejection_confirmed",
                        "action": "Short entry below broken support",
                        "stop_loss": round(stop_loss, 2),
                        "target": round(next_target, 2) if next_target else None,
                        "confidence": "HIGH" if price < level * 0.99 else "MEDIUM",
                    }
                    break

    # Clean up expired/failed zones (keep last 10 in history)
    expired_failed = [z for z in zones["active"] + zones.get("history", [])
                      if z["status"] in ["expired", "failed", "cvd_flip_skip"]]
    zones["active"] = [z for z in zones["active"] if z["status"] not in ["expired", "failed", "cvd_flip_skip"]]
    zones["history"] = expired_failed[-10:]

    # Save state atomically
    try:
        tmp_state = state_file + ".tmp"
        with open(tmp_state, 'w') as f:
            json.dump(zones, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_state, state_file)
    except Exception as e:
        log.warning(f"Failed to save breakdown zone state: {e}")

    # Return signal: new breakdown > active retest > monitoring status
    if new_breakdown:
        return new_breakdown
    elif active_signal:
        return active_signal
    elif zones["active"]:
        return {
            "signal": "MONITORING",
            "active_zones": len(zones["active"]),
            "levels": [z["level"] for z in zones["active"]],
            "timestamp": now_str,
        }
    else:
        return None


# ─── Main ─────────────────────────────────────────────────────

def collect_sentiment():
    """Collect sentiment/positioning metrics: Fear & Greed, Coinbase Premium, Whale, Session, Stablecoins."""
    realtime = read_json("/tmp/btc_realtime_state.json")
    market = read_json("/tmp/btc_market_state.json")
    risk_alerts = read_json("/tmp/btc_risk_alerts.json")
    session = read_json("/tmp/btc_session_state.json")
    
    result = {}
    
    # Fear & Greed
    if realtime:
        fng = realtime.get("fear_and_greed")
        fng_class = realtime.get("fng_classification", "")
        if fng is not None:
            result["fear_greed"] = {"value": fng, "classification": fng_class}
    
    # Coinbase Premium
    if market:
        cp = market.get("coinbase_premium")
        if cp is not None:
            result["coinbase_premium"] = round(cp, 4)
    
    # Whale Ratio
    if risk_alerts:
        whale = risk_alerts.get("whale") or {}
        if isinstance(whale, dict):
            result["whale"] = {
                "ratio": whale.get("ratio"),
                "trend": whale.get("trend"),
                "signal": whale.get("signal"),
                "direction": whale.get("direction"),
            }
    
    # Session
    if session:
        result["session"] = {
            "current": session.get("current_session", "—"),
            "ny_open": session.get("ny_open_myt", "—"),
            "golden_window": session.get("golden_window", "—"),
            "trap_zone": session.get("trap_zone", "—"),
            "mode": session.get("mode", "—"),
            "warnings": session.get("warnings", []),
        }
    
    # Stablecoins (ccxt Binance)
    try:
        import ccxt
        exchange = ccxt.binance()
        stable = {}
        try:
            usdc = exchange.fetch_ticker("USDC/USDT")
            stable["usdc_price"] = usdc["last"]
            stable["usdc_deviation"] = round((usdc["last"] - 1) * 100, 4)
        except Exception:
            stable["usdc_price"] = None
            stable["usdc_deviation"] = None
        try:
            dai = exchange.fetch_ticker("DAI/USDT")
            stable["dai_price"] = dai["last"]
            stable["dai_deviation"] = round((dai["last"] - 1) * 100, 4)
        except Exception:
            stable["dai_price"] = None
            stable["dai_deviation"] = None
        
        max_dev = max(abs(stable.get("usdc_deviation") or 0), abs(stable.get("dai_deviation") or 0))
        if max_dev < 0.5:
            stable["status"] = "healthy"
        elif max_dev < 2.0:
            stable["status"] = "elevated"
        else:
            stable["status"] = "depeg_risk"
        result["stablecoins"] = stable
    except Exception:
        result["stablecoins"] = {"status": "unavailable"}
    
    result["_collected"] = ts()
    return result


def collect_positioning():
    """Collect institutional positioning: CME COT + Deribit Options Full."""
    cot = read_json("/tmp/btc_cot.json")
    options = read_json("/tmp/btc_options_full.json")
    
    result = {}
    
    if cot:
        result["cot"] = {
            "as_of": cot.get("as_of") or cot.get("date"),
            "open_interest": cot.get("open_interest"),
            "leveraged_funds": {
                "long": cot.get("noncomm_long") or cot.get("leveraged_funds_long") or cot.get("lev_long"),
                "short": cot.get("noncomm_short") or cot.get("leveraged_funds_short") or cot.get("lev_short"),
                "net": cot.get("noncomm_net") or cot.get("leveraged_funds_net") or cot.get("lev_net"),
            },
            "commercials": {
                "long": cot.get("comm_long") or cot.get("commercials_long"),
                "short": cot.get("comm_short") or cot.get("commercials_short"),
                "net": cot.get("comm_net") or cot.get("commercials_net"),
            },
            "weekly_change": cot.get("weekly_change") or cot.get("change_date"),
            "signal": cot.get("signal"),
        }
    
    if options:
        result["options"] = {
            "total_oi": options.get("total_oi"),
            "call_oi": options.get("call_oi"),
            "put_oi": options.get("put_oi"),
            "volume_24h": options.get("volume_24h"),
            "call_volume": options.get("call_volume_24h") or options.get("call_volume"),
            "put_volume": options.get("put_volume_24h") or options.get("put_volume"),
            "pcr_oi": options.get("pcr_oi") or options.get("pcr"),
            "pcr_volume": options.get("pcr_volume") or options.get("pcr_vol"),
            "notional_value": options.get("notional_value"),
            "signal": options.get("signal"),
        }
    
    result["_collected"] = ts()
    return result


def collect_patterns():
    """Collect chart patterns, 3-candle confluence, and pattern outcome feed."""
    HOME = Path.home()
    result = {}
    
    # Chart Patterns — from btc-chart-patterns project
    try:
        chart_path = HOME / "btc-chart-patterns/data/alerts.jsonl"
        if chart_path.exists():
            with open(chart_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines:
                import json as _json
                entry = _json.loads(lines[-1])
                levels = entry.get("key_levels", {})
                result["chart_pattern"] = {
                    "pattern": entry.get("pattern_name", "—"),
                    "state": entry.get("state", "—"),
                    "direction": entry.get("direction", "—"),
                    "confidence": entry.get("confidence", 0),
                    "timeframe": entry.get("tf", "—"),
                    "target": levels.get("target"),
                    "stop": levels.get("stop"),
                    "description": entry.get("description", ""),
                }
    except Exception:
        pass
    
    # 3-Candle Pattern — from btc-3candle-confluence project
    try:
        candle_path = HOME / "btc-3candle-confluence/data/reads.jsonl"
        if candle_path.exists():
            with open(candle_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines:
                import json as _json
                entry = _json.loads(lines[-1])
                result["three_candle"] = {
                    "pattern": entry.get("pattern", "—"),
                    "direction": entry.get("direction", "—"),
                    "price": entry.get("price"),
                    "confidence": entry.get("confidence"),
                    "description": entry.get("description", ""),
                }
    except Exception:
        pass
    
    # RSI Reversal Signal — compute from existing supplementary data
    try:
        supp = read_json(str(DATA / "supplementary.json"))
        if supp and supp.get("rsi_14") is not None:
            rsi = supp["rsi_14"]
            price = supp.get("price")
            reversal = None
            if rsi > 70:
                reversal = {"signal": "overbought", "rsi": rsi, "action": "Watch for reversal down"}
            elif rsi < 30:
                reversal = {"signal": "oversold", "rsi": rsi, "action": "Watch for reversal up"}
            else:
                reversal = {"signal": "neutral", "rsi": rsi, "action": "No reversal signal"}
            if price:
                reversal["price"] = price
            result["rsi_reversal"] = reversal
    except Exception:
        pass
    
    result["_collected"] = ts()
    return result


def collect_crash_precursor():
    """D2 — Real-time crash precursor signals from btc-crash-monitor."""
    HOME = Path.home()
    result = {"composite": 0, "alert_fired": False, "signals": {}, "status": "NORMAL"}
    try:
        crash_path = HOME / "btc-crash-monitor/data/signal_log.jsonl"
        if not crash_path.exists():
            return result
        with open(crash_path) as f:
            lines = [l.strip() for l in f if l.strip()]
        if not lines:
            return result
        entry = json.loads(lines[-1])
        composite = entry.get("composite", 0)
        scores = entry.get("scores", {})
        result["composite"] = composite
        result["alert_fired"] = entry.get("alert_fired", False)
        result["signals"] = scores
        result["timestamp"] = entry.get("timestamp", "")
        if composite >= 4:
            result["status"] = "DANGER"
        elif composite >= 2:
            result["status"] = "ELEVATED"
        elif composite >= 1:
            result["status"] = "CAUTION"
        else:
            result["status"] = "NORMAL"
        active = [k.replace("_", " ").title() for k, v in scores.items() if v > 0]
        result["active_signals"] = active
    except Exception:
        pass
    result["_collected"] = ts()
    return result


def compute_black_swan():
    """Compute Black Swan Sentinel score (mirrors generate_v2.py logic)."""
    import json as _json
    
    onchain = read_json("/tmp/btc_onchain_state.json") or {}
    realtime = read_json("/tmp/btc_realtime_state.json") or {}
    macro_raw = read_json("/tmp/btc_macro_state.json") or {}
    risk = read_json("/tmp/btc_risk_state.json") or {}
    risk_alerts = read_json("/tmp/btc_risk_alerts.json") or {}
    
    # Crash monitor
    crash = None
    try:
        crash_path = HOME / "btc-crash-monitor/data/signal_log.jsonl"
        if crash_path.exists():
            with open(crash_path) as f:
                lines = [l.strip() for l in f if l.strip()]
            if lines:
                crash = _json.loads(lines[-1])
    except Exception:
        pass
    
    # Stablecoins for black swan scoring
    stable = {}
    try:
        import ccxt
        exchange = ccxt.binance()
        usdc = exchange.fetch_ticker("USDC/USDT")
        stable["usdc_deviation"] = round((usdc["last"] - 1) * 100, 4)
    except Exception:
        stable["usdc_deviation"] = None
    
    score = 0
    factors = {}
    max_score = 17
    
    # 1. MVRV Z-Score
    mvrv = onchain.get("mvrv_z")
    if mvrv is not None:
        try:
            mvrv = float(mvrv)
            if mvrv > 3.5:
                score += 2
                factors["mvrv"] = f"MVRV Z={mvrv:.2f} — extreme overvaluation"
            elif mvrv > 2.0:
                score += 1
                factors["mvrv"] = f"MVRV Z={mvrv:.2f} — overvalued"
            else:
                factors["mvrv"] = "✅ Normal"
        except (ValueError, TypeError):
            factors["mvrv"] = "N/A"
    
    # 2. Fear & Greed extremes
    fng = realtime.get("fear_and_greed")
    if fng is not None:
        try:
            fng = int(fng)
            if fng < 10:
                score += 1
                factors["fng"] = f"Extreme fear ({fng}) — panic"
            elif fng > 90:
                score += 1
                factors["fng"] = f"Extreme greed ({fng}) — euphoria"
            else:
                factors["fng"] = "✅ Normal"
        except (ValueError, TypeError):
            factors["fng"] = "N/A"
    
    # 3. VIX
    vix = risk.get("vix")
    if vix is not None:
        try:
            vix = float(vix)
            if vix > 35:
                score += 3
                factors["vix"] = f"VIX {vix:.0f} — extreme fear"
            elif vix > 28:
                score += 2
                factors["vix"] = f"VIX {vix:.0f} — elevated"
            elif vix > 22:
                score += 1
                factors["vix"] = f"VIX {vix:.0f} — caution"
            else:
                factors["vix"] = "✅ Normal"
        except (ValueError, TypeError):
            factors["vix"] = "N/A"
    
    # 4. Stablecoin depeg
    if stable.get("usdc_deviation") is not None:
        dev = abs(stable["usdc_deviation"])
        if dev > 2.0:
            score += 3
            factors["stablecoin"] = f"USDC depeg {stable['usdc_deviation']:.2f}% — CRITICAL"
        elif dev > 0.5:
            score += 1
            factors["stablecoin"] = f"USDC deviation {stable['usdc_deviation']:.2f}%"
        else:
            factors["stablecoin"] = "✅ Healthy"
    
    # 5. DXY (macro)
    dxy = macro_raw.get("dxy")
    if dxy is not None:
        try:
            dxy = float(dxy)
            if dxy > 106:
                score += 2
                factors["dxy"] = f"DXY {dxy:.0f} — strong dollar pressure"
            elif dxy > 104:
                score += 1
                factors["dxy"] = f"DXY {dxy:.0f} — elevated"
            else:
                factors["dxy"] = "✅ Normal"
        except (ValueError, TypeError):
            factors["dxy"] = "N/A"
    
    # 6. 10Y Yield
    y10 = macro_raw.get("us_10y_yield_percent")
    if y10 is not None:
        try:
            y10 = float(y10)
            if y10 > 5.5:
                score += 2
                factors["yield"] = f"10Y {y10:.1f}% — restrictive"
            elif y10 > 5.0:
                score += 1
                factors["yield"] = f"10Y {y10:.1f}% — elevated"
            else:
                factors["yield"] = "✅ Normal"
        except (ValueError, TypeError):
            factors["yield"] = "N/A"
    
    # 7. Whale signal
    whale = risk_alerts.get("whale") or {}
    if isinstance(whale, dict):
        ws = whale.get("signal")
        if ws == "whale_dominant":
            score += 1
            factors["whale"] = "Whale dominant — distribution risk"
        elif ws:
            factors["whale"] = "✅ Balanced"
    else:
        factors["whale"] = "N/A"
    
    # 8. Crash precursor
    if crash and isinstance(crash, dict):
        crash_signal = crash.get("signal") or crash.get("state")
        crash_score = crash.get("score", 0)
        if crash_signal in ("WARNING", "ALERT", "CRITICAL"):
            score += min(crash_score, 3)
            factors["crash"] = f"Crash precursor: {crash_signal} (score {crash_score})"
        else:
            factors["crash"] = "✅ Normal"
    
    # Determine status
    if score >= 10:
        status = "CRITICAL"
    elif score >= 6:
        status = "ELEVATED"
    elif score >= 3:
        status = "CAUTION"
    else:
        status = "NORMAL"
    
    result = {
        "score": score,
        "max": max_score,
        "status": status,
        "factors": factors,
        "_collected": ts(),
    }
    return result


def main():
    # Acquire shared lock to prevent race with detect_only.py on structural.json
    import fcntl
    _lock_fd = open("/tmp/pipeline-collector.lock", "w")
    fcntl.flock(_lock_fd, fcntl.LOCK_EX)

    print(f"Pipeline Dashboard Collector — {ts()}")
    print("=" * 50)

    btc = fetch_btc_price()
    print(f"BTC: ${btc.get('price', '?'):,.0f}" if btc.get("price") else "BTC: error")

    gate0 = collect_gate0()
    print(f"Layer 0: {gate0['verdict']} (sources: {gate0['sources']})")

    macro = collect_macro()
    print(f"Layer 1: Macro {'✓' if macro else '✗'}")

    structural = collect_structural()
    regime = structural.get("magnets", {}).get("regime", "?")
    print(f"Layer 2: Structural {'✓' if structural else '✗'} (regime: {regime})")

    derivatives = collect_derivatives()
    fr = derivatives.get("funding_rate")
    print(f"Layer 3: Derivatives {'✓' if derivatives else '✗'} (FR: {fr})")

    cycle = collect_cycle()
    score = cycle.get("composite_score")
    print(f"Layer 4: Cycle {'✓' if cycle else '✗'} (score: {score})")

    supplementary = collect_supplementary()
    print(f"Supplementary: {'✓' if supplementary else '✗'}")

    # AlphaEar-derived collectors (non-blocking, best-effort)
    news_feed = collect_news_feed()
    print(f"News Feed: {'✓' if news_feed else '✗'}")

    social_pulse = collect_social_pulse()
    print(f"Social Pulse: {'✓' if social_pulse else '✗'}")

    signal_tracker = collect_signal_tracker()
    print(f"Signal Tracker: {'✓' if signal_tracker else '✗'}")

    # Regime Summary — synthesize all layers
    regime = compute_regime_summary(gate0, macro, structural, derivatives, cycle, supplementary)
    synth_verdict = regime.get("synthesis", {}).get("verdict", "?")
    print(f"Regime Summary: {synth_verdict}")

    # Append regime change if any
    regime_payload = dict(regime)
    regime_payload["btc_price"] = btc.get("price")
    regime_payload["gate"] = {"verdict": gate0.get("verdict", "PROCEED"), "sources": gate0.get("sources", [])}
    append_prediction("regime_change", regime_payload)

    # VAL Absorption Detection — post-processing across Layer 2 + Layer 3
    val_signal = detect_val_absorption(btc, structural, derivatives)
    if val_signal:
        structural["val_absorption"] = val_signal
        sig_type = val_signal.get("signal", "none")
        print(f"VAL Absorption: {sig_type}")
        if sig_type == "VAL_ABSORPTION":
            val_signal["gate0_status"] = gate0.get("verdict", "PROCEED")
            val_signal["regime_label"] = synth_verdict
            append_prediction("trading_signal", val_signal)

    # Breakout-Retest Detection — post-processing across Layer 2 + Layer 3
    breakout_signal = detect_breakout_retest(btc, structural, derivatives)
    if breakout_signal:
        structural["breakout_retest"] = breakout_signal
        sig_type = breakout_signal.get("signal", "none")
        print(f"Breakout-Retest: {sig_type}")
        if sig_type == "ENTRY_SIGNAL":
            breakout_signal["gate0_status"] = gate0.get("verdict", "PROCEED")
            breakout_signal["regime_label"] = synth_verdict
            append_prediction("trading_signal", breakout_signal)

    # Breakdown-Retest Detection — bearish mirror (support break + rejection)
    breakdown_signal = detect_breakdown_retest(btc, structural, derivatives)
    if breakdown_signal:
        structural["breakdown_retest"] = breakdown_signal
        sig_type = breakdown_signal.get("signal", "none")
        print(f"Breakdown-Retest: {sig_type}")
        if sig_type == "ENTRY_SIGNAL":
            breakdown_signal["gate0_status"] = gate0.get("verdict", "PROCEED")
            breakdown_signal["regime_label"] = synth_verdict
            append_prediction("trading_signal", breakdown_signal)

    # Write all
    write_json("btc_price.json", btc)
    write_json("gate0.json", gate0)
    write_json("macro.json", macro)
    write_json("structural.json", structural)
    write_json("derivatives.json", derivatives)
    write_json("cycle.json", cycle)
    write_json("supplementary.json", supplementary)
    write_json("regime.json", regime)

    meta = {"last_update": ts(), "btc_price": btc.get("price"), "regime_verdict": synth_verdict}
    write_json("meta.json", meta)


    # New standalone collectors
    sentiment = collect_sentiment()
    print(f"Sentiment: {'✓' if sentiment else '✗'}")
    write_json("sentiment.json", sentiment)

    positioning = collect_positioning()
    print(f"Positioning: {'✓' if positioning else '✗'}")
    write_json("positioning.json", positioning)

    patterns = collect_patterns()
    print(f"Patterns: {'✓' if patterns else '✗'}")
    write_json("patterns.json", patterns)

    crash = collect_crash_precursor()
    print(f"D2 Crash: {crash.get('status', '?')} ({crash.get('composite', 0)}/5)")
    write_json("crash_precursor.json", crash)

    black_swan = compute_black_swan()
    print(f"Black Swan: {black_swan.get('status', '?')} ({black_swan.get('score', 0)}/{black_swan.get('max', 17)})")
    write_json("black_swan.json", black_swan)
    print(f"\n✅ All layers collected → {DATA}/")

    # Regenerate sitemap with current timestamp
    write_sitemap()

    # Inject cold-DOM timestamps into index.html (AI crawler fix)
    inject_timestamps_into_html()

    # Generate daily verdict archive page (once per day)
    try:
        import subprocess
        subprocess.run(
            [sys.executable, str(SCRIPTS / "generate_verdict_page.py")],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        pass

    # Check confidence calibration for auto-downgrade triggers
    alerts = check_confidence_downgrades()
    if alerts:
        print(f"\n⚠️  CONFIDENCE ALERT: {len(alerts)} label(s) flagged")
        for a in alerts:
            print(f"   {a}")


def check_confidence_downgrades():
    """Read confidence_tracker.json and check if any HIGH label should be downgraded.

    Rules (from README.md § Confidence calibration):
      - HIGH: >= 70% hit rate over 90 days, >= 30 trades
      - MEDIUM: 50-70% over 90 days, >= 15 trades
      - LOW: < 50% or < 15 trades
      - Auto-downgrade: if HIGH drops below 65% for 30 days -> MEDIUM

    Returns list of alert strings. Empty list = no issues.
    """
    tracker_path = DATA / "confidence_tracker.json"
    if not tracker_path.exists():
        return ["confidence_tracker.json not found"]

    try:
        with open(tracker_path) as f:
            data = json.load(f)
    except Exception:
        return []

    alerts = []
    summary = data.get("summary", {})
    for label in ["HIGH", "MEDIUM", "LOW"]:
        entry = summary.get(label, {})
        hit_rate = entry.get("hit_rate")
        sample = entry.get("sample_size", 0)

        if hit_rate is None:
            continue  # no data yet

        if label == "HIGH" and hit_rate < 0.65 and sample >= 30:
            alerts.append(
                f"HIGH confidence auto-downgrade: hit rate {hit_rate:.1%} < 65% threshold "
                f"({sample} trades). Downgrading to MEDIUM."
            )
        elif label == "HIGH" and hit_rate < 0.70 and sample >= 30:
            alerts.append(
                f"HIGH confidence warning: hit rate {hit_rate:.1%} approaching 65% downgrade "
                f"threshold ({sample} trades). Monitor closely."
            )

    return alerts


if __name__ == "__main__":
    run_start = ts()
    try:
        main()
        # Write success status
        write_json("run_status.json", {
            "status": "success",
            "started_at": run_start,
            "finished_at": ts(),
        })
    except Exception as e:
        log.error(f"Collector crashed: {e}", exc_info=True)
        write_json("run_status.json", {
            "status": "failed",
            "started_at": run_start,
            "finished_at": ts(),
            "error": str(e),
        })
        sys.exit(1)
