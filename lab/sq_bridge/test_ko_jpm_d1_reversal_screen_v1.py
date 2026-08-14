import csv
import json
import tempfile
import unittest
from pathlib import Path

import ko_jpm_d1_reversal_screen_v1 as subject


class ReversalScreenTest(unittest.TestCase):
    def _source(self, asset="KO", include_2025=False):
        temporary = tempfile.TemporaryDirectory()
        path = Path(temporary.name) / f"{asset}_2017_2024.csv"
        with path.open("w", newline="") as stream:
            writer = csv.writer(stream)
            writer.writerow(["date", "open", "high", "low", "close", "volume", "minutes"])
            value = 40.0
            for year in range(2017, 2026 if include_2025 else 2025):
                for day in range(1, 241):
                    value += .15
                    if day % 31 == 0:
                        value -= 3.0
                    writer.writerow([f"{year}-{1 + (day - 1) // 20:02d}-{1 + (day - 1) % 20:02d}",
                                     value, value + .6, value - .6, value + .1, 1, 390])
        return temporary, path

    def test_real_preregistration_matches_lock(self):
        prereg, digest = subject.load_frozen(subject.DEFAULT_PREREG, subject.DEFAULT_LOCK)
        self.assertEqual(digest, "cf99b0c7b33ff9ab39c4081954b454806b2185b00ff00123e3243961bed83210")
        self.assertEqual(len(prereg["variants"]), 3)

    def test_mutated_preregistration_is_rejected(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        prereg = Path(temporary.name) / "prereg.json"
        prereg.write_text(subject.DEFAULT_PREREG.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "hash mismatch"):
            subject.load_frozen(prereg, subject.DEFAULT_LOCK)

    def test_holdout_row_is_rejected(self):
        temporary, path = self._source(include_2025=True)
        self.addCleanup(temporary.cleanup)
        with self.assertRaisesRegex(ValueError, "holdout leakage"):
            subject.load_rows(path)

    def test_filename_boundary_is_rejected_before_read(self):
        with self.assertRaisesRegex(ValueError, "must end"):
            subject.load_rows(Path("KO_2017_2025.csv"))

    def test_next_open_and_maximum_holding_are_respected(self):
        temporary, path = self._source()
        self.addCleanup(temporary.cleanup)
        rows = subject.load_rows(path)
        prereg = json.loads(subject.DEFAULT_PREREG.read_text())
        orders = subject.orders_for(rows, prereg["variants"][0], "2022-01-01", "2023-12-31")
        self.assertTrue(orders)
        self.assertTrue(all(order["close_time"] >= order["open_time"] for order in orders))
        self.assertTrue(all(order["sessions"] <= 2 for order in orders))

    def test_asset_universe_is_frozen(self):
        temporary, path = self._source(asset="AAPL")
        self.addCleanup(temporary.cleanup)
        prereg = json.loads(subject.DEFAULT_PREREG.read_text())
        with self.assertRaisesRegex(ValueError, "outside frozen universe"):
            subject.evaluate_asset("AAPL", path, prereg)


if __name__ == "__main__":
    unittest.main()
