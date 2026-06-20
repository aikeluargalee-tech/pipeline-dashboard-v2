# Remaining Recommendations — Pipeline Dashboard

Everything in the success criteria has been implemented. Items below are owner actions or optional enhancements.

## A. Owner Actions (do these after deploy)

1. **Deploy the new structure.** The site is live — verify the homepage renders at `/` and the dashboard at `/dashboard/`.
2. **Google Search Console.**
   - Verify ownership (DNS or HTML-file method)
   - Submit `https://aikeluargalee-tech.github.io/pipeline-dashboard/sitemap.xml`
   - Use URL Inspection → Request indexing for homepage, methodology, glossary, and research pillars
3. **Validate rich results.** Run homepage, FAQ, and a research article through search.google.com/test/rich-results
4. **Legal review.** `/privacy/` and `/terms/` are good-faith templates — have an attorney review for your jurisdiction.
5. **Newsletter setup.** Create a Buttondown account and a list named "btcpipeline". The existing forms will start working immediately.
6. **Contact form.** Create a Formspree account and replace the placeholder form ID in `/contact/index.html`.

## B. Decisions Made Autonomously

- **Dashboard moved to `/dashboard/`** — root is now the SEO homepage. External links to the old root hit the new homepage (which links to dashboard prominently).
- **Contact = GitHub + Formspree placeholder** — GitHub Pages has no backend. Formspree is the simplest form solution for static sites.
- **Branding kept** — dark "deep space" + cyan/green. Favicon, logo, and social card generated programmatically.
- **Domain** left as `aikeluargalee-tech.github.io/pipeline-dashboard/`. A custom domain would improve credibility and simplify URLs.

## C. Optional Enhancements (nice-to-have)

1. **Custom domain** — biggest single credibility/SEO upgrade. Drop the `/pipeline-dashboard` base path.
2. **Privacy-friendly analytics** — Plausible or Cloudflare Web Analytics (no cookie banner needed).
3. **Real OG art** — replace generated social card with designed art per section.
4. **Article author detail** — add a named Person entity to strengthen E-E-A-T.
5. **404 page** — add `/404.html`; GitHub Pages serves it automatically.
6. **Performance pass** — self-host web fonts or subset them to shave the Google Fonts round-trip.
7. **Image alt audit** — ensure all heatmap PNGs have descriptive alt text.
8. **More research articles** — follow the 12-topic queue in CONTENT_STRATEGY.md.

## D. Maintenance Notes

- **Edit content** by modifying the HTML files directly. Shared nav/footer/CSS update automatically.
- **Add a page**: create `newpage/index.html`, add to sitemap in `collect.py`, add to `deploy.sh` staging, add to nav in `assets/nav.js`.
- **The data pipeline** (`collect.py`) injects timestamps into `dashboard/index.html`, regenerates the 52-URL sitemap, and generates daily verdict pages on every run. All 47 tests pass.

## E. What Was Built (summary)

| Component | Count | Status |
|---|---|---|
| HTML pages | 52 | ✅ Live |
| Research articles | 36 (6 pillars + 30 supporting) | ✅ Published |
| Glossary entries | 26 | ✅ Published |
| Comparison pages | 3 | ✅ Published |
| FAQ Q&As | 15 | ✅ Published |
| Verdict archive | Auto-generated daily | ✅ Wired into collect.py |
| Test suite | 47 tests (23 + 24) | ✅ All passing |
| Bug fixes | 17 (2 HIGH, 7 MED, 8 LOW) | ✅ All fixed |
| Dashboard enhancements | Tooltips, onboarding, learn-more links | ✅ Built |
| SEO infrastructure | Sitemap, schema, canonicals, OG, robots | ✅ Complete |
| Accessibility | Skip-link, ARIA, focus-visible | ✅ Built |
| Brand assets | Favicon, logo, social card | ✅ Generated |
| Newsletter forms | 4 placements | ✅ Built (account pending) |
| Deliverable docs | 4 documents | ✅ Written |
