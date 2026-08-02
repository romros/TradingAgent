import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import academia


class CatalogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "test.db"
        self.root = Path(__file__).resolve().parents[1]
        self.source = self.root / "sources/strategyquant/build142-reference.json"
        academia.ingest(self.db, list((self.root / "sources/strategyquant").glob("*.json")))

    def tearDown(self):
        self.tmp.cleanup()

    def test_fts_search_and_domain_filter(self):
        hits = academia.search(self.db, "correlació Databank", 5, "strategyquant")
        self.assertEqual(hits[0]["source_id"], "yt_easytrading_build142_20260528")
        self.assertEqual(academia.search(self.db, "correlació", 5, "other"), [])

    def test_reingest_is_idempotent(self):
        with sqlite3.connect(self.db) as db:
            before = db.execute("SELECT count(*) FROM sources").fetchone()[0], db.execute("SELECT count(*) FROM chunks").fetchone()[0]
        academia.ingest(self.db, [self.source])
        with sqlite3.connect(self.db) as db:
            after = db.execute("SELECT count(*) FROM sources").fetchone()[0], db.execute("SELECT count(*) FROM chunks").fetchone()[0]
            self.assertEqual(after, before)

    def test_benchmark(self):
        dataset = Path(__file__).resolve().parents[1] / "benchmark/queries.jsonl"
        result = academia.benchmark(self.db, dataset, 5)
        self.assertEqual(result["cases"], 27)
        self.assertEqual(result["recall_at_5"], 1.0)
        local_cases = {item["id"]: item for item in result["details"] if item["id"].startswith("sq-local-")}
        self.assertEqual(len(local_cases), 4)
        self.assertTrue(all(item["first_relevant_rank"] == 1 for item in local_cases.values()))

    def test_hard_benchmark_tracks_no_answer(self):
        academia.ingest(self.db, list((self.root / "sources").glob("*/*.json")))
        dataset = self.root / "benchmark/hard_queries.jsonl"
        result = academia.benchmark(self.db, dataset, 5)
        self.assertEqual(result["cases"], 22)
        self.assertEqual(result["answerable_cases"], 19)
        self.assertIn("no_answer_accuracy", result)

    def test_invalid_rights_policy_is_rejected(self):
        data = json.loads(self.source.read_text())
        data["rights_policy"] = "copy_everything"
        self.assertTrue(academia.validate(data))

    def test_unknown_field_is_rejected(self):
        data = json.loads(self.source.read_text())
        data["surprise"] = True
        self.assertIn("camp desconegut: surprise", academia.validate(data))

    def test_claim_evidence_resolves_to_chunk(self):
        academia.ingest_claims(self.db, [self.root / "claims/strategyquant/core-claims.json"])
        with sqlite3.connect(self.db) as db:
            self.assertEqual(db.execute("SELECT count(*) FROM claims").fetchone()[0], 16)
            self.assertEqual(db.execute("SELECT count(*) FROM claim_evidence").fetchone()[0], 17)


if __name__ == "__main__":
    unittest.main()
