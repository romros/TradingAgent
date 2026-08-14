import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "projects" / "wolfpack" / "opportunity_codex_monitor.py"
spec = importlib.util.spec_from_file_location("opportunity_codex_monitor", MODULE)
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


class OpportunityCodexMonitorTest(unittest.TestCase):
    def test_snapshot_buckets_material_regime_without_calling_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = [
                {"captured_at": "2026-08-14T10:00:00Z", "sources": {"ostium": [
                    {"instrument": "BTC/USD", "mid": 100}]}},
                {"captured_at": "2026-08-14T11:00:00Z", "sources": {"ostium": [
                    {"instrument": "BTC/USD", "mid": 101}]}}
            ]
            (root / "diary").write_text("\n".join(json.dumps(row) for row in rows))
            (root / "link").write_text(json.dumps({"status": "WATCH"}))
            payload = monitor.snapshot(root / "diary", root / "link")
            self.assertEqual(payload["markets"]["BTC/USD"]["regime"], "UP")
            self.assertEqual(payload["link"]["status"], "WATCH")
            self.assertFalse(payload["live_trading_authorized"])
            self.assertEqual(monitor.material_signature(payload), monitor.material_signature(payload))


if __name__ == "__main__":
    unittest.main()
