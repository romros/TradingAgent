import unittest

from aggregate_ostium_execution_snapshots import aggregate, percentile


def snapshot(at, opened, spread, slippage, pair_id="10", pair_from="US500", pair_to="USD"):
    return {
        "captured_at": at,
        "instrument": {"pair_id": pair_id, "pair_from": pair_from,
                       "pair_to": pair_to, "category": "index"},
        "market_state": {"is_market_open": opened},
        "fees": {"open_fee_bps": 1, "close_fee_bps": 0,
                 "rollover_long_pct_per_8h": .01, "rollover_short_pct_per_8h": -.02},
        "limits": {"min_notional_usd": 5, "max_leverage": 100,
                   "overnight_max_leverage": 0},
        "quote": {"spread_bps": spread},
        "simulated_slippage": {
            "long": [{"notional_usd": 200, "slippage_bps": slippage}],
            "short": [{"notional_usd": 200, "slippage_bps": slippage + 1}],
        },
    }


class AggregateExecutionSnapshotsTest(unittest.TestCase):
    def test_percentile_interpolates(self):
        self.assertEqual(percentile([1, 2, 3], .5), 2)
        self.assertEqual(percentile([], .95), None)

    def test_closed_samples_do_not_satisfy_gate(self):
        result = aggregate([snapshot("2026-08-08T10:00:00Z", False, 2, 1)],
                           min_open_samples=1, min_days=1, min_utc_hours=1)
        self.assertEqual(result["open_market_snapshots"], 0)
        self.assertEqual(result["gate"]["execution_economics"], "INSUFFICIENT_OPEN_MARKET_EVIDENCE")

    def test_diverse_open_samples_pass(self):
        rows = [
            snapshot("2026-08-08T10:00:00Z", True, 1, .5),
            snapshot("2026-08-09T11:00:00Z", True, 3, 1.5),
        ]
        result = aggregate(rows, min_open_samples=2, min_days=2, min_utc_hours=2)
        self.assertEqual(result["spread_bps"]["p50"], 2)
        self.assertEqual(result["slippage_by_notional"]["200"]["long"]["p50_bps"], 1)
        self.assertEqual(result["instrument"]["pair_id"], "10")
        self.assertEqual(result["fees"]["open_fee_bps"]["p95"], 1)
        self.assertEqual(result["gate"]["execution_economics"], "PASS")

    def test_generic_pair_is_inferred_and_mixed_pairs_are_rejected(self):
        usd_jpy = snapshot("2026-08-08T10:00:00Z", True, 1, .5,
                           pair_id="4", pair_from="USD", pair_to="JPY")
        result = aggregate([usd_jpy], min_open_samples=1, min_days=1, min_utc_hours=1)
        self.assertEqual(result["instrument"]["pair_id"], "4")
        self.assertEqual(result["instrument"]["pair_from"], "USD")
        with self.assertRaisesRegex(ValueError, "exactly one pair_id"):
            aggregate([usd_jpy, snapshot("2026-08-08T11:00:00Z", True, 1, .5)])


if __name__ == "__main__":
    unittest.main()
