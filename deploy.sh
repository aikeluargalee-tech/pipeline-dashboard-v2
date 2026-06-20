#!/bin/bash
# Pipeline Dashboard — Hourly Collect + Deploy
# Called by cron every hour. Runs collector, pushes to GitHub Pages.
set -euo pipefail

# Cron-safe environment
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
SITE="/home/maswilee/pipeline-dashboard V2"
PYTHON="/home/maswilee/.hermes/hermes-agent/.venv/bin/python3"

# Twitter/X auth for social_pulse collector
export TWITTER_AUTH_TOKEN="010b751cd4cfd5684b484c4f47bb557555a3b7d8"
export TWITTER_CT0="5a9b059629af87129dc0dce94f1835b0083220b605294c790ee5f12b2cef77e704328b670957521593e6c671b6131ef9be60cd6f4aea9e349b6a30003f10273c47ef208d10eed9d3065d0e2392ae5431"

# Lockfile — flock prevents race conditions
exec 9>/tmp/pipeline-deploy.lock
flock -n 9 || { echo "⚠️  Another deploy is running — skipping"; exit 0; }

cd "$SITE"

echo "═══════════════════════════════════════════"
echo "Pipeline Dashboard Deploy — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════"

# 0.5 — Run test suites before collecting
echo "── Running test suites ──"
if ! $PYTHON test_collect.py 2>&1; then
    echo "❌ collect test suite failed — aborting deploy"
    echo "CRASH_ALERT:collect_test_failed:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi
if ! $PYTHON test_detect_only.py 2>&1; then
    echo "❌ detect_only test suite failed — aborting deploy"
    echo "CRASH_ALERT:detect_test_failed:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi
echo "✅ Tests passed"

# 1. Run collector (95s timeout — subprocess calls inside have their own timeouts)
echo "── Collecting data ──"
COLLECT_OUTPUT=$(timeout 95 $PYTHON collect.py 2>&1) || COLLECT_EXIT=$?
COLLECT_EXIT=${COLLECT_EXIT:-0}
echo "$COLLECT_OUTPUT"

if [ $COLLECT_EXIT -eq 124 ]; then
    echo "⚠️  Collector timed out (95s) — deploying whatever data exists"
elif [ $COLLECT_EXIT -ne 0 ]; then
    echo "❌ Collector failed — aborting deploy"
    echo "CRASH_ALERT:collector_crashed:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
else
    echo "✅ Data collected"
fi

# 1.3 — Resolve predictions / signals (best-effort, warning on failure)
echo "── Resolving predictions ──"
if ! $PYTHON scripts/resolve_predictions.py 2>&1; then
    echo "⚠️  Resolution engine failed — continuing deploy with stale resolution"
fi

# 1.5 — Check run_status for collector-level failures
RUN_STATUS=$($PYTHON -c "import json; print(json.load(open('data/run_status.json')).get('status','unknown'))" 2>/dev/null || echo "missing")
if [ "$RUN_STATUS" != "success" ]; then
    echo "❌ run_status.json reports '$RUN_STATUS' — aborting deploy"
    echo "CRASH_ALERT:run_status_${RUN_STATUS}:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi

# 2. Validate generated JSON
if ! $PYTHON -m json.tool data/meta.json >/dev/null 2>&1; then
    echo "❌ Generated meta.json is invalid — aborting deploy"
    echo "CRASH_ALERT:invalid_meta_json:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi

# 3. Stage only expected files (no -A)
echo "── Checking for changes ──"
git add data/*.json data/run_status.json assets/v7_long.png assets/v7_short.png assets/styles.css assets/nav.js assets/favicon.png assets/logo.png assets/social-card.png index.html dashboard/index.html methodology/index.html glossary/index.html about/index.html faq/index.html contact/index.html research/ compare/ privacy/index.html terms/index.html verdicts/ track-record/ docs/ events-and-disruptions/ sitemap.xml robots.txt manifest.json 2>/dev/null || true
if git diff --cached --quiet; then
    echo "ℹ️  No data changes — skipping deploy"
    exit 0
fi

# 4. Commit + push (with timeout)
echo "── Deploying ──"
if ! git commit -m "Auto-deploy: $(date -u '+%Y-%m-%d %H:%M UTC')" --quiet; then
    echo "❌ Git commit failed"
    echo "CRASH_ALERT:git_commit_failed:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi
if ! timeout 60 git push origin main --quiet 2>&1; then
    echo "❌ Git push failed or timed out (60s) — local commit preserved"
    echo "CRASH_ALERT:git_push_failed:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi
echo "✅ Deployed to GitHub Pages"

# 5. Crash alert — check if any CRASH_ALERT was logged and deliver
ALERT_LOG="/tmp/pipeline_alerts.log"
if [ -f "$ALERT_LOG" ]; then
    NEW_ALERTS=$(grep "CRASH_ALERT:" "$ALERT_LOG" | tail -1 || true)
    if [ -n "$NEW_ALERTS" ]; then
        # Write to a dedicated alert file that cron can pick up
        echo "$NEW_ALERTS" > /tmp/btc_pipeline_crash_alert.txt
    fi
    # Clear processed alerts so stale crashes don't re-report forever
    : > "$ALERT_LOG"
fi

echo "═══════════════════════════════════════════"
echo "Done — $(date -u '+%H:%M UTC')"
