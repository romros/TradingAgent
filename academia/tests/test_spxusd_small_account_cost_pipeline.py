import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import summarize_execution_quotes

from lab.sq_bridge.spxusd_small_account_cost_gate import derive


def quote(day: int, window: str, minute: int) -> dict:
    return {
        "captured_at": f"2026-08-{day:02d}T14:{minute:02d}:00Z",
        "instrument": "US500/USD",
        "is_market_open": True,
        "session_window": window,
        "mid": 7500,
        "bid": 7499.5,
        "ask": 7500.5,
        "open_fee_bps": 1,
        "close_fee_bps": 0,
        "rollover_rate": {"long": "-0.005", "short": "0.002"},
        "simulated_slippage": {
            side: [{"ntl": str(notional), "slippage": "0.004"}
                   for notional in (60, 100, 200, 400, 500)]
            for side in ("long", "short")
        },
    }


class SpxSmallAccountCostPipelineTest(unittest.TestCase):
    def test_raw_quotes_to_frozen_200_usdc_costs(self):
        rows = [quote(day, window, minute)
                for day in range(1, 4)
                for window in ("open", "midday", "close")
                for minute in range(0, 40, 2)]

        summary = summarize_execution_quotes.summarize(rows)
        costs = derive(summary)

        self.assertEqual(summary["decision"], "MEASURED")
        self.assertEqual(summary["accepted_samples"], 180)
        self.assertEqual(summary["statistics_scope"], "qualifying_complete_days_only")
        self.assertEqual(costs["decision"], "PASS_COSTS_FROZEN")
        self.assertEqual(costs["qualifying_complete_days"],
                         ["2026-08-01", "2026-08-02", "2026-08-03"])
        self.assertAlmostEqual(costs["by_notional"]["200"]["base_roundtrip_bps"],
                               1.8)
        self.assertAlmostEqual(costs["by_notional"]["200"]["stress_roundtrip_bps"],
                               8.6)
        self.assertFalse(costs["paper_authorized"])
        self.assertFalse(costs["live_authorized"])

    def test_count_without_temporal_span_stays_blocked_end_to_end(self):
        rows = [quote(day, window, 0)
                for day in range(1, 4)
                for window in ("open", "midday", "close")
                for _ in range(20)]

        summary = summarize_execution_quotes.summarize(rows)
        costs = derive(summary)

        self.assertEqual(summary["decision"], "INSUFFICIENT_OPEN_SESSION_COVERAGE")
        self.assertEqual(costs["decision"], "BLOCK_INSUFFICIENT_EXECUTION_COVERAGE")
        self.assertFalse(costs["costs_frozen"])


if __name__ == "__main__":
    unittest.main()
