import importlib.util
import json
import unittest
from pathlib import Path

HERE = Path(__file__).parents[1] / "projects" / "wolfpack"
spec = importlib.util.spec_from_file_location("wolfpack", HERE / "wolfpack.py")
wolfpack = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wolfpack)


class WolfpackTest(unittest.TestCase):
    def setUp(self):
        self.pack = json.loads((HERE / "pack.json").read_text())
        self.council = json.loads((HERE / "council.json").read_text())

    def test_sparse_data_cannot_become_signal(self):
        result = wolfpack.build_brief([], [], self.pack, self.council)
        self.assertEqual(result["criticality_ceiling"], "C1")
        self.assertEqual(result["decision"], "OBSERVE")
        self.assertFalse(result["live_trading_authorized"])

    def test_coverage_only_opens_hypothesis_not_paper_trade(self):
        diary = [{"captured_at": f"2026-08-{day:02d}T{hour:02d}:00:00Z",
                  "sources": {"ostium": [{}], "hyperliquid_xyz": [{}],
                              "hyperliquid_mkts": [{}]}, "errors": {}}
                 for day in range(1, 21) for hour in range(15)]
        follows = [{"pair": "XAU/USD", "action": "Close",
                    "wallet_sha256": f"wallet-{index % 2}",
                    "detection_latency_seconds": 600} for index in range(30)]
        result = wolfpack.build_brief(diary, follows, self.pack, self.council)
        self.assertEqual(result["criticality_ceiling"], "C2")
        self.assertEqual(result["decision"], "READY_TO_FORM_HYPOTHESES")
        self.assertFalse(result["live_trading_authorized"])

    def test_liquidation_keeps_ceiling_low(self):
        diary = [{"captured_at": f"2026-08-{day:02d}T{hour:02d}:00:00Z",
                  "sources": {"ostium": [{}], "hyperliquid_xyz": [{}],
                              "hyperliquid_mkts": [{}]}, "errors": {}}
                 for day in range(1, 21) for hour in range(15)]
        follows = [{"pair": "US500/USD", "action": "Liquidation",
                    "wallet_sha256": f"wallet-{index % 2}", "detection_latency_seconds": 10}
                   for index in range(30)]
        result = wolfpack.build_brief(diary, follows, self.pack, self.council)
        self.assertEqual(result["criticality_ceiling"], "C1")
        self.assertIn("liquidations", " ".join(result["promotion_blockers"]))

    def test_crypto_is_part_of_the_open_universe(self):
        follows = [{"pair": "BTC/USD", "action": "Close",
                    "wallet_sha256": "crypto-wallet", "detection_latency_seconds": 420}]
        result = wolfpack.build_brief([], follows, self.pack, self.council)
        self.assertEqual(result["coverage"]["eligible_follow_events"], 1)
        self.assertEqual(result["coverage"]["eligible_closed_signals"], 1)
        self.assertEqual(result["activity"]["events_by_asset"], {"BTC/USD": 1})

    def test_one_exceptional_wallet_can_replace_consensus(self):
        diary = [{"captured_at": f"2026-08-{day:02d}T{hour:02d}:00:00Z",
                  "sources": {"ostium": [{}], "hyperliquid_xyz": [{}],
                              "hyperliquid_mkts": [{}]}, "errors": {}}
                 for day in range(1, 21) for hour in range(15)]
        pnl = [2.0, 2.0, -1.0] * 10
        follows = [{"pair": "BTC/USD", "action": "Close", "wallet_sha256": "solo",
                    "detection_latency_seconds": 30, "entry_detection_latency_seconds": 30,
                    "implementation_shortfall_bps": 2, "copy_net_pnl_usdc": value}
                   for value in pnl]
        result = wolfpack.build_brief(diary, follows, self.pack, self.council)
        self.assertEqual(result["validation"]["route"], "exceptional_single_wallet")
        self.assertEqual(result["decision"], "READY_TO_FORM_HYPOTHESES")

    def test_source_pnl_cannot_qualify_exceptional_wallet(self):
        follows = [{"pair": "BTC/USD", "action": "Close", "wallet_sha256": "solo",
                    "closed_pnl_usd": 10} for _ in range(30)]
        result = wolfpack.build_brief([], follows, self.pack, self.council)
        reasons = result["validation"]["exceptional_wallet_blockers"]["solo"]
        self.assertIn("missing copied net PnL after observed delay and costs", reasons)

    def test_separate_paper_results_drive_exceptional_route(self):
        follows = [{"pair": "BTC/USD", "action": "Close", "wallet_sha256": "solo"}
                   for _ in range(30)]
        paper = [{"action": "Close", "wallet_sha256": "solo", "copy_net_pnl_usdc": value}
                 for value in [2.0, 2.0, -1.0] * 10]
        for row in paper:
            row["implementation_shortfall_bps"] = 2
            row["entry_detection_latency_seconds"] = 30
        result = wolfpack.build_brief([], follows, self.pack, self.council, paper)
        self.assertEqual(result["validation"]["route"], "exceptional_single_wallet")

    def test_profitable_but_slow_wallet_is_not_exceptional(self):
        paper = [{"action": "Close", "wallet_sha256": "slow", "copy_net_pnl_usdc": value,
                  "implementation_shortfall_bps": 2, "entry_detection_latency_seconds": 180}
                 for value in [2.0, 2.0, -1.0] * 10]
        qualified, blockers = wolfpack.exceptional_wallets(paper)
        self.assertEqual(qualified, [])
        self.assertIn("median entry detection latency exceeds 120 seconds", blockers["slow"])

    def test_candidate_then_titular_roster(self):
        def rows(wallet, count):
            return [{"action": "Close", "wallet_sha256": wallet,
                     "copy_net_pnl_usdc": [2.0, 2.0, -1.0][index % 3],
                     "implementation_shortfall_bps": 2,
                     "entry_detection_latency_seconds": 30}
                    for index in range(count)]
        roster = wolfpack.portfolio_roster(rows("candidate", 12) + rows("titular", 30), True)
        self.assertEqual([row["wallet_sha256"] for row in roster["candidates"]], ["candidate"])
        self.assertEqual([row["wallet_sha256"] for row in roster["titulars"]], ["titular"])
        self.assertEqual(roster["portfolio_eligible"], ["titular"])
        self.assertFalse(roster["live_trading_authorized"])

    def test_no_roster_before_execution_realism(self):
        roster = wolfpack.portfolio_roster([], False)
        self.assertEqual(roster["portfolio_eligible"], [])


if __name__ == "__main__":
    unittest.main()
