import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from compare_order_parity import compare


def row(open_price="1.1000", open_time="2026.01.01 00:00:00"):
    return {
        "Type": "Buy",
        "Open time": open_time,
        "Close time": "2026.01.01 04:00:00",
        "Open price": open_price,
        "Close price": "1.1100",
        "Size": "0.1",
    }


class OrderParityTests(unittest.TestCase):
    def test_identical_orders_pass(self):
        result = compare([row()], [row()], 0, 0, 0)
        self.assertTrue(result["passed"])

    def test_price_difference_fails_outside_tolerance(self):
        result = compare([row()], [row(open_price="1.1002")], 0, 0.0001, 0)
        self.assertFalse(result["passed"])
        self.assertIn("open_price", result["mismatches"][0]["fields"])

    def test_count_difference_fails(self):
        result = compare([row(), row()], [row()], 0, 0, 0)
        self.assertEqual(result["count_delta"], -1)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
