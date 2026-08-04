import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sqx_to_reality


def extracted():
    return {
        "candidate_id": "sq-candidate",
        "artifact_sha256": "a" * 64,
        "classification": "OOS_RESULT_NOT_LIVE_READY",
        "generation_result": {"history_from": "2010-01-01", "history_to": "2018-12-31"},
        "execution_assumptions": {"instrument": "GENERIC"},
    }


def supplement():
    return {
        "venue": "target",
        "sealed_period": {"start": "2024", "end": "2026", "used_in_development": False},
        "mechanism": {"hypothesis": "persistent mechanism", "falsifier": "negative comparable regimes"},
        "normalization": {"price_distances": "atr", "position_risk": "equity_percent"},
        "regime_results": [
            {"id": "r1", "tags": ["trend"], "trades": 30, "net_expectancy": .1, "comparable_to_current": True},
            {"id": "r2", "tags": ["range"], "trades": 30, "net_expectancy": .05, "comparable_to_current": False},
        ],
        "current_execution": {"evidence_complete": True, "price_asof": "2026-08-01", "spread": 1, "slippage": 1, "commission": 1, "minimum_position_notional": 100, "account_equity": 200, "liquidation_checked": True, "net_expectancy": .02},
    }


class SqxToRealityTest(unittest.TestCase):
    def test_sqx_alone_stays_incomplete(self):
        result = sqx_to_reality.build(extracted())
        self.assertEqual(result["decision"], "INCOMPLET")
        self.assertIn("regime_results", result["missing"])
        self.assertIsNone(result["manifest"])

    def test_complete_supplement_reaches_reality_gate(self):
        result = sqx_to_reality.build(extracted(), supplement())
        self.assertEqual(result["decision"], "OBRIR HOLDOUT")
        self.assertEqual(result["manifest"]["candidate_id"], "sq-candidate")

    def test_supplement_cannot_override_sqx_identity(self):
        extra = supplement()
        extra["instrument"] = "DIFFERENT"
        result = sqx_to_reality.build(extracted(), extra)
        self.assertEqual(result["decision"], "INCOMPLET")
        self.assertEqual(result["conflicts"], ["instrument"])


if __name__ == "__main__":
    unittest.main()
