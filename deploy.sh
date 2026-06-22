#!/bin/bash
# Pipeline Dashboard V2 — Standalone Collect + Deploy
# Produces ALL data + collects + deploys. Zero external cron dependencies.
set -euo pipefail

# Cron-safe environment
export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
SITE="/home/maswilee/pipeline-dashboard V2"
PYTHON="/home/maswilee/.hermes/hermes-agent/.venv/bin/python3"
ERROR_LOG="/tmp/pipeline_deploy_errors.log"
PASSED=0
FAILED=0

# Twitter/X auth for social_pulse collector
export TWITTER_AUTH_TOKEN="010b751cd4cfd5684b484c4f47bb557555a3b7d8"
export TWITTER_CT0="5a9b059629af87129dc0dce94f1835b0083220b605294c790ee5f12b2cef77e704328b670957521593e6c671b6131ef9be60cd6f4aea9e349b6a30003f10273c47ef208d10eed9d3065d0e2392ae5431"

# Lockfile — flock prevents race conditions
exec 9>/tmp/pipeline-deploy.lock
flock -n 9 || { echo "⚠️  Another deploy is running — skipping"; exit 0; }

cd "$SITE"

echo "═══════════════════════════════════════════"
echo "Pipeline Dashboard V2 Deploy — $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "═══════════════════════════════════════════"

# ─── Helper: run a pipeline script with error tracking ───
run_pipeline() {
    local label="$1"
    local script="$2"
    echo -n "  $label ... "
    # If script arg contains a space, it has its own interpreter
    if [[ "$script" == *" "* ]]; then
        cmd="$script"
    else
        cmd="$PYTHON $script"
    fi
    if $cmd >> "$ERROR_LOG" 2>&1; then
        echo "✅"
        PASSED=$((PASSED + 1))
    else
        echo "❌ FAILED"
        FAILED=$((FAILED + 1))
        echo "  ─── $label error ───" >> "${ERROR_LOG}.append"
        tail -5 "$ERROR_LOG" >> "${ERROR_LOG}.append"
    fi
    : > "$ERROR_LOG"  # clear for next
}

# ─── 0. Test suites ───
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

# ─── 1. Data Production Phase — produce ALL /tmp/btc_*.json files ───
echo "── Data Production Phase ──"

# External project scripts (live in ~/btc-*/ directories)
run_pipeline "realtime"      ~/btc-onchain/realtime_proxies.py
run_pipeline "macro"         ~/btc-macro/macro_snapshot.py
run_pipeline "risk_assets"   ~/btc-risk/risk_assets.py
run_pipeline "risk_monitor"  ~/btc-risk/risk_monitor.py
run_pipeline "session"       ~/btc-sessions/session_brief.py
run_pipeline "onchain_mvrv"  ~/btc-onchain/bgeometrics_mvrv.py
run_pipeline "news"          ~/btc-news/pipeline.py
run_pipeline "cycle"         ~/btc-news/cycle_pipeline.py
run_pipeline "vol_profile"   ~/btc-volume-profile/scripts/profile.py
run_pipeline "chart_pat"     ~/btc-chart-patterns/scripts/main.py
run_pipeline "3candle"       ~/btc-3candle-confluence/scripts/main.py
run_pipeline "polymarket"    ~/btc-polymarket/scripts/markets.py

# Internal scripts (now live in V2/scripts/)
run_pipeline "market_data"   "$SITE/scripts/fetch_market_data.py"
run_pipeline "btc_dist"      "$SITE/scripts/fetch_btc_distribution.py"
run_pipeline "skew"          "$SITE/scripts/fetch_skew.py"
run_pipeline "cot"           "/usr/bin/python3 $SITE/scripts/fetch_cot.py"
run_pipeline "options_full"  "/usr/bin/python3 $SITE/scripts/fetch_options_full.py"
run_pipeline "gamma"         "python3 $SITE/scripts/fetch_gamma.py"
run_pipeline "etf_flow"      "$SITE/scripts/fetch_etf_flow.py"
run_pipeline "gate0"         "$SITE/scripts/fetch_gate0.py"
run_pipeline "sr_bands"      "$SITE/scripts/fetch_sr_bands.py"
run_pipeline "synthesis"     "$SITE/scripts/fetch_synthesis.py"
run_pipeline "v7_images"     "$SITE/scripts/capture_v7_images.py"

echo "── Production complete: $PASSED passed, $FAILED failed ──"

# ─── 2. Run collector ───
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

# ─── 3. Resolve predictions ───
echo "── Resolving predictions ──"
if ! $PYTHON scripts/resolve_predictions.py 2>&1; then
    echo "⚠️  Resolution engine failed — continuing deploy with stale resolution"
fi

# ─── 4. Check run_status ───
RUN_STATUS=$($PYTHON -c "import json; print(json.load(open('data/run_status.json')).get('status','unknown'))" 2>/dev/null || echo "missing")
if [ "$RUN_STATUS" != "success" ]; then
    echo "❌ run_status.json reports '$RUN_STATUS' — aborting deploy"
    echo "CRASH_ALERT:run_status_${RUN_STATUS}:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi

# ─── 5. Validate generated JSON ───
if ! $PYTHON -m json.tool data/meta.json >/dev/null 2>&1; then
    echo "❌ Generated meta.json is invalid — aborting deploy"
    echo "CRASH_ALERT:invalid_meta_json:$(date -u '+%Y-%m-%d %H:%M UTC')" >> /tmp/pipeline_alerts.log
    exit 1
fi

# ─── 6. Stage + commit + push ───
echo "── Checking for changes ──"
git add data/*.json data/run_status.json assets/v7_long.png assets/v7_short.png assets/styles.css assets/nav.js assets/favicon.png assets/logo.png assets/social-card.png index.html dashboard/index.html methodology/index.html glossary/index.html about/index.html faq/index.html contact/index.html research/ compare/ privacy/index.html terms/index.html verdicts/ track-record/ docs/ events-and-disruptions/ sitemap.xml robots.txt manifest.json scripts/ 2>/dev/null || true
if git diff --cached --quiet; then
    echo "ℹ️  No data changes — skipping deploy"
    exit 0
fi

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

# ─── 7. Crash alert delivery ───
ALERT_LOG="/tmp/pipeline_alerts.log"
if [ -f "$ALERT_LOG" ]; then
    NEW_ALERTS=$(grep "CRASH_ALERT:" "$ALERT_LOG" | tail -1 || true)
    if [ -n "$NEW_ALERTS" ]; then
        echo "$NEW_ALERTS" > /tmp/btc_pipeline_crash_alert.txt
    fi
    : > "$ALERT_LOG"
fi

echo "═══════════════════════════════════════════"
echo "Done — $(date -u '+%H:%M UTC')"
