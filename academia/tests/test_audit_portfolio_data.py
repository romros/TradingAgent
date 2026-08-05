import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import audit_portfolio_data


class PortfolioDataAuditTest(unittest.TestCase):
    def database(self, root):
        path = root / "data.db"
        with sqlite3.connect(path) as db:
            db.execute("CREATE TABLE DATA (SYMBOL TEXT, INSTRUMENT TEXT, TIMEFRAME TEXT, DATEFROM INT, DATETO INT, ROWS INT)")
            db.execute("INSERT INTO DATA VALUES ('EURDATA','EURUSDOST','M1',1483228800000,1782864000000,1000)")
            db.execute("INSERT INTO DATA VALUES ('BTCUSDT','BTCUSDT','M1',1569369600000,1782864000000,1000)")
        return path

    def test_blocks_missing_and_short_history(self):
        with tempfile.TemporaryDirectory() as directory:
            result = audit_portfolio_data.audit(
                self.database(Path(directory)),
                {"EUR/USD": ["EURUSDOST"], "BTC/USD": ["BTCUSDT"], "WTI/USD": ["WTI"]},
                "2017-01-01", "2026-07-01",
            )
        self.assertFalse(result["ready"])
        self.assertEqual(result["blockers"], ["BTC/USD", "WTI/USD"])
        self.assertEqual(result["assets"][1]["status"], "insufficient_history")

    def test_all_ready_only_authorizes_project_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            result = audit_portfolio_data.audit(
                self.database(Path(directory)), {"EUR/USD": ["EURUSDOST"]},
                "2017-01-01", "2026-07-01",
            )
        self.assertTrue(result["ready"])
        self.assertEqual(result["decision"], "PREPARE_SQ_PROJECTS")


if __name__ == "__main__":
    unittest.main()
