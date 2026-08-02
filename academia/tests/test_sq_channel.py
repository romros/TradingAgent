import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import sq_channel


class SqChannelTest(unittest.TestCase):
    def test_artifact_and_cli_precede_browser(self):
        self.assertEqual(sq_channel.choose({"artifact_available": True})["decision"], "artifact")
        self.assertEqual(sq_channel.choose({"sqcli_supported": True})["decision"], "sqcli")

    def test_pinchtab_requires_evidenced_gap(self):
        operation = {"ui_state_observable": True, "agentic_one_off": True}
        self.assertEqual(sq_channel.choose(operation)["decision"], "BLOCKED")
        operation["gap_evidence"] = "control absent from SQCLI"
        self.assertEqual(sq_channel.choose(operation)["decision"], "pinchtab")

    def test_live_is_never_routed(self):
        self.assertEqual(sq_channel.choose({"live_trading": True})["decision"], "REJECT")


if __name__ == "__main__":
    unittest.main()
