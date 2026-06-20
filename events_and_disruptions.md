# Events & Disruptions — Reference Log + Market Diary

**Dual purpose:**

1. **Trigger Library** — When similar macro/structural patterns appear, match
   RHYME TRIGGERS → pull entry → read transmission chain and outcome. A pre-wired
   response library, not a log.

2. **Market Diary** — Record events and market reactions. Price before, price after,
   what triggered the move, what the pipeline showed. No commentary needed. The
   data IS the value. Two years from now, the raw numbers and pipeline states
   tell the story without anyone's opinion attached.

**Maintainers:** Milo (mechanical entries, auto-generate from pipeline data).
Entries are factual — event, price, reaction, pipeline state. No judgment required.

**Write triggers:**
- L-1 Manual Gate is set → auto-generate entry skeleton
- Any Monitor fires 48h+ unresolved → record structural event
- Quarterly options expiry passes → add actual result row to historical table
- Each trading day → auto-generate Market Diary entry from pipeline data

---

## ENTRY FORMAT

```
## EVENT NNN — Title

DATE:        YYYY-MM-DD
STATUS:      ACTIVE | RESOLVED | ARCHIVED
TYPE:        Macro | Structural | Geopolitical | Technical | Composite

ECONOMY:
  [Transmission mechanism — how does this event flow through to markets?]

BTC EFFECT:
  [Specific BTC price/structure impact — levels, percentages, timeframes]

PIPELINE STATE AT EVENT:
  Gate0:       PROCEED | TIGHTENED | PAUSE | ABORT
  Macro:       RISK-ON | NEUTRAL | RISK-OFF
  Structure:   Balanced | Downside Sweep | Upside Squeeze
  Derivatives: BULLISH | NEUTRAL | OVERHEATED
  Cycle:       BUY ZONE | UNDERVALUED | MID | SELL ZONE
  Synthesis:   [verdict]
  BTC Price:   $XX,XXX

RHYME TRIGGERS:
  - [Compound condition 1]
  - [Compound condition 2]
  - [Minimum 2 conditions for a match]

RHYME CONFIDENCE: HIGH | MEDIUM | LOW
  [Based on trigger match count and macro regime similarity]

PRIOR RHYMES:
  - [Event NNN — similar trigger set, outcome]
  - [Event NNN — partial match, outcome]

RESOLUTION:
  [Filled AFTER event concludes — what actually happened vs expectation]

NOTES:
  [Additional context, invalidation conditions, edge cases]
```

---

## HISTORICAL EVENTS — 2021-2024

Research by Antigravity (Gemini 3 Pro), Jun 18 2026. 27 events filling the gap before
our live tracking began (Dec 2024). Condensed format: dates, narratives, triggers, outcomes.

Full research source: btc_historical_reference_2021_2024.md (Antigravity brain)

### EXPIRIES — Quarterly Options (2021-2023)

#### EVENT H01 — Mar 26, 2021 Expiry
- **Regime:** Strong Bull. BTC near ATH. Record $6.1B OI.
- **Narrative:** Tesla accepting BTC (Mar 24). MicroStrategy/Grayscale buying. Expected expiry to launch further gains.
- **Direction:** Consolidated flat → rallied sharply after expiry.
- **RHYME TRIGGERS:** Quarterly expiry + institutional accumulation narrative + BTC near ATH
- **CONFIDENCE:** MEDIUM

#### EVENT H02 — Jun 25, 2021 Expiry
- **Regime:** Post-crash consolidation. Bearish transition.
- **Narrative:** Max pain $34K. China mining ban in full effect — hashrate plunging, miners liquidating.
- **Direction:** Flat into expiry → modest relief bounce.
- **RHYME TRIGGERS:** Quarterly expiry + regulatory crackdown + hashrate capitulation
- **CONFIDENCE:** MEDIUM

#### EVENT H03 — Sep 24, 2021 Expiry
- **Regime:** Bull consolidation. Q3 correction seeking bottom. $3.2B OI.
- **Narrative:** China PBOC blanket ban on ALL crypto on expiry day. Evergrande debt crisis.
- **Direction:** Sharp drop on China ban → swift recovery → launched Q4 run to ATH.
- **RHYME TRIGGERS:** Quarterly expiry + China regulatory shock + TradFi debt crisis + V-shape recovery
- **CONFIDENCE:** HIGH

#### EVENT H04 — Dec 31, 2021 Expiry
- **Regime:** Distribution. Post-ATH downtrend. $5.7B expiry.
- **Narrative:** FOMC confirmed accelerated taper + 2022 hikes. Traders de-risking into year-end.
- **Direction:** Steady decline into year-end. Closed near lows.
- **RHYME TRIGGERS:** Year-end expiry + post-ATH distribution + Fed hawkish pivot + de-risking
- **CONFIDENCE:** HIGH

#### EVENT H05 — Mar 25, 2022 Expiry
- **Regime:** Bear market. Russia invaded Ukraine Feb 24. First Fed hike (25bp) Mar 16.
- **Narrative:** Luna Foundation Guard aggressively buying spot BTC to back UST — artificial demand. Max pain ~$42K.
- **Direction:** Rallied to $45K on LFG buying → peaked → deep downward spiral.
- **RHYME TRIGGERS:** Quarterly expiry + war + rate hike start + artificial spot demand
- **CONFIDENCE:** LOW (LFG buying was one-off, unrepeatable)

#### EVENT H06 — Jun 24, 2022 Expiry
- **Regime:** Severe capitulation. Terra/LUNA collapsed May 2022.
- **Narrative:** Celsius/Voyager/3AC insolvency contagion. Fed 75bp Jun 15. CPI 8.6% Jun 10.
- **Direction:** Crashed to $17.6K on Jun 18 → consolidated flat around expiry.
- **RHYME TRIGGERS:** Quarterly expiry + insolvency contagion + 75bp hike + CPI shock + max stress compound
- **CONFIDENCE:** HIGH

#### EVENT H07 — Sep 30, 2022 Expiry
- **Regime:** Deep winter. BTC stuck $18K-$20K for weeks.
- **Narrative:** UK gilt crisis. 75bp hike Sep 21. Dealer gamma pinning to max pain. Extreme vol compression.
- **Direction:** Sideways at $19K.
- **RHYME TRIGGERS:** Quarterly expiry + sovereign debt crisis + extreme vol compression + 75bp hike
- **CONFIDENCE:** MEDIUM

#### EVENT H08 — Dec 30, 2022 Expiry
- **Regime:** Bear market bottoming. FTX collapsed Nov 2022.
- **Narrative:** Dead market. Tax-loss harvesting. Genesis/DCG bankruptcy fears. Trust destroyed.
- **Direction:** Sideways at cycle lows ($16.5K). Historic vol compression.
- **RHYME TRIGGERS:** Year-end expiry + exchange collapse trauma + tax-loss selling + trust destruction
- **CONFIDENCE:** HIGH

#### EVENT H09 — Mar 31, 2023 Expiry
- **Regime:** Bull recovery. SVB/Signature/Silvergate collapsed Mar 10-12.
- **Narrative:** Fed BTFP injected billions. Short gamma forced dealers to buy as BTC broke higher. Banking crisis validated BTC thesis.
- **Direction:** Surged $20K → $28K into expiry → consolidated.
- **RHYME TRIGGERS:** Quarterly expiry + banking crisis + Fed emergency liquidity + short gamma squeeze
- **CONFIDENCE:** HIGH

#### EVENT H10 — Jun 30, 2023 Expiry
- **Regime:** Bull market. "The BlackRock Effect."
- **Narrative:** BlackRock filed spot BTC ETF Jun 15. Fidelity/Invesco followed. OI concentrated at $30K. SEC sued Binance/Coinbase.
- **Direction:** Surged mid-June → consolidated at $30K-$31K gamma wall on expiry.
- **RHYME TRIGGERS:** Quarterly expiry + institutional ETF catalyst + regulatory crackdown offset
- **CONFIDENCE:** MEDIUM

#### EVENT H11 — Sep 29, 2023 Expiry
- **Regime:** Bull consolidation. Flat spot, high OI.
- **Narrative:** Grayscale won SEC lawsuit Aug 2023. Fed paused Sep 20 but hawkish ("higher for longer"). Pre-ETF window.
- **Direction:** Flat into expiry → breakout above $28K after.
- **RHYME TRIGGERS:** Quarterly expiry + pre-ETF anticipation + hawkish Fed pause
- **CONFIDENCE:** MEDIUM

#### EVENT H12 — Dec 29, 2023 Expiry
- **Regime:** Strong bull. ETF approval countdown.
- **Narrative:** Spot ETF fever. MicroStrategy buying. Fed dovish pause Dec 13 — 3 rate cuts for 2024.
- **Direction:** Rallied through Q4 → consolidated $42K-$43K around expiry → broke higher Jan 2024.
- **RHYME TRIGGERS:** Year-end expiry + ETF approval imminent + dovish Fed pivot + institutional buying
- **CONFIDENCE:** HIGH

---

### GEOPOLITICAL — Major Shocks (2021-2024)

#### EVENT H13 — Russia-Ukraine Invasion (Feb 24, 2022)
- **BTC:** $39K → $34.5K (-9%) → recovered to $40K within 48h
- **Narrative:** BTC dumped with equities (risk-on behavior) then flipped to unconfiscatable asset as Ukrainians/Russians used it to move capital. Short squeeze on recovery.
- **RHYME TRIGGERS:** Military invasion + BTC flash crash -8%+ + safe-haven narrative flip within 48h + impending Fed decision
- **CONFIDENCE:** HIGH

#### EVENT H14 — Pelosi Taiwan Visit (Aug 2-3, 2022)
- **BTC:** $23.4K → $22.6K (-5%)
- **Narrative:** US-China military escalation fears. Risk-off to USD. Post-3AC/Celsius hangover amplified.
- **RHYME TRIGGERS:** US-China Taiwan escalation + crypto bear market + Fed QT active
- **CONFIDENCE:** LOW

#### EVENT H15 — US Banking Crisis (Mar 10-12, 2023)
- **BTC:** $22K → $19.6K (USDC depeg panic) → $24K (+15% intraday on BTFP)
- **Narrative:** SVB/Signature/Silvergate collapsed. Circle's $3.3B stuck at SVB — USDC depegged to $0.88. Fed/Treasury BTFP Mar 12. BTC validated as banking alternative. First real "digital gold" test.
- **RHYME TRIGGERS:** US bank failures + stablecoin depeg + Fed emergency + BTC safe-haven bid + >10% intraday reversal
- **CONFIDENCE:** HIGH (pattern: banking crisis → BTC dip → Fed rescue → BTC surge)

#### EVENT H16 — Iran-Israel Direct Attack (Apr 13-14, 2024)
- **BTC:** $67.5K → $61.2K (-9%) — weekend, TradFi closed
- **Narrative:** Crypto was only liquid market open. Real-time geopolitical risk proxy. High leverage amplified long liquidations.
- **RHYME TRIGGERS:** Middle East attack + weekend (TradFi closed) + elevated leverage + >8% flash crash
- **CONFIDENCE:** HIGH

#### EVENT H17 — Israel-Iran Retaliation Sweep (Apr 19, 2024)
- **BTC:** $64K → $59.6K → $64K (classic liquidity sweep, V-shape)
- **Narrative:** Israeli strikes on Isfahan. Asian hours panic. Limited scope confirmed → immediate reversal. Halving (Apr 20) proximity.
- **RHYME TRIGGERS:** Middle East retaliation + Asian hours + halving proximity + V-shape liquidity sweep
- **CONFIDENCE:** HIGH

#### EVENT H17b — Trump "Liberation Day" Tariff Shock (Apr 2, 2025)
- **BTC:** ~$84K → ~$76K (-10%) within 48h
- **Narrative:** Global tariff shock — "Liberation Day" announcement. Flight from risk across all asset classes. BTC traded as high-beta macro asset, not crypto-specific failure. Crowded risk positioning amplified the drop.
- **RHYME TRIGGERS:** Broad tariff/trade war announcement + BTC trading as risk-on macro proxy + crowded positioning + >8% single-event drop
- **CONFIDENCE:** HIGH
- **Source:** Perplexity AI research

---

### CRYPTO BLACK SWANS — Systemic Failures (2021-2023)

#### EVENT H18 — China Mining Ban (May 18-21, 2021)
- **BTC:** $58K → $30K (-30% single-day crash May 19)
- **Narrative:** Financial institutions banned (May 18), State Council targeted mining (May 21). Elon Musk suspended Tesla BTC payments May 12 (broke structure). 60%+ hashrate in China. Historic liquidation cascade.
- **RHYME TRIGGERS:** Government mining ban + environmental FUD + hashrate collapse + >25% crash + liquidation cascade
- **CONFIDENCE:** MEDIUM

#### EVENT H19 — Terra/LUNA Collapse (May 7-12, 2022)
- **BTC:** $39.5K → $26.7K (-32%)
- **Narrative:** UST depegged → LUNA hyperinflated → LFG sold 80K+ BTC defending peg. Algorithmic stablecoin death spiral. Systemic threat.
- **RHYME TRIGGERS:** Algorithmic stablecoin depeg + forced BTC spot selling + >30% crash + death spiral + macro tightening
- **CONFIDENCE:** MEDIUM

#### EVENT H20 — Crypto Credit Contagion (Jun 12 - Jul 5, 2022)
- **BTC:** $28K → $17.6K
- **Narrative:** Celsius froze withdrawals Jun 12. 3AC liquidation Jun 27. Voyager bankruptcy Jul 5. CPI 8.6%. Fed 75bp. Crypto credit crunch.
- **RHYME TRIGGERS:** Lending freeze + hedge fund insolvency + CPI shock + 75bp hike + cascading bankruptcies
- **CONFIDENCE:** HIGH

#### EVENT H21 — FTX Collapse (Nov 2-11, 2022)
- **BTC:** $21.3K → $15.5K (-27%)
- **Narrative:** Alameda balance sheet (Nov 2). CZ liquidated FTT (Nov 6). FTX bank run → bankruptcy (Nov 11). SBF from white knight to fraud. Genesis/DCG contagion.
- **RHYME TRIGGERS:** Exchange insolvency + fraud + bank run + >25% crash + trust destruction + counterparty contagion
- **CONFIDENCE:** HIGH

#### EVENT H22 — USDC Depeg (Mar 10-12, 2023)
- **BTC:** $22K → $19.6K → $24K (+22% reversal)
- **Narrative:** Circle's $3.3B at SVB. USDC to $0.88. DeFi threatened. Fed BTFP → USDC repegged → BTC surged as safe haven.
- **RHYME TRIGGERS:** Stablecoin depeg + banking crisis + Fed intervention + BTC safe-haven bid + V-shape
- **CONFIDENCE:** HIGH

---

### FOMC SHOCKS — Rate Decisions (2022-2023)

#### EVENT H23 — Rate Hike Cycle Start (Mar 16, 2022)
- **BTC:** $39K → $41.1K (+4.6%) → $48K within a week
- **Narrative:** First hike since 2018. 25bp expected. Powell optimistic. Relief rally. LFG buying compounded.
- **RHYME TRIGGERS:** First hike of cycle + fully priced + dovish presser + BTC relief rally
- **CONFIDENCE:** MEDIUM

#### EVENT H24 — 50bp Hike + QT (May 4, 2022)
- **BTC:** $37.6K → $39.7K (+5.2% day-of) → crashed -8.5% next day
- **Narrative:** Largest hike in 22 years. Powell ruled out 75bp — markets took as dovish. Next day macro reality hit.
- **RHYME TRIGGERS:** Larger hike + dovish qualifier + next-day reversal (headline vs substance gap)
- **CONFIDENCE:** HIGH

#### EVENT H25 — 75bp + Neutral Rate (Jul 27, 2022)
- **BTC:** $21.3K → $22.7K (+6.8%, intraday >+8%)
- **Narrative:** Powell said rates at "neutral," would slow pace. Extreme bearish positioning → massive short squeeze.
- **RHYME TRIGGERS:** 75bp hike + neutral rate language + extreme bearish positioning + >5% rally
- **CONFIDENCE:** HIGH

#### EVENT H26 — Hawkish Pause / Dot Plot Shock (Sep 20, 2023)
- **BTC:** $27.2K → $26K (-5%)
- **Narrative:** Rates unchanged but dot plot showed MORE hikes, fewer 2024 cuts. "Higher for longer." DXY strengthened.
- **RHYME TRIGGERS:** Fed pause + hawkish dot plot + DXY strengthening + BTC >3% decline
- **CONFIDENCE:** HIGH

#### EVENT H27 — Dovish Pivot / Rate Cuts (Dec 13, 2023)
- **BTC:** $41.3K → $42.9K (+3.4%) → continued rally
- **Narrative:** Dot plot: 3 cuts in 2024. Powell: cuts discussed. Massive risk-on. ETF anticipation compounded.
- **RHYME TRIGGERS:** Fed pause + dovish dot plot + rate cut projections + ETF catalyst + BTC rally
- **CONFIDENCE:** HIGH

---

### REGULATORY SHOCKS — Supply-Side & Institutional Access (2021-2025)

Added per GetClaw recommendation. Regulatory events hit BTC differently than geopolitical —
they target supply side, institutional access, and exchange infrastructure directly, not
just risk-off flows.

#### EVENT H27b — SEC Sues Binance + Coinbase (Jun 5-6, 2023)
- **BTC:** $27.1K → $25.5K (-5.9% intraday, recovered within 48h)
- **Narrative:** SEC sued Binance (Jun 5) and Coinbase (Jun 6) — 13 tokens labeled securities. BlackRock filed spot BTC ETF Jun 15 (validated BTC specifically, not crypto broadly).
- **RHYME TRIGGERS:** SEC enforcement action + exchange sued + BTC excluded from security label + ETF catalyst offset
- **CONFIDENCE:** MEDIUM
- **Note:** Event H10 (Jun 2023 Expiry) overlaps — ETF filing partly neutralized the SEC shock.

---

### GOVERNMENT / WHALE LIQUIDATIONS — Scheduled Overhangs (2024-2025)

Added per GetClaw recommendation. These are known, scheduled supply overhangs that show
up in order book before they hit price. Highly pattern-matchable.

#### EVENT H27c — German Government BTC Sales (Jun-Jul 2024)
- **BTC:** $67K → $53.5K (-20%) over 3 weeks
- **Narrative:** German government (BKA) sold ~50,000 BTC seized from Movie2k. Slow drip into thin summer markets. Mt. Gox distributions also beginning. Supply overhang + low volume amplified.
- **RHYME TRIGGERS:** Government BTC sales + thin summer liquidity + Mt. Gox distribution overlap + >15% drawdown
- **CONFIDENCE:** HIGH (repeatable: any government liquidation + low liquidity)

#### EVENT H27d — Mt. Gox Distribution Window (Jul 2024 - ongoing)
- **BTC:** Periodic 1-3% dips on distribution news, no sustained crash
- **Narrative:** Mt. Gox trustee distributing ~140K BTC to creditors over multi-year window. Each transfer announcement triggers short-term selling fears but actual market impact muted — most creditors hold.
- **RHYME TRIGGERS:** Mt. Gox transfer on-chain + distribution announcement + BTC near local high + leverage elevated
- **CONFIDENCE:** LOW (impact consistently overestimated by market)

---

### MACRO DATA SURPRISES — Non-FOMC Inflation / Labor Shocks (2022-2025)

Added per GetClaw recommendation. These move rate expectations without an FOMC meeting —
a blind spot in the original 4-category structure.

#### EVENT H27e — CPI 8.6% Shock (Jun 10, 2022)
- **BTC:** $30.1K → $27.5K (-8.6% day-of) → $17.6K within 1 week (total -41%)
- **Narrative:** May CPI print 8.6% vs 8.3% expected. Killed "inflation peaked" narrative. Fed went 75bp (not 50bp) at Jun 15 meeting. This happened on a non-FOMC week — pure macro data shock.
- **RHYME TRIGGERS:** CPI print above consensus + "inflation peaked" narrative break + hawkish repricing ahead of next FOMC + >5% single-day BTC drop
- **CONFIDENCE:** HIGH
- **Related:** H06 (Jun 2022 Expiry) and H20 (Credit Contagion) — all three stack into the same window.

---

### PROTOCOL / STRUCTURAL EVENTS — Halvings, Upgrades, Network Changes

Added per GetClaw recommendation. These create pre-event accumulation → sell-the-news patterns
and compress/amplify whatever macro event lands nearby.

#### EVENT H27f — Taproot Upgrade (Nov 14, 2021)
- **BTC:** $64.9K → $60.3K (-7%) → $46.2K by Dec (-29%)
- **Narrative:** Major Bitcoin protocol upgrade — Schnorr signatures, smart contract efficiency. BTC peaked at $68.8K days before (Nov 10 ATH), then entered distribution. Upgrade itself was smooth — macro unwind was the real driver.
- **RHYME TRIGGERS:** Major protocol upgrade + ATH proximity + post-upgrade sell-the-news + Fed hawkish pivot incoming
- **CONFIDENCE:** MEDIUM

#### EVENT H27g — Bitcoin Halving #4 (Apr 20, 2024)
- **BTC:** $64.9K pre → $66.1K day-of (+1.8%) → $56.5K by May 1 (-12.8%)
- **Narrative:** Fourth halving — block reward 6.25 → 3.125 BTC. ETF flows dominated the narrative. Halving itself was fully priced. Post-halving selloff overlapped with Iran-Israel tension (Apr 13-19), creating a compound drawdown.
- **RHYME TRIGGERS:** Bitcoin halving + fully priced in + geopolitical event within 7 days + sell-the-news + post-halving miner capitulation risk
- **CONFIDENCE:** MEDIUM
- **Related:** H16 (Iran-Israel Apr 13-14) and H17 (Retaliation Apr 19) — three events stacked within 7 days.

---

### PERPLEXITY AI — Full 2025 FOMC Table

Research by Perplexity AI, Jun 18 2026. Exact dates and % moves for every 2025 Fed meeting
with >3% BTC reaction. Source: Cointelegraph FOMC recap + Fed calendar cross-reference.

| Date | Event | BTC Move | Narrative | Compounding |
|:--|:--|--:|:--|:--|
| 2025-01-29 | FOMC Jan — Hold | -2.7% (one-source -27% outlier) | Rate-path sensitivity, profit-taking after strong prior gains | Leverage and macro positioning stretched |
| 2025-03-19 | FOMC Mar — Hold | **+5.11%** | Fed held steady, BTC front-ran the event | Anticipatory pricing + short-covering |
| 2025-05-07 | FOMC May — Cut | **+6.92%** | Pause or less-hawkish tone read as supportive | Repricing of policy path + momentum buying |
| 2025-06-18 | FOMC Jun — Hold | +1.48% | Market largely digested decision before the fact | Positioning already mature |
| 2025-07-30 | FOMC Jul — Hold | **-3.15%** | Policy patience kept pressure on risk assets | Traders repriced timing of cuts |
| 2025-09-17 | FOMC Sep — 25bp CUT | **-6.90%** | Cut not enough — "sell the cut" dynamic | Crowded long positioning |
| 2025-10-29 | FOMC Oct — 25bp CUT | **-8.00%** | Growth fears outweighed the cut | Profit-taking in high-beta environment |
| 2025-12-10 | FOMC Dec — 25bp CUT | **~-9%** | Year-end guidance disappointed | Late-year liquidity + crowded positioning |

**Dominant 2025 pattern: "Sell the cut."** Three cuts (Sep, Oct, Dec) all produced negative BTC
reactions. Only Mar/May holds rallied. The market wanted cuts when none came (rallied), then
sold when cuts arrived — fully priced in, no surprise.

#### EVENT H28 — 2025 FOMC "Sell the Cut" Pattern
- **Regime:** Bull-to-correction. BTC $80K–$126K range.
- **Narrative:** 6 of 8 meetings: post-meeting selloffs despite dovish action. Only exceptions: Mar (+5.1%) and May (+6.9%) when market held on pause. Sep/Oct/Dec cuts all sold: -6.9%, -8%, -9%. Classic "buy the rumor, sell the fact."
- **RHYME TRIGGERS:** FOMC rate cut + fully priced in + crowded long positioning + BTC extended in trend + SEP/dot plot disappointment
- **CONFIDENCE:** HIGH
- **Source:** Perplexity AI (Cointelegraph + Fed calendar)

#### EVENT H29 — Trump Tariff Crash + USDe Depeg (Oct 10-11, 2025)
- **BTC:** $120K+ → $102K (-15%+ intraday, $19B+ liquidations)
- **Narrative:** Trump tariff/export controls on China. BTC near ATH. Extreme leverage unwound. USDe depeg on Binance compounded panic. Weekend timing amplified.
- **RHYME TRIGGERS:** Tariff/trade war + ATH + extreme leverage + stablecoin depeg + weekend
- **CONFIDENCE:** HIGH

#### EVENT H30 — Dec 2025 Record Expiry ($23B+)
- **Regime:** Post-ATH correction. BTC $80K-$126K.
- **Narrative:** Largest quarterly expiry ever. Record OI, massive call/put skew. Post-election euphoria fading.
- **RHYME TRIGGERS:** Record notional OI (>$20B) + high skew + post-ATH correction + macro proximity
- **CONFIDENCE:** MEDIUM

---

### CODEX CLI — Additional 2024-2025 Events

#### EVENT H31 — Mar 29, 2024 Expiry (Post-ETF ATH Digestion)
- **BTC:** $70.8K → $64.6K (-8.8%) → $72.5K rebound (+12.2%)
- **Narrative:** Large Deribit expiry after March ETF-led ATH near $73.7K. Call-heavy OI — would dealer hedging pin spot or release vol? Pre-halving positioning, crowded leverage.
- **RHYME TRIGGERS:** Quarterly expiry + post-ATH + ETF inflows + pre-halving + crowded leverage
- **CONFIDENCE:** MEDIUM

#### EVENT H32 — BOJ Carry Trade Crash (Aug 5, 2024)
- **BTC:** $61K → $49K (-19.7%) → $57K rebound (+16.3%)
- **Narrative:** Weak US labor data + yen carry-trade unwind hit global risk. BTC below $55K as leveraged positions cut. Nasdaq selloff, VIX spike, yen short covering, crypto liquidations. One of the sharpest single-day risk-off events of the cycle.
- **RHYME TRIGGERS:** BOJ/central bank surprise + weak labor data + carry-trade unwind + VIX spike + >10% single-day BTC crash + correlated equity selloff
- **CONFIDENCE:** HIGH (repeatable: central bank shock + leveraged carry unwind)

#### EVENT H33 — US Election / Pro-Crypto Policy Repricing (Nov 6, 2024)
- **BTC:** $69K → $76.4K (+10.7% in 1 day) → $89K (+29% in 7 days)
- **Narrative:** Trump victory repriced US crypto-policy risk. Traders bought spot and upside options on friendlier regulation + strategic reserve speculation. Republican sweep expectations, $100K calls, ETF inflows, short liquidations all compounded.
- **RHYME TRIGGERS:** US election + pro-crypto candidate win + spot ETF inflows + short squeeze + $100K psychological level proximity
- **CONFIDENCE:** MEDIUM (election-specific)

#### EVENT H34 — Bybit Record Hack (Feb 21, 2025)
- **BTC:** $98K → $87K (-11.2% in 4 days) → $78.3K by Feb 28 (-20.1%)
- **Narrative:** Bybit lost ~$1.4B-$1.5B in ETH to North Korean/Lazarus-linked actors via Safe{Wallet} compromise. Largest exchange hack in history. BTC fell below $90K on systemic exchange-security fears. Trump tariff fears, inflation/rate uncertainty, tech weakness compounded.
- **RHYME TRIGGERS:** Record exchange hack (>$1B) + North Korea/Lazarus attribution + exchange-security fears + macro tightening + >10% BTC decline
- **CONFIDENCE:** HIGH (exchange hack pattern — Mt.Gox, FTX, Bybit)

---

### RHYME FRAMEWORK — Expiry-FOMC Proximity Rule (Calibrated)

Discovered by Perplexity AI cross-referencing every quarterly expiry against the FOMC calendar,
2021-2025. **Calibrated by GetClaw — base-rate adjusted for statistical significance.**

FOMC meets 8×/year. A ±14-day window around each meeting covers 224 days — 61.4% base rate
by chance alone. The 75-80% raw overlap is only 1.2× above base. The real signal concentrates
in the CRITICAL tier.

| Tier | Window | Expiries | Hit Rate | Base Rate | Signal | Verdict |
|:--|:--|--:|--:|--:|--:|:--|
| **CRITICAL** | 0-3 days | 8/20 | 40.0% | 15.3% | **2.6×** | STRONG — real clustering |
| HIGH | 4-7 days | 4/20 | 20.0% | 15.3% | 1.3× | MODERATE — slight above chance |
| MODERATE | 8-14 days | 3/20 | 15.0% | 15.3% | 1.0× | NOISE — indistinguishable from chance |
| LOW | 15+ days | 5/20 | 25.0% | 38.6% | 0.6× | Below base — confirms clustering into tighter windows |

**Compound trigger:** Quarterly expiry + FOMC within 0-3 days (CRITICAL) + elevated OI + spot trend extended.

**What changed:** The MODERATE tier (8-14 days) was demoted — it's at base rate, not a pattern.
Only the CRITICAL tier carries real predictive weight. HIGH tier is marginal — treat as
amplifier, not standalone trigger.

**Sources:** Perplexity AI (FOMC × Deribit cross-reference) + GetClaw (base-rate calibration)

---

## EVENT 001 — Triple Witching June 18 2026

DATE:        2026-06-18
STATUS:      ACTIVE
TYPE:        Macro | Structural

ECONOMY:
  Quarterly options/futures expiration across equities, index options,
  and single-stock futures simultaneously. Estimated $5.5T notional rolling
  off. Gamma exposure collapses as dealer hedges unwind. After settlement,
  dealers no longer need to delta-hedge the expiring positions — the
  "pinning" effect that held markets range-bound releases. This creates a
  volatility window: either a sharp directional move as freed capital
  repositions, or a liquidity vacuum if participants wait for post-expiry
  clarity. Historically, BTC drawdowns cluster within a 3-day window
  around triple witching when combined with elevated leverage.

| Date | BTC Drawdown | Context |
|------|-------------|---------|
| Mar 20, 2026 | -13.5% | Witching + post-FOMC positioning |
| Dec 19, 2025 | -30.5% | Witching + hawkish FOMC + extreme leverage |
| Sep 19, 2025 | -5.2% | Witching only |
| Jun 20, 2025 | -8.5% | Witching + pre-FOMC positioning |
| Mar 21, 2025 | -16.6% | Witching + rate uncertainty |
| Dec 20, 2024 | -13.5% | Witching + FOMC + year-end repositioning |
| Sep 20, 2024 | -2.8% | Witching only |
| Jun 21, 2024 | -12.2% | Witching + FOMC hawkish surprise |

Pattern: standalone witching averages -4.0% (Sep 24, Sep 25). Combined with FOMC or leverage extremes: -12% to -30.5%. Day-of action often muted — larger moves emerge in days/weeks following as positioning resets.

PIPELINE STATE AT EVENT:
  Gate0:       TIGHTENED
  Macro:       NEUTRAL (mild-risk-off)
  Structure:   Downside Sweep
  Derivatives: NEUTRAL
  Cycle:       UNDERVALUED
  Synthesis:   CAUTIOUS BEAR
  BTC Price:   $63,895

RHYME TRIGGERS:
  - Quarterly options expiry (Mar/Jun/Sep/Dec) within 3 days
  - BTC OTM put/call ratio > 60%
  - Gate0 TIGHTENED or worse
  - Structure in Downside Sweep or Upside Squeeze
  - FOMC meeting within ±2 weeks of expiry

RHYME CONFIDENCE: MEDIUM
  Triple witching alone is a recurring event. This instance is MEDIUM
  confidence (not HIGH) because: (1) structure is in active Downside Sweep
  but the sweep magnitude is moderate ($1,000 sandwich width), (2) no
  compounding FOMC this week — the June FOMC already passed, (3) leverage
  conditions are neutral (FR 0.0017%), not extreme.

PRIOR RHYMES:
  - Dec 19, 2025: witching + FOMC + extreme leverage → -30.5%
  - Jun 20, 2025: witching + pre-FOMC → -8.5%
  - Sep 19, 2025: witching only → -5.2%

RESOLUTION:
  [PENDING — update after June 20 close]

NOTES:
  This triple witching arrives with AI-3 wave active (Gate0 tightened) and
  a live Downside Sweep. But derivatives are neutral — no extreme positioning.
  Key difference from Dec 2025: leverage is NOT elevated. This more closely
  resembles Sep 2025 (-5.2%) than Dec 2025 (-30.5%). Monitor resolution
  of the Downside Sweep in the 48h post-expiry window will determine if
  the sweep was distribution or accumulation.

  REFERENCE — CoinBureau, Dec 18 2025 (published day before Dec 19 quad witching):
  "Quad witching amplifies existing market stress rather than creating it."
  BTC fell on every quad witching in 2025: -16.6% (Mar 21), -8.5% (Jun 20),
  -7.9% (Sep 19). Dec 19 turned out -30.5% — worse than the article's worst
  case because it compounded with hawkish FOMC + extreme leverage + year-end
  profit-taking. Key insight: witching is an AMPLIFIER, not a cause. Match
  triggers on "witching + existing stress," not on witching alone.

  REFERENCE — CoinBureau, Jun 18 2026 (published ON triple witching day):
  "Day-of price action is often muted. The larger moves frequently emerge in
  the days and weeks that follow as positioning resets." Confirms the Dec 2025
  article's prediction. Updated data: Mar 20, 2026 added to table (-13.5%).
  Notes that Wed FOMC + Thu witching + Fri holiday makes this week one of the
  most volatile setups of the quarter. $10.6B BTC options expiry June 26 adds
  a second derivatives event within 8 days of witching — compounding risk.

  Refines the amplifier thesis: "Triple witching events tend to amplify
  existing market NARRATIVES rather than create new ones." If the dominant
  narrative is Fed-as-restrictive, witching accelerates the bearish read.
  If narrative shifts dovish, witching accelerates the recovery.

  BULL CASE (recorded for balance): Equities historically deliver positive
  returns in months following major expiries. BTC enters from stronger
  institutional footing (ETF demand, corporate treasury, TradFi integration).
  Call options slightly outnumber puts. Max pain at $74K could exert upward
  gravity if dealer hedging dynamics align.

  FOUR COMPOUNDING FACTORS this week:
  1. Triple witching (Jun 18)
  2. $10.6B BTC options expiry (Jun 26)
  3. FOMC uncertainty (patient-hold, fewer projected cuts)
  4. Fragile US-Iran MOU (non-binding, multiple veto players)
  
  "History doesn't repeat, but it often rhymes. And right now, the rhyme
  scheme looks extremely uncomfortable."

---

## EVENT 002 — BTC $10.6B Options Expiry June 26 2026

DATE:        2026-06-26
STATUS:      PENDING
TYPE:        Structural

ECONOMY:
  $10.6B notional BTC options expire on Deribit. Max pain point and dealer
  gamma positioning will dominate price action in the 48h lead-up.
  Dealers hedging short gamma below max pain (sell into weakness,
  amplify downside) vs long gamma above (buy dips, dampen volatility).
  OTM call wall acts as resistance; OTM put wall as support. Post-expiry
  gamma release can trigger a sharp move in either direction as the
  "pinning" force disappears.

BTC EFFECT:
  [TO FILL — BigSameWorld judgment on expected impact]
  Max pain level: $74,000 (14% above spot)
  Call wall: $80,000 (~$406M exposure)
  Put wall: $60,000 (~$450M exposure)
  OTM ratio: ~80% ($8.6B of $10.6B out-of-the-money)
  
  Large gap between spot ($63.9K) and max pain ($74K) increases probability
  of aggressive dealer hedging. 80% OTM ratio means massive positioning will
  be unwound or rolled — mechanical flows dominate price action in final 48h.

PIPELINE STATE:
  [TO FILL — capture pipeline state on June 24-25]

RHYME TRIGGERS:
  - BTC monthly/quarterly options expiry (last Friday of month)
  - Notional > $5B outstanding
  - Max pain > 5% from spot at T-48h
  - OTM put/call ratio > 70% (downside pressure) or < 30% (upside pressure)

RHYME CONFIDENCE: [TO FILL]

PRIOR RHYMES:
  - [TO FILL — past large BTC options expiries with outcomes]

RESOLUTION:
  [PENDING — update after June 27]

NOTES:
  This is a mechanical event — not narrative-driven. The outcome is primarily
  determined by dealer positioning (gamma profile) and the max pain gravity
  effect in the final 24h. Less susceptible to headlines than FOMC or
  geopolitical events, but can compound with them if timing overlaps.
  
  COMPOUNDING RISK: This expiry falls 8 days after triple witching (Jun 18).
  Two derivatives-driven events within a single window. Post-witching
  positioning reset + options expiry flows = elevated volatility probability.
  80% OTM ratio is extreme — most contracts expire worthless, forcing
  mechanical unwinding rather than strategic positioning.

---

## EVENT 003 — FOMC June 2026 Hold

DATE:        2026-06-10 to 2026-06-11 (meeting)
STATUS:      ACTIVE (market processing)
TYPE:        Macro

ECONOMY:
  Fed held rates. Dot plot shifted — median 2026 projection moved from
  2 cuts to 1 cut. Powell used "patient" language, signaling the Fed is
  comfortable waiting for clearer data before moving. Market initially
  priced this as hawkish (fewer cuts than expected), then recalibrated
  as the "patient" language was parsed as data-dependent rather than
  structurally hawkish.

  Transmission chain:
  1. Dot plot → fewer projected cuts → USD strengthened → risk assets
     sold off initially
  2. "Patient" language → market realized Fed isn't actively tightening,
     just not easing yet → partial recovery
  3. Treasury curve: short end held, long end drifted higher → curve
     steepened modestly
  4. Delayed effect: the hawkish read takes 2-4 weeks to fully price
     into risk assets as positioning adjusts

BTC EFFECT:
  Initial dip on hawkish dot plot read, partial recovery on Powell's
  tone. Medium-term headwind from reduced rate-cut expectations —
  fewer cuts = tighter financial conditions = lower BTC speculative
  appetite. BUT: the "patient" qualifier leaves the door open. If
  inflation data softens, the dot plot can shift back at the July
  meeting. This is not a structural regime change — it's a timing shift.

PIPELINE STATE AT EVENT:
  [TO FILL — capture state on June 10-11]

RHYME TRIGGERS:
  - FOMC rate hold (no change)
  - Dot plot revision (fewer projected cuts than prior meeting)
  - Chair language: "patient" / "data-dependent" / "wait and see"
  - Market initially prices hawkish, then recalibrates within 48h
  - BTC within 10% of local high (elevated positioning sensitivity)

RHYME CONFIDENCE: HIGH
  Matched: rate hold + dot plot hawkish shift + patient language + BTC
  initial sell-off then partial recovery. This is a recurring FOMC pattern
  seen in 2024-2025 cycle: hawkish hold → risk-off → recalibration.

PRIOR RHYMES:
  - [TO FILL — similar FOMC holds with dot plot hawkish shifts]

RESOLUTION:
  [PENDING — reassess after July FOMC or when macro layer shifts regime]

NOTES:
  The delayed catalyst effect matters. The immediate sell-off recovered
  within 48h, but the reduced rate-cut expectations act as a slow bleed
  on risk appetite over 2-4 weeks. Watch the derivatives layer for
  positioning shifts (OI decline, FR turn negative) as the delayed effect
  propagates.
  
  COINBUREAU Jun 18: "The Fed may have removed a major supportive catalyst."
  If investors continue interpreting the Fed as restrictive rather than
  supportive, expiration-related volatility becomes an accelerator rather
  than an isolated event. Triple witching amplifies the dominant narrative —
  and the dominant narrative post-FOMC is cautious/restrictive.

---

## EVENT 004 — US-Iran MOU (Nuclear / Hormuz)

DATE:        2026-06-17 (MOU signed)
STATUS:      ACTIVE (MOU fragile — implementation pending)
TYPE:        Geopolitical

ECONOMY:
  US and Iran signed a Memorandum of Understanding covering nuclear
  enrichment limits and Strait of Hormuz transit security. Key points:
  - Iran agrees to enrichment cap (3.67%) and IAEA inspections
  - US agrees to partial sanctions relief (energy exports)
  - Strait of Hormuz transit security guarantees (20% of global oil)

  Fragility factors:
  - MOU is NOT a treaty — no Senate ratification, no binding mechanism
  - Multiple parties with veto power: Iranian hardliners, US Congress,
    Israeli government, Saudi Arabia, GCC states
  - Iranian hardliners oppose enrichment limits; US hawks oppose
    sanctions relief; Israel explicitly rejected the framework
  - Any single veto player can collapse the agreement

  Transmission chain if MOU holds:
  1. Sanctions relief → Iranian oil exports increase → oil prices ease
     → lower inflation expectations → Fed more dovish → risk-on
  2. Hormuz security → shipping insurance costs decline → global trade
     friction reduced → EM currencies strengthen → BTC correlated rally

  Transmission chain if MOU breaks:
  1. Enrichment resumes → military escalation risk → oil spikes → 
     inflation expectations surge → Fed hawkish → risk-off
  2. Hormuz threatened → oil supply disruption fear → VIX > 30 →
     BTC correlation with SPX turns sharply negative → flight to cash
  3. Israeli preemptive posture → regional conflict risk premium →
     gold rallies, BTC initially sells off (risk-off correlation),
     then potentially recovers as "digital gold" narrative reactivates

BTC EFFECT:
  MOU holding: mild bullish — lower oil = lower inflation = more Fed
  flexibility = better risk asset conditions. But the effect is indirect
  and slow (2-4 months to propagate through sanctions relief).

  MOU breaking: sharp bearish initially (risk-off spike, BTC correlation
  with equities), then potentially a decoupling if the "digital gold"
  narrative gains traction during a geopolitical crisis. The Dec 2025
  Iran-Israel escalation showed BTC initially sold off -8% then recovered
  within 72h as the safe-haven narrative activated.

PIPELINE STATE AT EVENT:
  Gate0:       TIGHTENED
  Macro:       NEUTRAL (mild-risk-off)
  Structure:   Downside Sweep
  Derivatives: NEUTRAL
  Cycle:       UNDERVALUED
  Synthesis:   CAUTIOUS BEAR
  BTC Price:   $63,895
  L-1 Gate:    INACTIVE (MOU holding — no override needed yet)

RHYME TRIGGERS:
  - US-Iran diplomatic engagement (negotiation/MOU/treaty phase)
  - Hormuz Strait transit security in question
  - Multiple veto players with stated opposition
  - Agreement is non-binding (MOU, not treaty)
  - Israeli government explicitly opposes framework
  - Oil price > $70/bbl (sensitivity to supply disruption)

RHYME CONFIDENCE: LOW
  Only 1 trigger firmly matched (non-binding agreement with multiple
  veto players). The MOU is holding but fragile. No historical precedent
  with this exact combination of players and stakes. LOW confidence means:
  use this entry for awareness, not for trading decisions.

PRIOR RHYMES:
  - April 2025: US-Iran indirect talks → MOU collapsed within 3 weeks →
    BTC -12% on escalation fears
  - Dec 2025: Iran-Israel direct escalation → BTC -8% initial, +15%
    recovery as digital gold narrative activated
  - JCPOA 2015: Nuclear deal signed, held for 3 years → oil -15%,
    EM currencies +8%, BTC not yet correlated

RESOLUTION:
  [PENDING — monitor for MOU collapse trigger (L-1 gate would be set)]

NOTES:
  This is the most important watchlist item. If the MOU breaks, L-1 Manual
  Gate must be set to PAUSE or ABORT immediately. The transmission chain
  from breakdown → oil spike → VIX surge → BTC correlation flip is well
  understood from prior episodes. The key question for resolution: does
  BTC decouple from equities during the next geopolitical shock (digital
  gold narrative), or does it remain a risk-on asset that sells off with SPX?
  
  COINBUREAU Jun 18: "Markets have largely welcomed reports of a temporary
  MOU... However, the agreement remains extremely fragile. The formal signing
  process is still unfolding, while opposition from multiple parties
  continues to create uncertainty. Any breakdown could quickly reignite
  geopolitical tensions, drive oil prices higher, and trigger broad risk-off."
  Bitcoin has increasingly traded as a macro-sensitive asset during
  geopolitical stress — this is a meaningful risk heading into an already
  volatile week (witching + options expiry + FOMC uncertainty + MOU fragility).

---

## EVENT 005 — Strategy (MSTR) Coverage Crisis

DATE:        2026-06-18
STATUS:      ACTIVE (WATCH)
TYPE:        Corporate Treasury Unwind
SOURCE:      Milo + GetClaw (discussion Jun 18)

ECONOMY:
  Strategy (formerly MicroStrategy) holds ~500K BTC (~$32B at $64K).
  STRC preferred stock trading at $91.79 — 8.2% BELOW $100 par value.
  Bond market pricing probability of missed dividends or forced restructuring.

  Coverage math:
  - Nov 2025: ~400K BTC × $90K = $36B ÷ 71yr = ~$507M/yr obligations
  - Jun 2026: ~500K BTC × $64K = $32B ÷ 32yr = ~$1B/yr obligations
  - They bought more BTC AND issued more preferred → obligations doubled
    while BTC value dropped ~11%. Coverage halved from both ends.

  First BTC sale: Strategy sold 32 BTC (~$2.5M at $78K) in June 2026.
  Breaks 4-year absolute commitment: "never selling BTC under any condition."
  Signal, not size — 32 BTC is 0.0038% of holdings. Rule change IS the event.

  Death spiral structure (not imminent, but real):
  BTC↓ → coverage↓ → STRC↓ → new issuance impossible → must sell BTC
  → BTC↓ further → coverage shrinks faster. Fixed-dollar obligations in a
  BTC-denominated asset base. This feedback loop is unique — neither
  German gov (H27c) nor FTX (H21) had it.

  Failure modes:
  - BTC $50K → coverage ~22yr → STRC further below par → ALERT
  - BTC $40K → coverage ~18yr → no new issuance possible → FIRING
  - BTC $30K → coverage ~13yr → forced selling probable → CRITICAL

BTC EFFECT:
  Current: 32 BTC sold → $402M futures liquidation on thin order book
  Risk: Quarterly dividend obligations recurring → each sale at lower
    BTC price requires MORE BTC sold → ratchet effect
  Not a one-time shock — a structural overhang that interacts with every
    other bear-side event in the library

PIPELINE STATE AT EVENT:
  Gate0:       TIGHTENED
  Macro:       NEUTRAL
  Structure:   Downside Sweep
  Derivatives: NEUTRAL
  Cycle:       UNDERVALUED
  Synthesis:   CAUTIOUS BEAR
  BTC Price:   $64,431

RHYME TRIGGERS:
  - Corporate BTC treasury NAV premium → discount (< 1.0x holdings)
  - Preferred shares below par > 5%
  - Coverage ratio halving within single calendar year
  - First BTC sale from previously committed accumulator
  - BTC price sustained below corporate average cost basis

INVALIDATION CONDITIONS:
  - BTC recovers to $90K+ (restores coverage ratio)
  - Strategy converts preferred to equity (removes cash obligation)
  - New equity raise (dilutive but removes the BTC sale trigger)
  - Saylor buys more BTC publicly (strong accumulator signal)

RHYME CONFIDENCE: MEDIUM
  First event of this type. Tesla 2022 sale (E01) is the closest analog
  but Tesla had no preferred dividend structure, no feedback loop.

PRIOR RHYMES:
  - E01 — Tesla BTC sale Q1 2022 (orderly, -8% BTC, no feedback loop)
  - H27c — German gov BTC sales (orderly drip, no feedback loop)
  - H21 — FTX collapse (forced selling with cascade, different cause)

RESOLUTION:
  [PENDING — track coverage ratio and STRC par distance]
  Leading indicators: coverage decline rate, STRC price vs par, quarterly
  dividend coverage, Saylor public statements (defensive vs offensive)

MONITOR TIERS:
  WATCH:   STRC 2-5% below par OR coverage < 40yr (CURRENT)
  ALERT:   STRC >5% below par OR coverage < 20yr OR quarterly sale pattern
  FIRING:  BTC sale > $500M OR STRC >10% below par OR coverage < 15yr

SOURCE: GetClaw + Milo discussion, verified against MSTR market data

---

### Category E — Corporate Treasury Unwind

Added per GetClaw recommendation. Unique properties vs existing categories:
- Feedback loop from BTC price → company stock → debt servicing → forced BTC sales
- No counterparty contagion (unlike exchange collapses)
- Balance sheet is public and readable (13F, 8-K disclosures)
- Transmission is direct, not via sentiment (unlike geopolitical)

#### EVENT E01 — Tesla BTC Sale (Q1 2022)
- **BTC:** $46.9K (Q1 avg) → ~$38K post-sale (-8% orderly)
- **Narrative:** Tesla sold 75% of its $1.5B BTC position (~$936M). Musk: "to prove liquidity of Bitcoin as cash alternative." No feedback loop — Tesla had no BTC-denominated debt obligations. Orderly absorption.
- **RHYME TRIGGERS:** Major corporation BTC sale + orderly (no debt pressure) + CEO public explanation + no feedback loop
- **CONFIDENCE:** LOW (sale was by choice, not necessity)

#### EVENT E02 — Strategy First BTC Sale (Jun 2026)
- **BTC:** 32 BTC sold at ~$78K ($2.5M). STRC $91.79 (< par). Coverage 71yr→32yr.
- **Narrative:** First sale in 4 years. Breaks absolute no-sell commitment. Signal > size. Feedback loop: USD-denominated dividends in a BTC-denominated treasury.
- **RHYME TRIGGERS:** Corporate BTC sale from accumulator + preferred below par + coverage halved + feedback loop active
- **CONFIDENCE:** MEDIUM
- **Related:** EVENT 005 (full entry above)

#### EVENT E03 — [Placeholder: ETF Forced Redemption Event]
- **Reserved** for any future ETF closure, forced redemption, or large institutional unwind with feedback-loop properties.

---

### DECISION 001 — Monitor Ceiling Coupling Fix

DATE:        2026-06-18
AUTHOR:      Milo + GetClaw + Antigravity (dual audit)
STATUS:      DEPLOYED

SUMMARY:
  Synthesis and structural monitors were decoupled. The DOWNSIDE SWEEP
  monitor fired but did not constrain the synthesis verdict — leading
  to CAUTIOUS BULL coexisting with an active structural warning.

  Fix: Active Downside Sweep caps BULLISH/CAUTIOUS BULL at NEUTRAL.
  Active Upside Squeeze caps BEARISH at NEUTRAL.
  Neutral FR no longer inflates bull count (🟡 not 🟢).
  Cycle layer gets 0.5x weight (months-scale cannot outvote live events).

RATIONALE:
  Both independent auditors (Antigravity and GetClaw) identified the same
  root cause: monitors were decorative, not constraining. A beginner seeing
  CAUTIOUS BULL during an active DOWNSIDE SWEEP would enter long into a
  stop-hunt. The fix couples monitors to synthesis ceiling.

REVERSION CONDITION:
  If monitor resolution detection is added (recovery candle closes above
  swept level → monitor clears), the ceiling lifts automatically. No
  manual intervention needed.

---

### DECISION 002 — Beginner Mode Verdict Translations

DATE:        2026-06-18
AUTHOR:      Milo + GetClaw
STATUS:      DEPLOYED

SUMMARY:
  Six verdicts translated to plain English for Simple mode:
  - PROCEED → "🟢 Conditions Clear (No blockers detected)"
  - TIGHTENED → "🟡 CAUTION / RISK"
  - PAUSE → "🟠 HOLD / WAIT"
  - ABORT → "🔴 HIGH RISK"
  - CAUTIOUS BULL → "Rising Safely (Watch for changes)"
  - CAUTIOUS BEAR → "Falling Safely (Use caution)"
  - BULLISH → "Market Rising (Growth Phase)"
  - BEARISH / DO NOT TRADE → "High Risk (Avoid buying)"
  - NEUTRAL → "Neutral / Stable"

RATIONALE:
  Institutional verdicts (CAUTIOUS BULL, DOWNSIDE SWEEP) are meaningless
  to beginners. The translations explain WHAT it means in terms of safety
  and action, without recommending specific trades.

DISCLAIMER GATING:
  FAQ Schema explicitly states "This dashboard doesn't recommend buys
  or sells." No "Safe to Buy," no leverage recommendations. The decision
  is always the user's.

---

## WATCHLIST

| Date | Event | Action Required | Pipeline Alert |
|------|-------|----------------|----------------|
| Jun 20 | Triple witching resolution | Check BTC drawdown vs historical. Update EVENT 001 RESOLUTION. | Downside Sweep — did it resolve? |
| Jun 26 | BTC $10.6B options expiry | Capture max pain, dealer gamma profile. Update EVENT 002. | Monitor 48h pre-expiry |
| Jul 4 | US Independence Day | Thin liquidity. Watch for stop hunts during low-volume session. | Session monitor — reduced hours |
| Jul 15 | July FOMC preview (blackout) | Fed speakers enter blackout. Last signals before meeting. | Macro layer — watch for hawkish/dovish lean |
| Jul 29-30 | July FOMC meeting | Dot plot may shift if June data softens. Update EVENT 003. | Macro regime may shift |
| Ongoing | US-Iran MOU status | If MOU collapses → set L-1 PAUSE immediately. Update EVENT 004. | L-1 gate trigger |
| Ongoing | AI-3 Wave | Currently ACTIVE. Monitor for clearance or escalation to PAUSE. | Gate0 — tight stop mode |
| Ongoing | **CORPORATE_TREASURY_STRESS** | Track MSTR STRC par distance, coverage ratio, quarterly sales. Update EVENT 005. | New monitor — WATCH tier active |
| Quarterly | Options expiry cycle | Add actual row to EVENT 001 historical table after each expiry. | Auto-compare |

---

## MARKET DIARY — Daily / Weekly Price & Events Record

**Purpose:** Capture what actually happened — not just notable disruptions, but the
routine pulse of the market. Prices, moves, news, sentiment shifts. Even the
"obvious" days. Especially the obvious days.

Why record the obvious? Because two years from now, "BTC was $63,895 and dropping
during a Downside Sweep in June 2026" becomes non-obvious. Context erodes. The
diary preserves it.

**Format:** Date, price, what moved, pipeline snapshot. One entry per trading
day or weekly summary during quiet periods. Facts only. The data speaks.

---

### WEEK 25 — June 16-22, 2026

#### Jun 18 — Triple Witching + Downside Sweep Active

- BTC: $63,895 (-2.92% 24h, -4.0% from week open ~$66,560)
- Range: $63,696 – $66,446
- Event: Triple witching — $5.5T notional options/futures expiry
- Reaction: Price swept downside through $64K support. Tested $63.7K.
  Declined steadily from $66.4K high to $63.7K low over 24h.
- News: Triple witching, US-Iran MOU signed (fragile, non-binding),
  FOMC patient-hold still settling, Tether winding aUSDT, Kentucky
  suing Polymarket/Kalshi
- Pipeline: TIGHTENED | mild-risk-off | Downside Sweep (3/3 TF, $1K sandwich) | NEUTRAL (FR 0.0017%) | UNDERVALUED (MVRV-Z 0.42) → CAUTIOUS BEAR
- Key levels: Overhead magnet $65K-$66.2K | Downside magnet $63.5K-$64K | POC $65.8K

#### Jun 17 — Pre-Witching Positioning

- BTC: ~$65,800
- Event: Day before triple witching. Price hovered near overhead magnet cluster.
  US-Iran MOU signed.
- Reaction: [TO FILL — capture exact OHLC]
- Pipeline: [TO FILL]
- Key levels: Overhead magnet $65K-$66.2K active

---

### TEMPLATE — Daily Entry

```
#### Mon DD — Brief Title

- BTC: $XX,XXX (±X.X% 24h, ±X.X% from week open)
- Range: $XX,XXX – $XX,XXX
- Event: [What triggered the move — expiry, FOMC, news, technical break, nothing]
- Reaction: [How price moved — sweep, breakout, chop, recovery. Specific levels.]
- News: [Headlines that coincided — not all news, what moved price]
- Pipeline: GATE0 | MACRO | STRUCTURE | DERIVATIVES | CYCLE → SYNTHESIS
- Key levels: [Magnets, S/R bands, POC — levels that mattered today]
```

### TEMPLATE — Weekly Summary (quiet weeks)

```
### WEEK NN — Mon DD–DD, YYYY

- BTC: Open $XX,XXX → Close $XX,XXX (range $XX,XXX–$XX,XXX)
- Dominant regime: [e.g., Downside Sweep | Balanced chop | Upside squeeze]
- Events: [What happened this week]
- Pipeline average: [dominant states across layers]
```
