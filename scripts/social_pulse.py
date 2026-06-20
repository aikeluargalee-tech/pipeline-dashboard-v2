#!/usr/bin/env python3
"""
BTC Pipeline Social Pulse Collector
Fetches social sentiment from Reddit, Twitter, Xueqiu via Agent Reach CLIs.

Output: data/social_pulse.json
Usage: python3 scripts/social_pulse.py
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

OUTPUT_PATH = Path(__file__).parent.parent / "data" / "social_pulse.json"
BIN_PATH = os.path.expanduser("~/.local/bin")
ENV = {**os.environ, "PATH": f"{BIN_PATH}:{os.environ.get('PATH', '')}"}


def ts():
    return datetime.now(timezone.utc).isoformat()


def run_cmd(cmd, timeout=25):
    """Run a CLI command, return (ok, parsed_json_or_error)."""
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env=ENV
        )
        if result.returncode != 0:
            return False, f"exit={result.returncode}: {result.stderr[:200]}"
        data = json.loads(result.stdout)
        if data.get("ok"):
            return True, data.get("data", data)
        return False, data.get("error", {}).get("message", str(data)[:200])
    except subprocess.TimeoutExpired:
        return False, "timeout"
    except json.JSONDecodeError as e:
        return False, f"json_parse_error: {str(e)[:100]}"
    except Exception as e:
        return False, str(e)[:200]


def collect_reddit():
    """Fetch top r/Bitcoin posts from past day."""
    ok, data = run_cmd([
        "rdt", "search", "bitcoin", "-r", "Bitcoin",
        "-n", "10", "--json", "--compact", "-t", "day"
    ])
    if ok:
        items = []
        for post in (data if isinstance(data, list) else [])[:8]:
            items.append({
                "id": post.get("id", ""),
                "title": post.get("title", ""),
                "author": post.get("author", ""),
                "score": post.get("score", 0),
                "num_comments": post.get("num_comments", 0),
                "url": post.get("url", ""),
                "selftext": (post.get("selftext", "") or "")[:200],
                "created_utc": post.get("created_utc"),
            })
        return {"status": "ok", "source": "r/Bitcoin", "count": len(items), "items": items}
    return {"status": "error", "source": "r/Bitcoin", "count": 0, "items": [], "error": data}


def collect_twitter():
    """Fetch BTC tweets (requires TWITTER_AUTH_TOKEN + TWITTER_CT0 env vars)."""
    if not os.environ.get("TWITTER_AUTH_TOKEN") or not os.environ.get("TWITTER_CT0"):
        return {"status": "no_auth", "source": "Twitter/X", "count": 0, "items": [],
                "error": "Set TWITTER_AUTH_TOKEN and TWITTER_CT0 env vars"}

    ok, data = run_cmd([
        "twitter", "search", "Bitcoin", "--json", "-n", "10",
        "--exclude", "retweets", "--lang", "en", "-t", "latest"
    ], timeout=30)
    if ok and isinstance(data, (dict, list)):
        items = []
        tweets = data if isinstance(data, list) else data.get("tweets", data.get("data", []))  # type: ignore[union-attr]
        for t in (tweets if isinstance(tweets, list) else [])[:8]:
            author = t.get("author", {})
            metrics = t.get("metrics", {})
            items.append({
                "id": t.get("id", ""),
                "text": (t.get("text", "") or "")[:200],
                "user": author.get("screenName", ""),
                "likes": metrics.get("likes", 0),
                "retweets": metrics.get("retweets", 0),
            })
        return {"status": "ok", "source": "Twitter/X", "count": len(items), "items": items}
    return {"status": "error", "source": "Twitter/X", "count": 0, "items": [], "error": data}


def collect_xueqiu():
    """Xueqiu stub — CLI not yet installed."""
    return {"status": "not_installed", "source": "Xueqiu", "count": 0, "items": [],
            "error": "xueqiu CLI not installed"}


def main():
    print("[social_pulse] Collecting social sentiment...")

    reddit = collect_reddit()
    print(f"[social_pulse] Reddit: {reddit['status']} ({reddit['count']} posts)")

    twitter = collect_twitter()
    print(f"[social_pulse] Twitter: {twitter['status']} ({twitter['count']} tweets)")

    xueqiu = collect_xueqiu()
    print(f"[social_pulse] Xueqiu: {xueqiu['status']}")

    output = {
        "timestamp": ts(),
        "reddit": reddit,
        "twitter": twitter,
        "xueqiu": xueqiu,
    }

    os.makedirs(OUTPUT_PATH.parent, exist_ok=True)
    tmp = str(OUTPUT_PATH) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    os.replace(tmp, str(OUTPUT_PATH))
    print(f"[social_pulse] Written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
