import unittest

from normalize_ostium_execution_snapshot import normalize


class NormalizeOstiumSnapshotTest(unittest.TestCase):
    def fixture(self):
        return {
            "capturedAt": "2026-08-08T12:00:00Z",
            "requestedNotionalsUsd": ["10", "200"],
            "source": {"package": "@ostium/builder-sdk", "version": "0.7.0",
                       "mode": "read-only", "builderFeeBps": 0},
            "pair": {
                "pairId": "10", "pairFrom": "US500", "pairTo": "USD", "category": "Indices",
                "minSz": "0.001", "minNtl": "10", "maxBSz": "100", "maxSSz": "90",
                "maxLeverage": 200, "overnightMaxLeverage": 50,
                "openFee": 3, "closeFee": 0, "midPx": "5000", "bidPx": "4999.5", "askPx": "5000.5",
                "rolloverRate": {"long": "0.001", "short": "-0.001"},
                "rolloverFeePerBlock": "1", "isMarketOpen": True,
                "isDayTradingClosed": False, "secondsToToggleIsDayTradingClosed": 60,
            },
            "simulatedSlippage": {
                "long": [{"ntl": "200", "slippage": "0.02"}, {"ntl": "10", "slippage": "0.01"}],
                "short": [{"ntl": "10", "slippage": "0.03"},
                          {"ntl": "200", "slippage": "0.04"}],
            },
        }

    def test_normalizes_and_sorts(self):
        result = normalize(self.fixture(), source_sha256="abc")
        self.assertAlmostEqual(result["quote"]["spread_bps"], 2.0)
        self.assertEqual(result["limits"]["max_leverage"], 200.0)
        self.assertEqual(result["simulated_slippage"]["long"][0]["notional_usd"], 10.0)
        self.assertEqual(result["simulated_slippage"]["long"][0]["slippage_bps"], 1.0)
        self.assertTrue(result["limits"]["overnight_zero_means_unrestricted"])
        self.assertEqual(result["source"]["raw_sha256"], "abc")
        self.assertEqual(result["source"]["builder_fee_bps"], 0)

    def test_rejects_non_read_only(self):
        payload = self.fixture()
        payload["source"]["mode"] = "self-and-self"
        with self.assertRaisesRegex(ValueError, "read-only"):
            normalize(payload)

    def test_rejects_unknown_or_unversioned_source_package(self):
        payload = self.fixture()
        payload["source"]["package"] = "lookalike"
        with self.assertRaisesRegex(ValueError, "source package"):
            normalize(payload)
        payload = self.fixture()
        payload["source"]["version"] = ""
        with self.assertRaisesRegex(ValueError, "version"):
            normalize(payload)

    def test_rejects_builder_surcharge_in_research_capture(self):
        payload = self.fixture()
        payload["source"]["builderFeeBps"] = 1
        with self.assertRaisesRegex(ValueError, "builderFeeBps=0"):
            normalize(payload)

    def test_rejects_bad_quote_order(self):
        payload = self.fixture()
        payload["pair"]["askPx"] = "4990"
        with self.assertRaisesRegex(ValueError, "ordering"):
            normalize(payload)

    def test_normalizes_an_explicit_non_spx_pair_only_when_expected(self):
        payload = self.fixture()
        payload["pair"].update({"pairId": "2", "pairFrom": "USD", "pairTo": "JPY"})
        result = normalize(payload, expected_pair=("USD", "JPY"))
        self.assertEqual(result["instrument"]["pair_from"], "USD")
        with self.assertRaisesRegex(ValueError, "SPX/USD"):
            normalize(payload)

    def test_rejects_negative_duplicate_or_missing_slippage_points(self):
        payload = self.fixture()
        payload["simulatedSlippage"]["long"][0]["slippage"] = "-0.01"
        with self.assertRaisesRegex(ValueError, "non-negative"):
            normalize(payload)
        payload = self.fixture()
        payload["simulatedSlippage"]["short"].pop()
        with self.assertRaisesRegex(ValueError, "do not match"):
            normalize(payload)


if __name__ == "__main__":
    unittest.main()
