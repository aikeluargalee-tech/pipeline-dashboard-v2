# Site Structure Map — Pipeline Dashboard

## Information Architecture

```
/                                   Homepage — value prop, live verdict preview, CTAs
├── /dashboard/                     Live dashboard (relocated from /; data at ../data/)
├── /methodology/                   6-layer framework deep dive
├── /glossary/                      26 metric entries, anchor-linked, cross-referenced
├── /research/                      Research hub — 36 articles across 6 clusters
│   ├── /research/mvrv-z-score/              Pillar: On-Chain Valuation
│   ├── /research/liquidation-magnets/       Pillar: Structural Liquidity
│   ├── /research/gate0-framework/           Pillar: Risk Frameworks
│   ├── /research/derivatives-positioning/   Pillar: Derivatives
│   ├── /research/bitcoin-macro-correlation/ Pillar: Macro Context
│   ├── /research/trading-sessions/          Pillar: Trading Execution
│   └── [30 supporting articles]             5 per cluster
├── /verdicts/                      Daily verdict archive (auto-generated)
│   └── /verdicts/YYYY-MM-DD/               One page per day with reasoning + metrics
├── /compare/                       Competitor comparison hub
│   ├── /compare/gate0-vs-glassnode/
│   ├── /compare/gate0-vs-cryptoquant/
│   └── /compare/gate0-vs-coinglass/
├── /faq/                           15 Q&As with FAQPage schema
├── /about/                         Project story, philosophy, privacy
├── /contact/                       Contact (GitHub + Formspree placeholder)
├── /privacy/                       Privacy policy (no data collected)
└── /terms/                         Terms of use (not financial advice)
```

## Navigation Model

- **Primary nav** (header, every page via nav.js): Dashboard · Methodology · Research · Glossary · Verdicts · Compare · FAQ · Live Dashboard CTA. Collapses to hamburger below 768px.
- **Footer nav** (every page): Tools (Dashboard, Verdicts, Compare) · Learn (Methodology, Research, Glossary, FAQ) · About (About, Contact, Privacy, Terms).
- **Contextual links**: homepage → all sections; dashboard cards → glossary; research articles → pillars + glossary + dashboard; verdicts → methodology + dashboard; comparisons → dashboard + research.

## Topical Authority Clusters

Six content clusters, each mapping to a dashboard layer:

| Cluster | Pillar | Supporting Articles | Glossary Entries |
|---|---|---|---|
| On-Chain Valuation | MVRV Z-Score | 5 | MVRV, SOPR, Puell, Netflow, Composite Score |
| Structural Liquidity | Liquidation Magnets | 5 | Magnet, Volume Profile, POC, VAH/VAL, S/R Bands |
| Risk Frameworks | Gate0 Framework | 5 | Gate0, Black Swan, VIX, Stablecoins |
| Derivatives | Derivatives Positioning | 5 | Funding, OI, CVD, L/S, Taker |
| Macro Context | Bitcoin Macro Correlation | 5 | DXY, VIX, ETF Flow, M2, Yields |
| Trading Execution | Trading Sessions | 5 | ATR, RSI, Bollinger, Sessions |

## Source Layout

```
pipeline-dashboard/
├── index.html                      Homepage
├── dashboard/index.html            Live dashboard (shared CSS, data at ../data/)
├── methodology/index.html          Framework deep dive
├── glossary/index.html             26 metric entries
├── research/                       36 articles (6 pillars + 30 supporting)
├── verdicts/                       Auto-generated daily verdict pages
├── compare/                        3 competitor comparison pages
├── faq/index.html                  15 Q&As
├── about/index.html                Project story
├── contact/index.html              Contact form
├── privacy/index.html              Privacy policy
├── terms/index.html                Terms of use
├── assets/
│   ├── styles.css                  Shared CSS (1,193 lines)
│   ├── nav.js                      Shared nav + footer + favicon injection
│   ├── favicon.png                 Site favicon
│   ├── logo.png                    Apple touch icon
│   ├── social-card.png             OG/Twitter card image
│   └── v7_*.png                    Heatmap images
├── data/                           Generated JSON (collect.py output)
├── scripts/                        Python scripts (collect, detect, verdict gen, etc.)
├── docs/                           Deliverable docs (this folder)
├── collect.py                      Data pipeline
├── deploy.sh                       Build + deploy to GitHub Pages
├── test_collect.py                 23 tests
├── test_detect_only.py             24 tests
├── sitemap.xml                     52 URLs (auto-regenerated)
└── robots.txt                      Crawler rules
```

## Build & Deploy Flow

```
cron (hourly):  test_collect.py + test_detect_only.py → collect.py (data + sitemap + verdict page)
                                                                    └→ deploy.sh (git add + push) → GitHub Pages
cron (15 min):  detect_only.py → signal detection → structural.json update
```

To change page content: edit the HTML file directly. Shared nav/footer/CSS update automatically via nav.js and styles.css.
