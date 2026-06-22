#!/usr/bin/env python3
"""
BTC ETF Flow Data Collector
============================
Fetches daily BTC Spot ETF flow data from multiple sources with fallback.

Sources (tried in order):
  1. Farside.co.uk — Direct HTML scrape (Cloudflare may block)
  2. blockchain.news RSS — Parse ETF flow articles for numbers
  3. News scraping fallback — Search for ETF flow data in news

Output: /tmp/btc_etf_flow.json (schema matches generate_v2.py A6 card)

Features:
  - 12-hour file cache (avoid hammering sources)
  - Graceful fallback between sources
  - Robust error handling
  - Can be run via cron: */15 * * * * python3 scripts/fetch_etf_flow.py
"""

import json
import os
import re
import sys
import time
import traceback
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
OUTPUT_PATH = "/tmp/btc_etf_flow.json"
CACHE_MAX_AGE_SECONDS = 12 * 3600  # 12 hours
REQUEST_TIMEOUT = 20  # seconds
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def log(msg: str):
    print(f"[ETF-Flow] {msg}", flush=True)


def is_cache_valid() -> bool:
    """Return True if OUTPUT_PATH exists and was modified < CACHE_MAX_AGE_SECONDS ago."""
    if not os.path.exists(OUTPUT_PATH):
        return False
    try:
        mtime = os.path.getmtime(OUTPUT_PATH)
        age = time.time() - mtime
        if age < CACHE_MAX_AGE_SECONDS:
            remaining = CACHE_MAX_AGE_SECONDS - age
            log(f"Cache valid ({age/3600:.1f}h old, {remaining/3600:.1f}h remaining)")
            return True
        log(f"Cache expired ({age/3600:.1f}h old)")
    except OSError:
        pass
    return False


def http_get(url: str, headers: dict = None, timeout: int = REQUEST_TIMEOUT) -> str | None:
    """HTTP GET with httpx (preferred) or urllib fallback."""
    hdrs = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}
    if headers:
        hdrs.update(headers)

    # Try httpx first
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            r = client.get(url, headers=hdrs)
            if r.status_code == 200:
                return r.text
            log(f"  HTTP {r.status_code} from {url}")
            return None
    except ImportError:
        pass
    except Exception as e:
        log(f"  httpx error: {e}")

    # Fallback to urllib
    try:
        import urllib.request
        req = urllib.request.Request(url, headers=hdrs)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        log(f"  urllib error: {e}")

    return None


def http_get_json(url: str, headers: dict = None, timeout: int = REQUEST_TIMEOUT) -> dict | None:
    """HTTP GET expecting JSON response."""
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    text = http_get(url, headers=hdrs, timeout=timeout)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    return None


def parse_date_flexible(date_str: str) -> str | None:
    """Try to parse various date formats and return 'DD Mon YYYY' style."""
    date_str = date_str.strip()

    # Try: "19 May 2026", "May 19, 2026", "19-May-2026", "2026-05-19"
    formats = [
        "%d %b %Y", "%d %B %Y",
        "%b %d, %Y", "%B %d, %Y",
        "%d-%b-%Y", "%Y-%m-%d",
        "%d/%m/%Y", "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime("%d %b %Y")
        except ValueError:
            continue
    return None


def format_flow_display(value_millions: float) -> str:
    """Format flow value as $XXX.XM with sign."""
    return f"${value_millions:+,.1f}M"


def compute_direction(total: float) -> str:
    """Classify flow direction based on daily total in millions."""
    if total > 300:
        return "strong_inflow"
    elif total > 50:
        return "mild_inflow"
    elif total < -300:
        return "strong_outflow"
    elif total < -50:
        return "mild_outflow"
    else:
        return "flat"


def compute_streak(flows: list[dict]) -> str:
    """Count consecutive days of same direction from the end."""
    if not flows:
        return "—"
    count = 0
    sign = None
    for f in reversed(flows):
        fsign = "in" if f["total"] >= 0 else "out"
        if sign is None:
            sign = fsign
        if fsign == sign:
            count += 1
        else:
            break
    word = "inflow" if sign == "in" else "outflow"
    return f"{count}-day {word} streak"


def build_output(flows: list[dict], source: str) -> dict:
    """Build the enriched A6 JSON output from raw flow data."""
    if not flows:
        return {"card": "A6", "error": "no_flow_data", "source": source}

    # Sort by date (oldest first)
    # flows should already be sorted, but ensure
    latest = flows[-1]
    weekly_net = round(sum(f["total"] for f in flows[-5:]), 1)
    direction = compute_direction(latest["total"])
    streak_label = compute_streak(flows)

    signal_map = {
        "strong_inflow": "🟢 Strong Inflow",
        "mild_inflow": "🟢 Mild Inflow",
        "strong_outflow": "🔴 Strong Outflow",
        "mild_outflow": "🟡 Mild Outflow",
        "flat": "🟡 Flat",
    }

    # Check data staleness
    now = datetime.now(timezone.utc)
    lag_warning = ""
    confirmed = True
    try:
        # Try to parse the latest date to check staleness
        for fmt in ["%d %b %Y", "%d %B %Y", "%b %d, %Y", "%Y-%m-%d"]:
            try:
                latest_dt = datetime.strptime(latest["date"], fmt).replace(tzinfo=timezone.utc)
                age_days = (now - latest_dt).days
                if age_days > 3:
                    lag_warning = f"Data is {age_days} days old"
                    confirmed = False
                break
            except ValueError:
                continue
    except Exception:
        pass

    data = {
        "card": "A6",
        "timestamp": now.strftime("%Y-%m-%d %H:%M UTC"),
        "source": source,
        "direction": direction,
        "total_flow_display": format_flow_display(latest["total"]),
        "streak_7d_display": format_flow_display(weekly_net),
        "streak_label": streak_label,
        "signal_display": signal_map.get(direction, "🟡 Unknown"),
        "data_date": latest["date"],
        "confirmed": confirmed,
        "lag_warning": lag_warning,
        "confirmed_date_note": f"Data as of {latest['date']}",
        "flows": flows,
        "latest": latest,
        "weekly_net": weekly_net,
    }
    return data


def write_output(data: dict):
    """Write output JSON to OUTPUT_PATH."""
    with open(OUTPUT_PATH, "w") as f:
        json.dump(data, f, indent=2)
    log(f"✅ Written to {OUTPUT_PATH}")
    if "error" not in data:
        log(f"   Latest: {data.get('data_date')} = {data.get('total_flow_display')}")
        log(f"   7-day:  {data.get('streak_7d_display')}")
        log(f"   Streak: {data.get('streak_label')}")
        log(f"   Signal: {data.get('signal_display')}")
        log(f"   Source: {data.get('source')}")


# ---------------------------------------------------------------------------
# Source 1: Farside.co.uk Direct Scrape
# ---------------------------------------------------------------------------

def fetch_farside() -> list[dict] | None:
    """
    Try to scrape Farside.co.uk/btc/ for BTC ETF flow data.
    The page has a table with daily totals. Cloudflare often blocks this.
    """
    log("Source 1: Farside.co.uk direct scrape...")
    url = "https://farside.co.uk/btc/"

    html = http_get(url, headers={
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Cache-Control": "no-cache",
    })

    if not html:
        log("  ❌ Farside: No response or blocked by Cloudflare")
        return None

    # Check for Cloudflare challenge
    if "Just a moment" in html or "cf_chl_opt" in html or "challenges.cloudflare.com" in html:
        log("  ❌ Farside: Cloudflare challenge detected")
        return None

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")

        # Look for the main data table
        tables = soup.find_all("table")
        if not tables:
            log("  ❌ Farside: No tables found in HTML")
            return None

        flows = []
        for table in tables:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all(["td", "th"])
                if len(cells) < 2:
                    continue

                # First cell is usually the date
                date_text = cells[0].get_text(strip=True)
                parsed_date = parse_date_flexible(date_text)
                if not parsed_date:
                    continue

                # Last cell (or "Total" column) has the daily total
                # Try to find a numeric value in the row
                total = None
                for cell in reversed(cells[1:]):
                    cell_text = cell.get_text(strip=True).replace(",", "").replace(" ", "")
                    # Match patterns like +123.4, -56.7, 0, (331.1)
                    m = re.match(r'^[+-]?\d+\.?\d*$', cell_text)
                    if m:
                        try:
                            total = float(cell_text)
                            break
                        except ValueError:
                            continue
                    # Handle parentheses as negative
                    m = re.match(r'^\((\d+\.?\d*)\)$', cell_text)
                    if m:
                        try:
                            total = -float(m.group(1))
                            break
                        except ValueError:
                            continue

                if total is not None and parsed_date:
                    flows.append({"date": parsed_date, "total": total})

        if flows:
            # Sort by date
            flows.sort(key=lambda x: datetime.strptime(x["date"], "%d %b %Y"))
            log(f"  ✅ Farside: Extracted {len(flows)} days of data")
            return flows[-10:]  # Keep last 10 days
        else:
            log("  ❌ Farside: Could not parse flow data from tables")
            return None

    except Exception as e:
        log(f"  ❌ Farside parse error: {e}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Source 2: blockchain.news RSS Feed
# ---------------------------------------------------------------------------

def fetch_blockchain_news_rss() -> list[dict] | None:
    """
    Parse blockchain.news RSS feed for BTC ETF flow articles.
    Extract daily flow numbers from article titles/descriptions.
    """
    log("Source 2: blockchain.news RSS feed...")

    # Try multiple RSS URLs
    rss_urls = [
        "https://blockchain.news/rss",
        "https://blockchain.news/Feed/RSS",
    ]

    html = None
    for url in rss_urls:
        html = http_get(url)
        if html and "<item>" in html.lower():
            break
        html = None

    if not html:
        log("  ❌ blockchain.news: Could not fetch RSS feed")
        return None

    try:
        # Parse RSS XML
        root = ET.fromstring(html)
        channel = root.find("channel")
        if channel is None:
            log("  ❌ blockchain.news: No channel in RSS")
            return None

        items = channel.findall("item")
        log(f"  Found {len(items)} RSS items, filtering for ETF flow...")

        # Look for ETF flow related articles
        etf_keywords = [
            r"bitcoin\s+etf\s+(?:flow|inflow|outflow)",
            r"btc\s+etf\s+(?:flow|inflow|outflow)",
            r"spot\s+(?:bitcoin|btc)\s+etf",
            r"etf\s+(?:net\s+)?(?:flow|inflow|outflow)",
            r"bitcoin\s+etf\s+(?:saw|record|post|see|report)",
            r"(?:IBIT|FBTC|GBTC|BITB|ARKB|BTCO|HODL|BRRR|EZBC|BTCW|BTC).*(?:flow|inflow|outflow)",
        ]

        # Flow number patterns: "$123M", "$1.2B", "+$456 million", "($789)", etc.
        flow_patterns = [
            r'\$([+-]?\d+(?:\.\d+)?)\s*[Mm]illion',
            r'\$([+-]?\d+(?:\.\d+)?)\s*[Bb]illion',
            r'([+-]?\d+(?:\.\d+)?)\s*[Mm]\s+(?:inflow|outflow|net)',
            r'(?:inflow|outflow|net\s+(?:flow|inflow|outflow))\s+(?:of\s+)?\$?([+-]?\d+(?:\.\d+)?)\s*[MmBb]',
            r'\(?([+-]?\d+(?:\.\d+)?)\)?\s*[Mm]\s+(?:net|total)',
        ]

        flows = []
        found_articles = []

        for item in items:
            title_el = item.find("title")
            desc_el = item.find("description")
            pubdate_el = item.find("pubDate")

            title = title_el.text if title_el is not None and title_el.text else ""
            desc = ""
            if desc_el is not None and desc_el.text:
                # Strip HTML from description
                desc = re.sub(r'<[^>]+>', '', desc_el.text)

            full_text = f"{title} {desc}"

            # Check if this article is about ETF flows
            is_etf_article = False
            for kw in etf_keywords:
                if re.search(kw, full_text, re.IGNORECASE):
                    is_etf_article = True
                    break

            if not is_etf_article:
                continue

            found_articles.append(title)
            log(f"  📰 ETF article: {title[:80]}...")

            # Try to extract flow numbers
            flow_value = None
            is_outflow = "outflow" in full_text.lower() or "out flow" in full_text.lower()

            for pattern in flow_patterns:
                m = re.search(pattern, full_text, re.IGNORECASE)
                if m:
                    try:
                        val = float(m.group(1))
                        # Convert billions to millions
                        if "billion" in full_text[max(0, m.start()-20):m.end()+20].lower():
                            val *= 1000
                        if is_outflow and val > 0:
                            val = -val
                        flow_value = val
                        break
                    except (ValueError, IndexError):
                        continue

            # Parse publication date
            if pubdate_el is not None and pubdate_el.text:
                try:
                    # RSS date format: "Mon, 15 Jun 2026 04:03:45 GMT"
                    dt = datetime.strptime(pubdate_el.text, "%a, %d %b %Y %H:%M:%S %Z")
                    date_str = dt.strftime("%d %b %Y")
                except ValueError:
                    try:
                        dt = datetime.strptime(pubdate_el.text[:25], "%a, %d %b %Y %H:%M:%S")
                        date_str = dt.strftime("%d %b %Y")
                    except ValueError:
                        continue
            else:
                continue

            if flow_value is not None:
                flows.append({"date": date_str, "total": flow_value})
                log(f"     Extracted: {date_str} = ${flow_value:+,.1f}M")

        if flows:
            # De-duplicate by date (keep most recent extraction)
            seen = {}
            for f in flows:
                seen[f["date"]] = f
            flows = sorted(seen.values(), key=lambda x: datetime.strptime(x["date"], "%d %b %Y"))
            log(f"  ✅ blockchain.news RSS: Extracted {len(flows)} flow data points")
            return flows[-10:]

        if found_articles:
            log(f"  ⚠️ Found {len(found_articles)} ETF articles but couldn't extract flow numbers")
        else:
            log("  ⚠️ No ETF flow articles in current RSS feed")
        return None

    except ET.ParseError as e:
        log(f"  ❌ blockchain.news: XML parse error: {e}")
        return None
    except Exception as e:
        log(f"  ❌ blockchain.news: Error: {e}")
        traceback.print_exc()
        return None


# ---------------------------------------------------------------------------
# Source 3: Farside Data API (JSON endpoint)
# ---------------------------------------------------------------------------

def fetch_farside_api() -> list[dict] | None:
    """
    Try Farside's internal data API endpoints that might bypass Cloudflare.
    They sometimes have JSON endpoints for their chart data.
    """
    log("Source 3: Farside data API endpoints...")

    endpoints = [
        "https://farside.co.uk/wp-json/wp/v2/posts?categories=4&per_page=5",  # BTC ETF category
        "https://farside.co.uk/wp-json/wp/v2/posts?search=bitcoin+etf&per_page=5",
    ]

    for url in endpoints:
        data = http_get_json(url)
        if data and isinstance(data, list) and len(data) > 0:
            log(f"  ✅ Got {len(data)} posts from Farside API")
            # Try to extract flow data from post content
            flows = []
            for post in data:
                content = post.get("content", {}).get("rendered", "")
                title = post.get("title", {}).get("rendered", "")
                date = post.get("date", "")[:10]  # "2026-06-15T..."

                full_text = f"{title} {content}"
                full_text_clean = re.sub(r'<[^>]+>', ' ', full_text)

                # Look for flow numbers
                m = re.search(
                    r'(?:total|net|combined)\s+(?:flow|inflow|outflow)?.*?\$?\(?([+-]?\d+(?:\.\d+)?)\)?\s*[Mm]',
                    full_text_clean, re.IGNORECASE
                )
                if m:
                    try:
                        val = float(m.group(1))
                        parsed_date = parse_date_flexible(date)
                        if parsed_date:
                            flows.append({"date": parsed_date, "total": val})
                    except (ValueError, IndexError):
                        continue

            if flows:
                log(f"  ✅ Farside API: Extracted {len(flows)} data points")
                return flows
            else:
                log(f"  ⚠️ Farside API: Got posts but no flow data")

    log("  ❌ Farside API: No data")
    return None


# ---------------------------------------------------------------------------
# Source 4: News article scraping (broad search)
# ---------------------------------------------------------------------------

def fetch_news_articles() -> list[dict] | None:
    """
    Search for recent BTC ETF flow news from various sources.
    Extract flow numbers from article content.
    """
    log("Source 4: News article scraping...")

    # Try CoinDesk ETF page
    flows = []

    # Source: CoinDesk ETF tag
    coindesk_url = "https://www.coindesk.com/tag/bitcoin-etf/"
    html = http_get(coindesk_url)
    if html and "cloudflare" not in html.lower()[:500]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            articles = soup.find_all("h4") or soup.find_all("h3") or soup.find_all("a")

            for article in articles[:20]:
                text = article.get_text(strip=True)
                if re.search(r'etf.*flow|flow.*etf', text, re.IGNORECASE):
                    log(f"  📰 CoinDesk: {text[:80]}")
                    # Extract numbers
                    m = re.search(r'\$?([+-]?\d+(?:\.\d+)?)\s*[Mm]illion', text)
                    if m:
                        try:
                            val = float(m.group(1))
                            if "outflow" in text.lower():
                                val = -val
                            # Use today's date as approximation
                            flows.append({
                                "date": datetime.now(timezone.utc).strftime("%d %b %Y"),
                                "total": val
                            })
                        except ValueError:
                            continue
        except Exception as e:
            log(f"  CoinDesk parse error: {e}")

    # Source: Decrypt ETF page
    decrypt_url = "https://decrypt.co/tag/etf"
    html = http_get(decrypt_url)
    if html and "cloudflare" not in html.lower()[:500]:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a"):
                text = link.get_text(strip=True)
                if re.search(r'bitcoin.*etf.*(?:flow|inflow|outflow)', text, re.IGNORECASE):
                    log(f"  📰 Decrypt: {text[:80]}")
                    m = re.search(r'\$?([+-]?\d+(?:\.\d+)?)\s*[Mm](?:illion)?', text)
                    if m:
                        try:
                            val = float(m.group(1))
                            if "outflow" in text.lower() or "out" in text.lower():
                                val = -val
                            flows.append({
                                "date": datetime.now(timezone.utc).strftime("%d %b %Y"),
                                "total": val
                            })
                        except ValueError:
                            continue
        except Exception as e:
            log(f"  Decrypt parse error: {e}")

    if flows:
        # De-duplicate
        seen = {}
        for f in flows:
            seen[f["date"]] = f
        flows = sorted(seen.values(), key=lambda x: datetime.strptime(x["date"], "%d %b %Y"))
        log(f"  ✅ News scraping: Extracted {len(flows)} data points")
        return flows[-10:]

    log("  ❌ News scraping: No ETF flow data found")
    return None


# ---------------------------------------------------------------------------
# Source 5: Static/Hardcoded recent data (last resort)
# ---------------------------------------------------------------------------

def fetch_static_fallback() -> list[dict] | None:
    """
    Last resort: Return None (we don't hardcode stale data).
    The dashboard will show 'No data available' gracefully.
    """
    log("Source 5: Static fallback — not available (deliberately)")
    return None


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    log("=" * 60)
    log("BTC ETF Flow Data Collector")
    log(f"Time: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    log("=" * 60)

    # Check cache first
    if is_cache_valid():
        try:
            with open(OUTPUT_PATH) as f:
                data = json.load(f)
            if data.get("card") == "A6" and not data.get("error"):
                log("Using cached data (still fresh)")
                return
        except (json.JSONDecodeError, OSError):
            pass

    # Try sources in order
    sources = [
        ("Farside.co.uk (scrape)", fetch_farside),
        ("blockchain.news (RSS)", fetch_blockchain_news_rss),
        ("Farside (WP-API)", fetch_farside_api),
        ("News articles (broad)", fetch_news_articles),
        ("Static fallback", fetch_static_fallback),
    ]

    flows = None
    source_name = ""

    for name, fetcher in sources:
        try:
            result = fetcher()
            if result and len(result) > 0:
                flows = result
                source_name = name
                break
        except Exception as e:
            log(f"  ❌ {name} failed with exception: {e}")
            traceback.print_exc()
            continue

    # Build and write output
    if flows:
        data = build_output(flows, source=source_name)
        write_output(data)
    else:
        log("⚠️ All sources failed. Writing error placeholder.")
        # Check if we have stale data we can extend
        stale_data = None
        if os.path.exists(OUTPUT_PATH):
            try:
                with open(OUTPUT_PATH) as f:
                    stale_data = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass

        if stale_data and stale_data.get("card") == "A6" and not stale_data.get("error"):
            # Keep stale data but mark it as old
            stale_data["lag_warning"] = f"⚠️ Data is stale (last updated: {stale_data.get('timestamp', 'unknown')}). All sources failed."
            stale_data["confirmed"] = False
            stale_data["source"] = stale_data.get("source", "") + " (STALE - refresh failed)"
            write_output(stale_data)
            log("  Kept existing stale data with warning")
        else:
            # Write error placeholder
            error_data = {
                "card": "A6",
                "error": "all_sources_failed",
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "source": "none",
                "direction": "flat",
                "total_flow_display": "—",
                "streak_7d_display": "—",
                "streak_label": "—",
                "signal_display": "⚠️ Data Unavailable",
                "data_date": "—",
                "confirmed": False,
                "lag_warning": "ETF flow data sources are temporarily unavailable",
                "confirmed_date_note": "Data unavailable",
                "flows": [],
                "latest": {},
                "weekly_net": 0,
            }
            write_output(error_data)

    log("Done.")


if __name__ == "__main__":
    main()
