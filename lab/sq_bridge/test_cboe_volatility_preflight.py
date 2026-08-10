import tempfile
import unittest
from pathlib import Path

from cboe_volatility_preflight import inspect_csv


class CboeVolatilityPreflightTest(unittest.TestCase):
    def write(self, text):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
        tmp.write(text)
        tmp.close()
        return Path(tmp.name)

    def test_valid_csv(self):
        path = self.write(
            "DATE,OPEN,HIGH,LOW,CLOSE\n"
            "01/03/2012,20,22,19,21\n"
            "12/31/2018,18,19,17,18.5\n"
        )
        result = inspect_csv(path, "VIX")
        self.assertEqual(result["duplicate_dates"], 0)
        self.assertEqual(result["invalid_ohlc_development"], 0)
        self.assertEqual(result["gate"], "PASS")

    def test_duplicate_and_invalid_ohlc_fail(self):
        path = self.write(
            "DATE,OPEN,HIGH,LOW,CLOSE\n"
            "01/03/2012,20,19,18,21\n"
            "01/03/2012,20,22,19,21\n"
            "12/31/2018,18,19,17,18.5\n"
        )
        result = inspect_csv(path, "VIX")
        self.assertEqual(result["duplicate_dates"], 1)
        self.assertEqual(result["invalid_ohlc_total"], 1)
        self.assertEqual(result["invalid_ohlc_development"], 1)
        self.assertEqual(result["gate"], "FAIL")

    def test_predevelopment_anomaly_is_disclosed_but_does_not_block(self):
        path = self.write(
            "DATE,OPEN,HIGH,LOW,CLOSE\n"
            "01/03/2006,20,19,18,21\n"
            "01/03/2012,20,22,19,21\n"
            "12/31/2018,18,19,17,18.5\n"
        )
        result = inspect_csv(path, "VIX")
        self.assertEqual(result["invalid_ohlc_total"], 1)
        self.assertEqual(result["invalid_ohlc_development"], 0)
        self.assertEqual(result["gate"], "PASS")


if __name__ == "__main__":
    unittest.main()
