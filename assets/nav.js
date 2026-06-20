// Shared Navigation + Footer Component
// Injected into every page for consistent navigation.
// Falls back to static HTML in <noscript> for crawlers.

(function() {
  const BASE = window.location.pathname.startsWith('/pipeline-dashboard-v2') 
    ? '/pipeline-dashboard-v2' 
    : (window.location.pathname.startsWith('/pipeline-dashboard') ? '/pipeline-dashboard' : '');

  // Inject Google Fonts if not already present
  if (!document.querySelector('link[href*="fonts.googleapis.com"]')) {
    const preconnect1 = document.createElement('link');
    preconnect1.rel = 'preconnect';
    preconnect1.href = 'https://fonts.googleapis.com';
    document.head.appendChild(preconnect1);

    const preconnect2 = document.createElement('link');
    preconnect2.rel = 'preconnect';
    preconnect2.href = 'https://fonts.gstatic.com';
    preconnect2.setAttribute('crossorigin', 'anonymous');
    document.head.appendChild(preconnect2);

    const fontLink = document.createElement('link');
    fontLink.rel = 'stylesheet';
    fontLink.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600;700&display=swap';
    document.head.appendChild(fontLink);
  }

  // Inject favicon and social card meta if not already present
  if (!document.querySelector('link[rel="icon"]')) {
    const fav = document.createElement('link');
    fav.rel = 'icon';
    fav.type = 'image/png';
    fav.href = BASE + '/assets/favicon.png';
    document.head.appendChild(fav);
  }
  if (!document.querySelector('link[rel="manifest"]')) {
    const manifest = document.createElement('link');
    manifest.rel = 'manifest';
    manifest.href = BASE + '/manifest.json';
    document.head.appendChild(manifest);
  }
  if (!document.querySelector('link[rel="apple-touch-icon"]')) {
    const apple = document.createElement('link');
    apple.rel = 'apple-touch-icon';
    apple.href = BASE + '/assets/logo.png';
    document.head.appendChild(apple);
  }
  if (!document.querySelector('meta[property="og:image"]')) {
    const og = document.createElement('meta');
    og.setAttribute('property', 'og:image');
    og.content = 'https://aikeluargalee-tech.github.io' + BASE + '/assets/social-card.png';
    document.head.appendChild(og);
  }
  if (!document.querySelector('meta[name="twitter:card"]')) {
    const tw = document.createElement('meta');
    tw.name = 'twitter:card';
    tw.content = 'summary_large_image';
    document.head.appendChild(tw);
  }

  // Inject skip-link for accessibility
  const skipLink = document.createElement('a');
  skipLink.href = '#main';
  skipLink.className = 'skip-link';
  skipLink.textContent = 'Skip to content';
  document.body.insertBefore(skipLink, document.body.firstChild);

  // Static <noscript> nav is already in the HTML for crawlers — nothing to do here.
  // The nav below is the JS-enhanced version for interactive users.

  const navHTML = `
  <nav class="site-nav" aria-label="Primary navigation">
    <div class="site-nav-inner">
      <a href="${BASE}/" class="site-nav-logo" aria-label="Pipeline Dashboard home">⚡ Pipeline<span>Dashboard</span></a>
      <button class="site-nav-toggle" aria-label="Toggle navigation menu" aria-expanded="false">☰</button>
      <ul class="site-nav-links" role="menubar">
        <li role="none"><a role="menuitem" href="${BASE}/dashboard/">Dashboard</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/methodology/">Methodology</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/research/">Research</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/glossary/">Glossary</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/events-and-disruptions/">Events</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/verdicts/">Verdicts</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/track-record/">Track Record</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/compare/">Compare</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/faq/">FAQ</a></li>
        <li role="none"><a role="menuitem" href="${BASE}/dashboard/" class="site-nav-cta">Live Dashboard →</a></li>
      </ul>
    </div>
  </nav>`;

  const footerHTML = `
  <footer class="site-footer" role="contentinfo">
    <div class="site-footer-inner">
      <div>
        <h4>⚡ Pipeline Dashboard</h4>
        <p style="font-size:0.82em;color:var(--muted);line-height:1.6;margin-top:8px">
          Free, open-source Bitcoin intelligence — macro-first multi-layer analysis
          with Gate0 risk gating. Not financial advice.
        </p>
      </div>
      <div>
        <h4>Tools</h4>
        <ul>
          <li><a href="${BASE}/dashboard/">Live Dashboard</a></li>
          <li><a href="${BASE}/verdicts/">Verdict Archive</a></li>
          <li><a href="${BASE}/track-record/">Track Record</a></li>
          <li><a href="${BASE}/compare/">Comparisons</a></li>
        </ul>
      </div>
      <div>
        <h4>Learn</h4>
        <ul>
          <li><a href="${BASE}/methodology/">Methodology</a></li>
          <li><a href="${BASE}/research/">Research</a></li>
          <li><a href="${BASE}/events-and-disruptions/">Events & Disruptions</a></li>
          <li><a href="${BASE}/glossary/">Glossary</a></li>
          <li><a href="${BASE}/faq/">FAQ</a></li>
        </ul>
      </div>
      <div>
        <h4>About</h4>
        <ul>
          <li><a href="${BASE}/about/">About</a></li>
          <li><a href="${BASE}/contact/">Contact</a></li>
          <li><a href="${BASE}/privacy/">Privacy</a></li>
          <li><a href="${BASE}/terms/">Terms</a></li>
        </ul>
      </div>
    </div>
    <div class="site-footer-bottom">
      BTC Pipeline Dashboard · Macro-first Bitcoin analysis engine ·
      Data sources: Binance + Yahoo Finance + FRED + on-chain providers ·
      Auto-refreshed every 15 minutes (<span id="footer-time"></span>) ·
      <a href="https://github.com/aikeluargalee-tech/pipeline-dashboard" style="color:var(--muted)">GitHub</a> ·
      MIT License
    </div>
  </footer>`;

  // Inject navigation
  const navPlaceholder = document.getElementById('nav-placeholder');
  if (navPlaceholder) {
    navPlaceholder.innerHTML = navHTML;
  } else {
    document.body.insertAdjacentHTML('afterbegin', navHTML);
  }

  // Inject footer
  const footerPlaceholder = document.getElementById('footer-placeholder');
  if (footerPlaceholder) {
    footerPlaceholder.innerHTML = footerHTML;
  } else {
    document.body.insertAdjacentHTML('beforeend', footerHTML);
  }

  // Highlight active nav link based on current path
  const currentPath = window.location.pathname;
  document.querySelectorAll('.site-nav-links a').forEach(link => {
    const linkPath = new URL(link.href).pathname;
    if (currentPath === linkPath || (linkPath !== BASE + '/' && currentPath.startsWith(linkPath))) {
      link.classList.add('active');
      link.setAttribute('aria-current', 'page');
    }
  });

  // Wire up mobile nav toggle with ARIA
  const toggle = document.querySelector('.site-nav-toggle');
  const links = document.querySelector('.site-nav-links');
  if (toggle && links) {
    toggle.addEventListener('click', function() {
      const isOpen = links.classList.toggle('open');
      toggle.setAttribute('aria-expanded', isOpen);
    });
  }
})();
