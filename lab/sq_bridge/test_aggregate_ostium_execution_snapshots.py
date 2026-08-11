import hashlib
import unittest

from aggregate_ostium_execution_snapshots import aggregate, percentile


def snapshot(at, opened, spread, slippage, pair_id="10", pair_from="US500", pair_to="USD"):
    return {
        "captured_at": at,
        "instrument": {"pair_id": pair_id, "pair_from": pair_from,
                       "pair_to": pair_to, "category": "index"},
        "market_state": {"is_market_open": opened},
        "source": {"raw_sha256": hashlib.sha256(at.encode()).hexdigest(),
                   "package": "@ostium/builder-sdk", "version": "0.7.0",
                   "mode": "read-only", "builder_fee_bps": 0},
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
        self.assertEqual(
            result["roundtrip_proxy_bps_by_notional"]["200"]["direction_neutral"]["p50"],
            4,
        )
        self.assertEqual(
            result["roundtrip_proxy_bps_by_notional"]["200"]["long"]["p50"], 4)
        self.assertEqual(
            result["roundtrip_proxy_bps_by_notional"]["200"]["short"]["p50"], 4)
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

    def test_duplicates_and_clustered_captures_cannot_inflate_gate(self):
        first = snapshot("2026-08-08T10:00:00Z", True, 1, .5)
        duplicate = dict(first)
        clustered = snapshot("2026-08-08T10:05:00Z", True, 99, 99)
        independent = snapshot("2026-08-08T10:15:00Z", True, 3, 1.5)
        result = aggregate(
            [first, duplicate, clustered, independent],
            min_open_samples=3, min_days=1, min_utc_hours=1)
        self.assertEqual(result["raw_open_market_snapshots"], 4)
        self.assertEqual(result["open_market_snapshots"], 2)
        self.assertEqual(result["gate"]["checks"]["open_samples"]["actual"], 2)
        self.assertEqual(result["gate"]["execution_economics"],
                         "INSUFFICIENT_OPEN_MARKET_EVIDENCE")
        self.assertEqual(result["independence_filter"], {
            "minimum_sample_spacing_seconds": 900,
            "exact_duplicate_snapshots_ignored": 1,
            "too_close_snapshots_ignored": 1,
        })
        self.assertEqual(result["spread_bps"]["p50"], 2)

    def test_same_timestamp_with_conflicting_payload_fails_closed(self):
        first = snapshot("2026-08-08T10:00:00Z", True, 1, .5)
        conflict = snapshot("2026-08-08T10:00:00Z", True, 2, .5)
        with self.assertRaisesRegex(ValueError, "conflicting snapshots"):
            aggregate([first, conflict])

    def test_reused_or_missing_raw_hash_cannot_count_as_independent(self):
        first = snapshot("2026-08-08T10:00:00Z", True, 1, .5)
        second = snapshot("2026-08-08T11:00:00Z", True, 2, 1)
        second["source"] = first["source"]
        with self.assertRaisesRegex(ValueError, "reuse a raw SHA-256"):
            aggregate([first, second])
        del first["source"]
        with self.assertRaisesRegex(ValueError, "requires a lowercase raw SHA-256"):
            aggregate([first])

    def test_source_version_or_mode_drift_cannot_be_mixed(self):
        first = snapshot("2026-08-08T10:00:00Z", True, 1, .5)
        second = snapshot("2026-08-08T11:00:00Z", True, 2, 1)
        second["source"]["version"] = "0.8.0"
        with self.assertRaisesRegex(ValueError, "source contract drift"):
            aggregate([first, second])


if __name__ == "__main__":
    unittest.main()
