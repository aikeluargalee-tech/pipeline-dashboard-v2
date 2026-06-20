# SEO, AEO & GEO Strategy — Pipeline Dashboard

> **Live URL:** https://aikeluargalee-tech.github.io/pipeline-dashboard/
> **Status:** Active optimization. Last reviewed June 2026.

---

## Strategy Overview

The Pipeline Dashboard is a real-time Bitcoin analysis engine. It's a **data product**, not a blog or article. Optimization strategy reflects this: we compete on **freshness signals**, **structured data density**, and **technical authority** — not keyword density or backlinks.

### Three Pillars

| Pillar | Goal | Key Techniques |
|--------|------|----------------|
| **SEO** (Search Engine) | Appear in Google/Bing for Bitcoin analysis queries | Semantic HTML (`<h1>`/`<h2>`), descriptive `<title>`, meta description, sitemap.xml with `changefreq=always` |
| **AEO** (Answer Engine) | Get cited by Google AI Overviews, Perplexity, ChatGPT | FAQPage schema, Dataset schema with `variableMeasured`, OG timestamps, Dublin Core meta |
| **GEO** (Generative Engine) | Influence what AI models say about BTC market structure | Prose narrative sections, entity-rich methodology text, static JSON snapshot for crawlers |

---

## Implementation Checklist

### ✅ Implemented

- [x] **Schema.org Dataset** with 11 `variableMeasured` entries
- [x] **Schema.org FAQPage** with 4 Q&A pairs (<45 words each)
- [x] **Schema.org BreadcrumbList** for sitelink eligibility
- [x] **Schema.org Organization** with `knowsAbout` entities
- [x] **Schema.org WebSite** with SearchAction
- [x] **Schema.org DataDownload** — 6 JSON feed links for Google Dataset Search
- [x] **Semantic HTML** — `<h1>` on dashboard title, `<h2>` on layer headers, `<main>`, `<footer>`
- [x] **Meta tags** — description, subject, classification, author
- [x] **Open Graph** — og:title, og:type, og:description, og:updated_time
- [x] **Dublin Core** — DC.type=Dataset, DC.date, DC.language
- [x] **Article timestamps** — published_time, modified_time (both injected at build + JS refresh)
- [x] **robots.txt** — allows GPTBot, PerplexityBot, ClaudeBot; blocks Google-Extended (AI training)
- [x] **sitemap.xml** — regenerated every collect.py run with current date
- [x] **Cold-DOM fix** — timestamps baked into HTML at build time (not JS-only)
- [x] **Static JSON snapshot** — `<script type="application/json">` with layer descriptions
- [x] **`<link rel="alternate">`** — 6 links to raw JSON data files
- [x] **TL;DR Executive Summary** — above-the-fold, dense with keywords
- [x] **Signal Narrative** — per-layer prose summaries generated from live data
- [x] **Per-card one-liners** — 14 narrative divs populated on refresh
- [x] **How to Use This Data** section — entity-rich methodology paragraph
- [x] **`<title>`** — descriptive with Bitcoin + Macro Analysis keywords
- [x] **TA collapsed by default** — respects "lagging, context only" philosophy

### 🔜 Not Yet Implemented

- [ ] **Confidence calibration auto-downgrade** — README defines the rules; needs trade history DB to wire
- [ ] **Quarterly confidence report** — `/analysis/confidence-report.md` (0 trades tracked so far)
- [ ] **Web Stories** or AMP pages — low priority for a data dashboard
- [ ] **VideoObject schema** — no video content exists
- [ ] **Review schema** — needs user reviews/testimonials (none collected)

---

## Crawler Access Rules

```
# All search crawlers: ALLOWED
User-agent: *
Allow: /

# AI answer engine crawlers: ALLOWED
GPTBot, PerplexityBot, ClaudeBot, OAI-SearchBot: ALLOW

# AI training crawler: BLOCKED
Google-Extended: DISALLOW
```

**Rationale:** We want AI Overviews and answer engines to cite us, but we don't consent to our data being used for foundation model training.

---

## Freshness Strategy

The dashboard's competitive moat is **data freshness**. Every optimization decision flows from this:

1. **Build-time timestamps** — `collect.py` injects ISO 8601 timestamps into `index.html` on every run
2. **JS refresh timestamps** — browser updates `og:updated_time` and Schema `dateModified` after each data fetch
3. **sitemap.xml** — regenerated with `changefreq=always` on every collect.py run
4. **Cold-DOM coverage** — even crawlers that skip JavaScript see real timestamps (not empty `content=""`)

Cron runs every hour. AI engines checking freshness see timestamps never more than 60 minutes old.

---

## Entity Map

These entities should appear in prose sections, meta tags, and Schema.org markup:

| Entity | Type | Where Used |
|--------|------|------------|
| Bitcoin (BTC) | Cryptocurrency | Title, FAQ, methodology, Dataset |
| Macroeconomics | Concept | Methodology, FAQ, layer titles |
| Open Interest | Financial Metric | Dataset variableMeasured, narrative |
| MVRV Z-Score | On-Chain Metric | Dataset, FAQ, methodology |
| Liquidation Heatmap | Technical Indicator | Dataset, FAQ, methodology |
| Structural Liquidity | Concept | FAQ, methodology, layer titles |
| Funding Rate | Derivatives Metric | Dataset, narrative |
| Bollinger Bands | Technical Indicator | Dataset, narrative |
| SOPR | On-Chain Metric | Dataset, methodology |

---

## Measurement & Iteration

- **Google Search Console** — verify sitemap indexing, check FAQ rich results
- **Rich Results Test** — validate all JSON-LD schemas parse correctly
- **Perplexity test queries** — search "BTC pipeline dashboard" and "Bitcoin macro analysis dashboard" monthly
- **Google Dataset Search** — verify DataDownload entries are indexed

If a schema is valid but not surfacing in results, check:
1. Is the page indexed? (site: search)
2. Are timestamps fresh? (<1 hour old)
3. Is the FAQ content unique? (not duplicated from other pages)

---

*Updated June 2026. This file defines the rules — any agent working on this dashboard must follow these conventions.*
