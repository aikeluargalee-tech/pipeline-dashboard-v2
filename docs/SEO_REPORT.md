# SEO Report — Pipeline Dashboard

_Generated June 2026. Baseline = the original single-page dashboard._

## 1. Executive Summary

The site moved from a **single indexable URL** (the dashboard) to a **52-page content platform** with a clear information architecture, ~25,000 words of original educational content, complete on-page SEO, and structured data on every page.

| Metric | Before | After |
|---|---|---|
| Indexable pages | 1 | 52 |
| Sitemap URLs | 1 | 52 |
| Original content (words) | ~0 (data UI) | ~25,000 |
| Pages with canonical | 1 | 52 / 52 |
| Pages with OG/Twitter cards | 1 | 52 / 52 |
| Pages with JSON-LD schema | 1 | 52 / 52 |
| Distinct schema types | Dataset, WebSite | + Organization, Article, FAQPage, BreadcrumbList |
| Research articles | 0 | 36 (6 pillars + 30 supporting) |
| Comparison pages | 0 | 3 |
| Verdict archive pages | 0 | Auto-generated daily |
| Favicon / social card | none | yes |
| Newsletter signup | none | 4 placements |

## 2. On-Page SEO

Every page includes: unique `<title>`, unique meta description, canonical URL, Open Graph + Twitter Card tags, favicon, single `<h1>`, semantic headings, and breadcrumb navigation where applicable.

## 3. Technical SEO

- **SEO-friendly URLs** — clean, lowercase, hyphenated, directory-style with trailing slash
- **Canonical URLs** — absolute canonical on every page
- **XML sitemap** — 52 URLs with `lastmod`, `changefreq`, and `priority`. Regenerated automatically by collect.py
- **robots.txt** — allows search + AI-answer crawlers, blocks Google-Extended (AI training), references sitemap
- **Structured data** — Organization + WebSite (home), Article (research/verdicts), FAQPage (15 Q&As), Dataset (dashboard), BreadcrumbList
- **Mobile** — responsive layout, viewport meta, collapsing nav, fluid grids
- **Performance** — static HTML + one shared CSS + one tiny JS file. No framework, no bundler
- **Accessibility** — skip-to-content link, ARIA labels on nav, focus-visible outlines, semantic landmarks

## 4. Internal Linking

Hub-and-spoke model with cross-references throughout:
- Homepage links to all major sections
- Dashboard cards link to glossary entries (learn-more links)
- Research articles cross-link to pillars, glossary, and dashboard
- Verdict pages link to methodology and dashboard
- Comparison pages link to dashboard and research

## 5. Content Clusters (Topical Authority)

Six clusters, each with a pillar page + 5 supporting articles + glossary entries:

1. **On-Chain Valuation** — MVRV Z-Score, SOPR, Puell, Netflow, Cycle Phases, Composite Score
2. **Structural Liquidity** — Liquidation Magnets, Volume Profile, S/R Bands, Vice Grip, Squeeze/Sweep, VAL Absorption
3. **Risk Frameworks** — Gate0, Black Swan, Position Sizing, VIX Spillover, Stablecoin Health, L-1 Manual Gate
4. **Derivatives** — Funding Rate, Open Interest, CVD, L/S Ratio, Taker Flow
5. **Macro Context** — DXY, Treasury Yields, ETF Flows, M2 Supply, Risk Asset Correlation
6. **Trading Execution** — Breakout-Retest, Breakdown-Retest, Weekend Trading, Signal Tracking, Golden Window

## 6. Discoverability Checklist

- [x] XML sitemap generated and referenced in robots.txt
- [x] robots.txt allows crawling
- [x] Canonical + indexable directives on every page
- [x] Structured data on every page
- [x] Unique titles/descriptions
- [x] Crawlable internal links
- [x] Favicon and social card
- [ ] **Submit sitemap in Google Search Console** (owner action)
- [ ] **Verify domain ownership in GSC** (owner action)
- [ ] Request indexing for priority URLs (owner action)

## 7. Known Limitations

- Lighthouse not run (no headed browser in build env)
- Google Search Console verification = owner action
- Newsletter forms (Buttondown) require account setup
- Contact form (Formspree) requires account setup
- Custom domain not set (still on github.io)
