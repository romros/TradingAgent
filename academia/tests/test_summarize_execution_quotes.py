import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import summarize_execution_quotes


def quote(day: int, window: str, *, minute: int = 0, open_: bool = True) -> dict:
    return {
        "captured_at": f"2026-08-{day:02d}T14:{minute:02d}:00Z",
        "instrument": "US500/USD",
        "is_market_open": open_,
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


class SummarizeExecutionQuotesTest(unittest.TestCase):
    def test_atomic_writer_leaves_only_complete_target(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "summary.json"
            summarize_execution_quotes.write_atomic(target, '{"ok": true}\n')
            self.assertEqual(target.read_text(), '{"ok": true}\n')
            self.assertEqual(list(Path(directory).iterdir()), [target])

    def test_requires_three_days_and_all_session_windows(self):
        rows = [quote(day, window, minute=minute) for day in range(1, 4)
                for window in ("open", "midday", "close") for minute in (0, 20, 40)]
        result = summarize_execution_quotes.summarize(rows, min_days=3, min_per_window=3)
        self.assertEqual(result["decision"], "MEASURED")
        self.assertAlmostEqual(result["spread_bps"]["p95"], 1.3333333333333333)
        self.assertAlmostEqual(result["roundtrip_proxy_bps_by_notional"]["200"]["median"],
                               3.1333333333333333)
        self.assertEqual(result["qualifying_complete_days"],
                         ["2026-08-01", "2026-08-02", "2026-08-03"])

    def test_aggregate_window_counts_cannot_hide_incomplete_days(self):
        rows = ([quote(1, window, minute=minute)
                 for window in ("open", "midday", "close") for minute in (0, 20, 40)]
                + [quote(2, "open", minute=minute) for minute in (0, 20, 40)]
                + [quote(3, "midday", minute=minute) for minute in (0, 20, 40)])
        result = summarize_execution_quotes.summarize(rows, min_days=3, min_per_window=3)
        self.assertEqual(result["decision"], "INSUFFICIENT_OPEN_SESSION_COVERAGE")
        self.assertEqual(result["qualifying_complete_days"], ["2026-08-01"])

    def test_simultaneous_rows_do_not_fake_temporal_coverage(self):
        rows = [quote(1, window) for window in ("open", "midday", "close") for _ in range(20)]
        result = summarize_execution_quotes.summarize(rows, min_days=1, min_per_window=20)
        self.assertEqual(result["decision"], "INSUFFICIENT_OPEN_SESSION_COVERAGE")
        self.assertEqual(result["qualifying_complete_days"], [])

    def test_partial_later_day_cannot_contaminate_measured_statistics(self):
        rows = [quote(day, window, minute=minute) for day in range(1, 4)
                for window in ("open", "midday", "close") for minute in (0, 20, 40)]
        outlier = quote(4, "open")
        outlier.update({"bid": 7400, "ask": 7600})
        result = summarize_execution_quotes.summarize(
            rows + [outlier], min_days=3, min_per_window=3)
        self.assertEqual(result["decision"], "MEASURED")
        self.assertEqual(result["statistical_samples"], 27)
        self.assertEqual(result["statistics_scope"], "qualifying_complete_days_only")
        self.assertLess(result["spread_bps"]["maximum"], 2)

    def test_closed_and_invalid_quotes_do_not_count(self):
        rows = [quote(1, "open", open_=False), {**quote(1, "midday"), "bid": 7600}]
        result = summarize_execution_quotes.summarize(rows, min_days=1, min_per_window=1)
        self.assertEqual(result["accepted_samples"], 0)
        self.assertEqual(result["rejected_samples"], {"invalid_quote": 1, "market_closed": 1})
        self.assertEqual(result["decision"], "INSUFFICIENT_OPEN_SESSION_COVERAGE")

    def test_missing_small_notional_slippage_is_rejected(self):
        row = quote(1, "open")
        row["simulated_slippage"]["long"] = row["simulated_slippage"]["long"][-1:]
        result = summarize_execution_quotes.summarize([row], min_days=1, min_per_window=1)
        self.assertEqual(result["accepted_samples"], 0)
        self.assertEqual(result["rejected_samples"], {"invalid_quote": 1})


if __name__ == "__main__":
    unittest.main()
