import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import import_sqx_evidence


class SqxEvidenceTest(unittest.TestCase):
    def test_external_missing_file_fails_without_side_effects(self):
        with self.assertRaises(FileNotFoundError):
            import_sqx_evidence.extract(Path("/tmp/does-not-exist.sqx"))

    def test_parameter_helper_is_deterministic(self):
        from xml.etree import ElementTree as ET
        item = ET.fromstring('<Item><Param key="#Period#">14</Param><Param key="#Shift#">2</Param></Item>')
        self.assertEqual(import_sqx_evidence._params(item), {"Period": "14", "Shift": "2"})


if __name__ == "__main__":
    unittest.main()
