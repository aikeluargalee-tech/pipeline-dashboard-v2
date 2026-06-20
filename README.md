# ⚡ Pipeline Dashboard

> **Macro-first BTC analysis engine.** Liquidation physics, derivatives positioning, and cycle context — with a Gatekeeper that can veto everything.

[![Build](https://img.shields.io/badge/build-v2.6-22d3ee)]()
[![Refresh](https://img.shields.io/badge/refresh-15min-10b981)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()

🔗 **Live dashboard:** https://aikeluargalee-tech.github.io/pipeline-dashboard/

---

## Philosophy

Most BTC dashboards lead with price, then layer on indicators as decoration. This one leads with **structure** and treats price as the last variable, not the first.

The pipeline runs in strict order, and each layer can only override the layers above it — never the layers below:

```
┌─────────────────────────────────────────────┐
│  L0  GATEKEEPER        — can veto EVERYTHING│
│  L1  MACRO             — sets the wind      │
│  L2  STRUCTURE         — physics, not opinion│
│  L3  DERIVATIVES       — who's positioned   │
│  L4  CYCLE             — where we are in time│
│  TA  TECHNICAL         — context only, last  │
└─────────────────────────────────────────────┘
```

TA is intentionally last and de-emphasized. It cannot generate a signal on its own — it can only confirm or contradict the layers above it. If your read on BTC starts with the chart, you're already wrong about what matters.

---

## Layer reference

### L0 — Gatekeeper
Pre-trade risk filter. Five independent modules, each can push the gate to:
- **🟢 PROCEED** — full size, normal rules
- **🟡 TIGHTENED** — max 10x, half size, tight stops
- **🟠 PAUSE** — close only, no new entries
- **🔴 ABORT** — flatten everything, do not open the app

| Module | What it watches |
|---|---|
| `black_swan` | Composite tail-risk score (0–17): VIX term inversion, DXY spike, funding extremes, stablecoin depeg, etc. |
| `vix_spx` | VIX level + SPX/RSI divergence |
| `ai3_wave` | Hyperscaler capex / capex-to-revenue divergence (the "AI bubble" proxy) |
| `stablecoins` | USDT + USDC market cap trend and velocity |
| `session` | Time-of-day / day-of-week liquidity regime |

**Trigger order matters.** If Black Swan scores ≥ 4 *or* `ai3_wave` flips active, the gate moves to TIGHTENED regardless of other modules. PAUSE/ABORT requires two or more modules in escalation.

### L1 — Macro & Speculation
The wind, not the sail.
- **DXY, US 10Y yield, M2 supply**
- **Risk assets:** SPX, NDX, GOLD, COPPER, WTI
- **VIX** (level + term structure)
- **News feed** — last 5 macro-relevant headlines, deduplicated

### L2 — Structural Liquidity
"Physics, not opinion." Where will price be forced to go?
- **🧲 Liquidation Magnets** — above/below leverage clusters, with cluster density
- **📊 S/R Bands** — ATR-weighted support/resistance on 1h / 4h / 1d
- **📏 Volume Profile** — POC, VAH, VAL with bar chart
- **VAL Absorption Monitor** — active detection of value-area-low absorption setups
- **Breakout-Retest Monitor** — active detection of resistance break + retest entries

Each monitor runs even when no signal is active, so you can see what the system is *looking for* — not just what it found.

### L3 — Derivatives
Real-time positioning. Who's leaning which way, and how stretched.
- **Funding rate** (perps, 8h)
- **Long/Short ratio** (top trader accounts)
- **CVD** (cumulative volume delta, spot+perp aggregated)
- **Open Interest** (with accumulating / unwinding / stable badge)

### L4 — Cycle Context
Weekly and monthly view. Where are we in the 4-year cycle?
- **MVRV-Z** score and threshold zone
- **Puell Multiple**
- **Net exchange flow** (BTC)
- **Coin Days Destroyed** (proxy)
- **BTC supply distribution** by age cohort

### TA — Technical Analysis *(deprioritized)*
Reference only. Lagging indicators that describe what already happened:
- MA50 / MA200 with % distance
- RSI(14), Stochastic, MACD
- Bollinger Bands width, %B, squeeze state
- Options skew (25Δ put/call)

Collapsed by default in the UI. If you're using TA to make decisions, you're trading the rearview mirror.

---

## Regime synthesis

The footer of the page shows a one-line verdict, e.g.:

> **CAUTIOUS BULL** — Tightened rules active. 2 bullish / 1 bearish signals. Max 10x leverage. · TA: Price 10.5% below MA50 — medium-term structure bearish

Synthesis rules (simplified):
1. Start with the gate verdict. If ABORT, the synthesis is ABORT.
2. Tally layer verdicts: bullish (B), neutral (N), bearish (R).
3. If ≥ 2 bear signals and gate ≥ TIGHTENED → **DEFENSIVE** (close partial, no new longs)
4. If gate PROCEED and ≥ 2 bull signals → **AGGRESSIVE BULL**
5. If gate PROCEED and 1-1 split → **NEUTRAL**
6. All other cases → **CAUTIOUS BULL** (the default)

TA warning appended separately, never weighted equally with structural signals.

---

## Confidence calibration

Every monitor and the gate itself emit a `HIGH | MEDIUM | LOW` confidence label. Calibration table (kept internal; updated quarterly):

| Label | Empirical hit rate over last 90 days | Sample size |
|---|---|---|
| HIGH | ≥ 70% | ≥ 30 trades |
| MEDIUM | 50–70% | ≥ 15 trades |
| LOW | < 50% or n < 15 | n < 15 |

If a `HIGH` label drops below 65% for 30 days, it's auto-downgraded to MEDIUM and a flag is raised. The full table is published quarterly in `/analysis/confidence-report.md`.

---

## Data sources

| Layer | Source | Refresh |
|---|---|---|
| BTC price | Binance public API | 1m |
| Liquidation heatmaps | Coinglass (rendered PNG, fetched) | 1h |
| Funding / OI / L-S ratio | Binance Futures public API | 5m |
| CVD | Derived from Binance aggTrades | 5m |
| Volume Profile | Derived from Binance klines | 15m |
| S/R bands | Derived (ATR-weighted) | 15m |
| MVRV-Z, Puell, Netflow | Glassnode / CryptoQuant (manual) | 1d |
| DXY, yields, SPX, VIX | FRED + Yahoo Finance | 1h |
| News | RSS aggregator (filtered) | 15m |

Run `python collect.py` to refresh everything in one go. `deploy.sh` rebuilds `data/*.json` and pushes to GitHub Pages.

---

## Known failure modes

This is a *macro-first* system. It will be wrong, sometimes expensively, in these regimes:

1. **Sudden liquidity shocks** (exchange hack, stable depeg) — Black Swan module catches some, not all. If the trigger isn't in the score, we miss it. Manual override required.
2. **Regime change at cycle boundary** — the cycle model assumes 4-year halving cycles; a structural break (e.g. spot ETF era) can re-base valuations in ways the model doesn't anticipate.
3. **Weekend / holiday illiquidity** — derivatives signals are noisier, the session module downgrades but doesn't fully neutralize. Treat weekend signals with extra skepticism.
4. **Correlation breakdown** — the macro layer assumes BTC eventually re-correlates with DXY/liquidity. During acute risk-off (e.g. COVID March 2020) it can decouple for weeks.
5. **AI-3 wave module** is new (added v2.4). The "AI bubble" thesis is still forming. Treat this module as MEDIUM-confidence at best.

---

## Local development

```bash
git clone https://github.com/aikeluargalee-tech/pipeline-dashboard.git
cd pipeline-dashboard
pip install -r requirements.txt
python collect.py          # refresh data/
python -m http.server     # serve at http://localhost:8000
```

No build step. Pure static HTML + Python data collection.

---

## Architecture

```
.
├── index.html              # Single-page dashboard, all CSS+JS inline
├── collect.py              # Data pipeline: fetch → process → emit JSON
├── deploy.sh               # Build + push to GitHub Pages
├── data/                   # Generated. One JSON per source.
│   ├── regime.json
│   ├── macro.json
│   ├── structure.json
│   ├── derivatives.json
│   ├── cycle.json
│   ├── ta.json
│   └── ...
└── assets/                 # Heatmap images, charts
```

The page is intentionally monolithic — no React, no bundler, no npm. Open `index.html` in a browser, it works. This is a *tool*, not a product.

---

## Changelog

### v2.6 — current
- Breakout-Retest monitor with 48h retest window
- VAL absorption detection (volume + CVD confirmation)
- Gatekeeper rule: AI-3 wave module

### v2.5
- Volume Profile chart with POC/VAH/VAL markers
- Signal stats footer

### v2.4
- AI-3 wave module (experimental)
- Session module

### v2.0
- Macro-first architecture (gate → macro → structure → derivatives → cycle)
- TA demoted to supplementary

### v1.x
- Chart-first prototype (deprecated)

---

## License

MIT. Use the data, fork the dashboard, build your own version. Just don't paper-trade the verdicts without understanding the layers.

---

*Built and maintained by [@aikeluargalee-tech](https://github.com/aikeluargalee-tech). Not financial advice. The dashboard is a tool — the judgment is yours.*
