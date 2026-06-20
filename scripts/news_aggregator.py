#!/usr/bin/env python3
"""
BTC Pipeline News Aggregator — standalone, zero external DB dependency.
Cherry-picked from AlphaEar (RKiding/Awesome-finance-skills) per GetClaw review.

Fetches: Google News RSS (3 feeds: bitcoin, crypto, fed) + Polymarket prediction markets.
Output: writes data/news_feed.json for dashboard consumption.
Usage: python3 scripts/news_aggregator.py
"""
import requests
from requests.exceptions import RequestException, Timeout
import json
import os
import time
import threading
from datetime import datetime, timezone
from typing import List, Dict, Optional
import xml.etree.ElementTree as ET

# === Configuration ===
NEWS_CACHE_SECONDS = 300  # 5 minutes
POLYMARKET_CACHE_SECONDS = 600  # 10 minutes
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'news_feed.json')
CACHE_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', '.news_cache')

# BTC-relevant English sources via Google News RSS (no API key required)
# Chinese sources removed — irrelevant general news (football, entertainment, etc.)
# NewsNow sources stubbed — BTC_SOURCES left empty; NewsNowTools is dead code until populated.
BTC_SOURCES = {}

# Fall back to print if loguru unavailable
try:
    from loguru import logger
except ImportError:
    import logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(level=logging.INFO)


# ============================================================
# Content Extractor — Jina Reader API (from AlphaEar)
# ============================================================

class ContentExtractor:
    """Content extraction via Jina Reader API. No API key = 20 req/min."""

    JINA_BASE_URL = "https://r.jina.ai/"
    _rate_limit_no_key = 20
    _rate_window = 60.0
    _min_interval = 3.0
    _request_times = []
    _last_request_time = 0.0
    _lock = threading.Lock()

    @classmethod
    def _wait_for_rate_limit(cls, has_api_key: bool) -> None:
        if has_api_key:
            time.sleep(0.5)
            return
        with cls._lock:
            now = time.time()
            cls._request_times = [t for t in cls._request_times if now - t < cls._rate_window]
            if len(cls._request_times) >= cls._rate_limit_no_key:
                oldest = cls._request_times[0]
                wait = cls._rate_window - (now - oldest) + 1.0
                if wait > 0:
                    time.sleep(wait)
                    now = time.time()
                    cls._request_times = [t for t in cls._request_times if now - t < cls._rate_window]
            since_last = now - cls._last_request_time
            if since_last < cls._min_interval:
                time.sleep(cls._min_interval - since_last)
            cls._request_times.append(time.time())
            cls._last_request_time = time.time()

    @classmethod
    def extract(cls, url: str, timeout: int = 30) -> Optional[str]:
        if not url or not url.startswith("http"):
            return None
        api_key = os.getenv("JINA_API_KEY")
        has_key = bool(api_key and api_key.strip())
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "application/json",
        }
        if has_key:
            headers["Authorization"] = f"Bearer {api_key}"
        cls._wait_for_rate_limit(has_key)
        try:
            resp = requests.get(f"{cls.JINA_BASE_URL}{url}", headers=headers, timeout=timeout)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                    if isinstance(data, dict) and "data" in data:
                        return data["data"].get("content", "")
                    return data.get("content", resp.text)
                except (json.JSONDecodeError, TypeError):
                    return resp.text
            elif resp.status_code == 429:
                time.sleep(60)
                # Recurse once only — prevent infinite loop
                if getattr(cls, '_retried_429', False):
                    return None
                cls._retried_429 = True
                try:
                    return cls.extract(url, timeout)
                finally:
                    cls._retried_429 = False
            return None
        except Exception:
            return None


# ============================================================
# NewsNow Tools — 14-source news aggregator (from AlphaEar)
# ============================================================

class NewsNowTools:
    """Hot news fetcher via NewsNow API. In-memory cached."""

    BASE_URL = "https://newsnow.busiyi.world"
    SOURCES = BTC_SOURCES

    def __init__(self):
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        )
        self.extractor = ContentExtractor()
        self._cache = {}

    def fetch_hot_news(self, source_id: str, count: int = 10, fetch_content: bool = False) -> List[Dict]:
        cache_key = f"{source_id}_{count}"
        cached = self._cache.get(cache_key)
        now = time.time()

        if cached and (now - cached["time"] < NEWS_CACHE_SECONDS):
            return cached["data"]

        try:
            url = f"{self.BASE_URL}/api/s?id={source_id}"
            response = requests.get(url, headers={"User-Agent": self.user_agent}, timeout=30)
            if response.status_code == 200:
                data = response.json()
                items = data.get("items", [])[:count]
                processed = []
                for i, item in enumerate(items, 1):
                    item_url = item.get("url", "")
                    content = ""
                    if fetch_content and item_url:
                        content = self.extractor.extract(item_url) or ""
                    processed.append({
                        "id": item.get("id") or f"{source_id}_{int(now)}_{i}",
                        "source": source_id,
                        "source_name": self.SOURCES.get(source_id, source_id),
                        "rank": i,
                        "title": item.get("title", ""),
                        "url": item_url,
                        "content": content[:500] if content else "",
                        "publish_time": item.get("publish_time") or datetime.now(timezone.utc).isoformat(),
                    })
                self._cache[cache_key] = {"time": now, "data": processed}
                return processed
            else:
                if cached:
                    return cached["data"]
                return []
        except Exception:
            if cached:
                return cached["data"]
            return []

    def get_unified_report(self, sources: Optional[List[str]] = None) -> str:
        """Get multi-source unified report as Markdown."""
        sources = sources or list(self.SOURCES.keys())[:4]  # default: top 4
        all_news = []
        for src in sources:
            all_news.extend(self.fetch_hot_news(src))
            time.sleep(0.2)

        if not all_news:
            return "❌ No news data available"

        report = f"# 📰 BTC Pipeline News Digest ({datetime.now().strftime('%Y-%m-%d %H:%M UTC')})\n\n"
        for src in sources:
            src_name = self.SOURCES.get(src, src)
            report += f"### 🔥 {src_name}\n"
            src_news = [n for n in all_news if n['source'] == src]
            for n in src_news[:5]:
                report += f"- [{n['title']}]({n['url']})\n"
            report += "\n"
        return report

    def fetch_all_json(self, sources: Optional[List[str]] = None) -> Dict:
        """Fetch all sources and return structured JSON for dashboard."""
        sources = sources or list(self.SOURCES.keys())
        result = {
            "timestamp": datetime.now().isoformat(),
            "sources_scanned": len(sources),
            "feeds": {},
        }
        for src in sources:
            items = self.fetch_hot_news(src, count=8)
            result["feeds"][src] = {
                "name": self.SOURCES.get(src, src),
                "count": len(items),
                "items": items,
            }
        return result


# ============================================================
# Polymarket Tools — prediction market data (from AlphaEar)
# ============================================================

class PolymarketTools:
    """Polymarket prediction market data."""

    BASE_URL = "https://gamma-api.polymarket.com"

    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        self._cache = None
        self._cache_time = 0

    def get_active_markets(self, limit: int = 20) -> List[Dict]:
        now = time.time()
        if self._cache and (now - self._cache_time < POLYMARKET_CACHE_SECONDS):
            return self._cache

        try:
            response = requests.get(
                f"{self.BASE_URL}/markets",
                params={"active": "true", "closed": "false", "limit": limit},
                headers={"User-Agent": self.user_agent, "Accept": "application/json"},
                timeout=30,
            )
            if response.status_code == 200:
                markets = response.json()
                result = []
                for m in markets:
                    result.append({
                        "id": m.get("id"),
                        "question": m.get("question"),
                        "slug": m.get("slug"),
                        "outcomes": m.get("outcomes"),
                        "outcomePrices": m.get("outcomePrices"),
                        "volume": m.get("volume"),
                        "liquidity": m.get("liquidity"),
                    })
                self._cache = result
                self._cache_time = now
                return result
            return self._cache or []
        except Exception:
            return self._cache or []

    def get_crypto_relevant(self) -> List[Dict]:
        """Filter markets with crypto/Fed/macro relevance."""
        keywords = ["btc", "bitcoin", "crypto", "fed", "fomc", "rate", "tariff",
                     "recession", "inflation", "cpi", "treasury", "sec"]
        markets = self.get_active_markets(30)
        relevant = []
        for m in markets:
            q = (m.get("question") or "").lower()
            if any(kw in q for kw in keywords):
                relevant.append(m)
        return relevant

    def get_summary_json(self) -> Dict:
        """Return structured prediction market data."""
        crypto = self.get_crypto_relevant()
        return {
            "timestamp": datetime.now().isoformat(),
            "total_active": 0,  # filled below
            "crypto_relevant": len(crypto),
            "markets": crypto,
        }


# ============================================================
# English News — Google News RSS (free, no API key)
# ============================================================

def fetch_english_news() -> Dict:
    """Fetch English BTC/crypto headlines from Google News RSS."""
    feeds = {
        "bitcoin": "https://news.google.com/rss/search?q=bitcoin+price&hl=en-US&gl=US&ceid=US:en",
        "crypto": "https://news.google.com/rss/search?q=cryptocurrency+market&hl=en-US&gl=US&ceid=US:en",
        "fed": "https://news.google.com/rss/search?q=federal+reserve+interest+rates&hl=en-US&gl=US&ceid=US:en",
    }
    result = {}
    for key, url in feeds.items():
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
            if resp.status_code == 200:
                root = ET.fromstring(resp.text)
                items = []
                for i, item in enumerate(root.findall(".//item")[:8]):
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    pub_date = item.findtext("pubDate", "")
                    source = item.findtext("source", "")
                    items.append({
                        "id": f"en_{key}_{i}",
                        "source": f"en_{key}",
                        "source_name": f"{source or key.title()}",
                        "rank": i + 1,
                        "title": title,
                        "url": link,
                        "content": "",
                        "publish_time": pub_date or datetime.now(timezone.utc).isoformat(),
                    })
                result[key] = {"name": f"🇬🇧 {key.title()} News", "count": len(items), "items": items}
        except Exception as e:
            print(f"[news_aggregator] EN {key} fetch failed: {e}")
            result[key] = {"name": f"🇬🇧 {key.title()} News", "count": 0, "items": [], "error": str(e)[:100]}
    return result


# ============================================================
# Main — collect and write
# ============================================================

def main():
    print("[news_aggregator] Fetching Polymarket...")
    pm = PolymarketTools()
    pm_data = pm.get_summary_json()
    pm_data["total_active"] = len(pm.get_active_markets(20))
    print(f"[news_aggregator] Polymarket: {pm_data['crypto_relevant']} crypto-relevant markets")

    print("[news_aggregator] Fetching English BTC news...")
    en_news = fetch_english_news()
    en_total = sum(v["count"] for v in en_news.values())
    print(f"[news_aggregator] English: {en_total} headlines from {len(en_news)} sources")

    # Combine and write
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "en_news": en_news,
        "polymarket": pm_data,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    # Atomic write
    tmp_path = OUTPUT_PATH + ".tmp"
    with open(tmp_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, OUTPUT_PATH)
    print(f"[news_aggregator] Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
