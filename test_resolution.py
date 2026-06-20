#!/usr/bin/env python3
"""
Test suite for resolve_predictions.py.
Uses unittest and mocks to verify outcome calculation and stats aggregation.
"""
import sys
import os
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add current dir to path
sys.path.insert(0, str(Path(__file__).parent))

import scripts.resolve_predictions as r

class TestResolution(unittest.TestCase):
    def setUp(self):
        # Setup paths
        self.predictions_backup = r.PREDICTIONS_PATH
        self.stats_backup = r.STATS_PATH
        self.summary_backup = r.SUMMARY_PATH
        self.confidence_backup = r.CONFIDENCE_PATH

        r.PREDICTIONS_PATH = "/tmp/test_predictions.json"
        r.STATS_PATH = "/tmp/test_signal_stats.json"
        r.SUMMARY_PATH = "/tmp/test_track_summary.json"
        r.CONFIDENCE_PATH = "/tmp/test_confidence.json"

        # Clear temp files
        for path in [r.PREDICTIONS_PATH, r.STATS_PATH, r.SUMMARY_PATH, r.CONFIDENCE_PATH]:
            if os.path.exists(path):
                os.remove(path)

    def tearDown(self):
        # Restore paths
        r.PREDICTIONS_PATH = self.predictions_backup
        r.STATS_PATH = self.stats_backup
        r.SUMMARY_PATH = self.summary_backup
        r.CONFIDENCE_PATH = self.confidence_backup

    @patch('scripts.resolve_predictions.fetch_klines')
    def test_resolve_regime_changes(self, mock_fetch):
        # 1d horizon (24h) passed, others pending
        # Created at 25 hours ago
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        created_at = (now - timedelta(hours=25)).isoformat()

        mock_preds = {
            "predictions": [
                {
                    "id": "test_regime_1",
                    "type": "regime_change",
                    "created_at": created_at,
                    "btc_price_at_call": 60000.0,
                    "direction": "bullish",
                    "gate0_status": "PROCEED",
                    "regime_label": "CAUTIOUS BULL",
                    "outcomes": {"1d": None, "7d": None, "30d": None},
                    "resolved": False
                }
            ]
        }

        with open(r.PREDICTIONS_PATH, "w") as f:
            json.dump(mock_preds, f, indent=2)

        # Mock fetch_klines for 1d: returns klines where last close is 61000 (direction correct)
        # format: [time, open, high, low, close, volume, ...]
        mock_fetch.return_value = [
            [0, "60000", "62000", "59000", "61000", "100"]
        ]

        r.resolve_predictions()

        # Load updated predictions
        with open(r.PREDICTIONS_PATH) as f:
            updated = json.load(f)

        pred = updated["predictions"][0]
        self.assertIsNotNone(pred["outcomes"]["1d"])
        self.assertTrue(pred["outcomes"]["1d"]["direction_correct"])
        self.assertEqual(pred["outcomes"]["1d"]["price_then"], 61000.0)
        self.assertIsNone(pred["outcomes"]["7d"])
        self.assertFalse(pred["resolved"])

    @patch('scripts.resolve_predictions.fetch_klines')
    def test_resolve_trading_signals_win(self, mock_fetch):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        created_at = (now - timedelta(hours=5)).isoformat()

        mock_preds = {
            "predictions": [
                {
                    "id": "test_sig_1",
                    "type": "trading_signal",
                    "signal_name": "BREAKOUT_DETECTED",
                    "created_at": created_at,
                    "btc_price_at_call": 60000.0,
                    "direction": "bullish",
                    "entry": 60000.0,
                    "stop_loss": 59000.0,
                    "target": 62000.0,
                    "confidence": "HIGH",
                    "resolved": False
                }
            ]
        }

        with open(r.PREDICTIONS_PATH, "w") as f:
            json.dump(mock_preds, f, indent=2)

        # First candle is sideways, second hits target (62500 high)
        mock_fetch.return_value = [
            [0, "60000", "60500", "59500", "60200", "10"],
            [3600000, "60200", "62500", "60100", "62100", "10"]
        ]

        r.resolve_predictions()

        with open(r.PREDICTIONS_PATH) as f:
            updated = json.load(f)

        pred = updated["predictions"][0]
        self.assertTrue(pred["resolved"])
        self.assertEqual(pred["outcomes"]["outcome"], "win")
        self.assertEqual(pred["outcomes"]["exit_price"], 62000.0)

    @patch('scripts.resolve_predictions.fetch_klines')
    def test_resolve_trading_signals_loss(self, mock_fetch):
        from datetime import datetime, timezone, timedelta
        now = datetime.now(timezone.utc)
        created_at = (now - timedelta(hours=5)).isoformat()

        mock_preds = {
            "predictions": [
                {
                    "id": "test_sig_2",
                    "type": "trading_signal",
                    "signal_name": "BREAKOUT_DETECTED",
                    "created_at": created_at,
                    "btc_price_at_call": 60000.0,
                    "direction": "bullish",
                    "entry": 60000.0,
                    "stop_loss": 59000.0,
                    "target": 62000.0,
                    "confidence": "HIGH",
                    "resolved": False
                }
            ]
        }

        with open(r.PREDICTIONS_PATH, "w") as f:
            json.dump(mock_preds, f, indent=2)

        # Hits stop loss (58500 low)
        mock_fetch.return_value = [
            [0, "60000", "60500", "58500", "59000", "10"]
        ]

        r.resolve_predictions()

        with open(r.PREDICTIONS_PATH) as f:
            updated = json.load(f)

        pred = updated["predictions"][0]
        self.assertTrue(pred["resolved"])
        self.assertEqual(pred["outcomes"]["outcome"], "loss")
        self.assertEqual(pred["outcomes"]["exit_price"], 59000.0)

if __name__ == "__main__":
    unittest.main()
