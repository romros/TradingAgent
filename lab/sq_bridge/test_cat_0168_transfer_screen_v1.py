import csv
import tempfile
import unittest
from pathlib import Path

import cat_0168_transfer_screen_v1 as subject


class FrozenTransferScreenTest(unittest.TestCase):
    def _source(self, name="SYNTH_2017_2024.csv", include_2025=False):
        folder = tempfile.TemporaryDirectory()
        path = Path(folder.name) / name
        rows = []
        for year in range(2017, 2026 if include_2025 else 2025):
            for day in range(1, 61):
                date = f"{year}.{1 + (day - 1) // 28:02d}.{1 + (day - 1) % 28:02d}"
                base = 100 + (year - 2017) * 2 + day * .03
                # Repeated downside impulses make -DI turn-down signals.
                low = base - (3 if day % 11 == 0 else .8)
                rows.append([date, "00:00", base, base + 1, low, base + .2, 1])
        with path.open("w", newline="") as stream:
            csv.writer(stream).writerows(rows)
        return folder, path

    def test_periods_are_frozen_and_2025_is_not_accessed(self):
        folder, path = self._source()
        self.addCleanup(folder.cleanup)
        result = subject.screen("SYNTH", path, [1000])
        self.assertEqual(set(result["periods"]), {"train", "validation", "oos"})
        self.assertEqual(result["periods"]["oos"]["date_to"], "2024.12.31")
        self.assertFalse(result["optimized"])
        self.assertFalse(result["holdout_2025_accessed"])

    def test_filename_gate_rejects_holdout_before_loading(self):
        folder, path = self._source(name="SYNTH_2017_2025.csv", include_2025=True)
        self.addCleanup(folder.cleanup)
        with self.assertRaisesRegex(ValueError, "must not mention 2025"):
            subject.screen("SYNTH", path, [1000])

    def test_hidden_2025_row_is_rejected(self):
        folder, path = self._source(include_2025=True)
        self.addCleanup(folder.cleanup)
        with self.assertRaisesRegex(ValueError, "holdout leakage"):
            subject.screen("SYNTH", path, [1000])

    def test_frozen_contract_has_no_cli_tuning_parameters(self):
        self.assertEqual(subject.FROZEN["atr_period"], 30)
        self.assertEqual(subject.FROZEN["stop_atr"], 2.5)
        self.assertEqual(subject.FROZEN["target_atr"], 2.1)
        self.assertIn("-DI(40)", subject.FROZEN["signal"])

    def test_cat_control_reproduces_known_period_counts_and_stress(self):
        root = Path(__file__).resolve().parents[2]
        source = root / "data/ibkr_sq_v2/preflight/CATUSUSD_NYSE_RTH_D1_2024.csv"
        result = subject.screen("CAT", source, [1000])
        periods = result["periods"]
        self.assertEqual([periods[name]["trades"] for name in ("train", "validation", "oos")],
                         [73, 36, 21])
        self.assertAlmostEqual(periods["validation"]["results"]["1000"]["stress"]["return_pct"],
                               20.919104, places=6)
        self.assertAlmostEqual(periods["oos"]["results"]["1000"]["stress"]["return_pct"],
                               13.1873, places=4)


if __name__ == "__main__":
    unittest.main()
