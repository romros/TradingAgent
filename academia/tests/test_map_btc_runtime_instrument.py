import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import map_btc_runtime_instrument as mapper


class MapBtcRuntimeInstrumentTest(unittest.TestCase):
    def test_maps_only_contract_metadata(self):
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "data.db"
            with sqlite3.connect(db_path) as db:
                db.execute("CREATE TABLE DATA (SYMBOL TEXT, INSTRUMENT TEXT, BROKER_ID INTEGER)")
                db.execute("CREATE TABLE BROKER (ID INTEGER)")
                db.execute("CREATE TABLE INSTRUMENTS (INSTRUMENT TEXT PRIMARY KEY, DESCRIPTION TEXT, DEFAULTSPREAD REAL, DEFAULTSLIPPAGE REAL, ORDERSIZESTEP REAL, BROKER_ID INTEGER, DATATYPE INTEGER)")
                db.execute("INSERT INTO DATA VALUES ('BTCUSDT','BTCUSDT',-1)")
                db.execute("INSERT INTO BROKER VALUES (12)")
                db.execute("INSERT INTO INSTRUMENTS VALUES ('BTCUSDT','crypto',0,0,0,-1,7)")
            result = mapper.map_instrument(db_path, True)
            self.assertFalse(result["prices_modified"])
            with sqlite3.connect(db_path) as db:
                self.assertEqual(db.execute("SELECT INSTRUMENT,BROKER_ID FROM DATA").fetchone(), ("BTCUSDOST", 12))
                self.assertEqual(db.execute("SELECT ORDERSIZESTEP FROM INSTRUMENTS WHERE INSTRUMENT='BTCUSDOST'").fetchone()[0], 0.001)


if __name__ == "__main__":
    unittest.main()
