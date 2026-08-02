import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_sq_cow_runtime


class SqCowRuntimeTest(unittest.TestCase):
    def fixture(self, root: Path):
        internal = root / "source/internal"
        user = root / "source/user"
        (internal / "libs").mkdir(parents=True)
        (internal / "libs/a.jar").write_bytes(b"jar")
        (user / "data/History/X").mkdir(parents=True)
        (user / "data/History/X/bars.bin").write_bytes(b"history")
        (user / "data/data.db").write_bytes(b"db")
        return internal, user

    def test_busy_runtime_is_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            internal, user = self.fixture(root)
            result = prepare_sq_cow_runtime.assess(internal, user, root / "runtime/test", root / "runtime", 1)
            self.assertIn("sq_busy:1", result["blockers"])

    def test_copy_excludes_history_payload_and_creates_mountpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            internal, user = self.fixture(root)
            destination = root / "runtime/test"
            result = prepare_sq_cow_runtime.assess(internal, user, destination, root / "runtime", 0)
            self.assertTrue(result["ready_to_copy"])
            prepare_sq_cow_runtime.prepare(internal, user, destination)
            self.assertTrue((destination / "internal/libs/a.jar").exists())
            self.assertTrue((destination / "user/data/data.db").exists())
            self.assertTrue((destination / "user/data/History").is_dir())
            self.assertFalse((destination / "user/data/History/X/bars.bin").exists())

    def test_destination_outside_runtime_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            internal, user = self.fixture(root)
            result = prepare_sq_cow_runtime.assess(internal, user, root / "elsewhere", root / "runtime", 0)
            self.assertIn("destination_outside_academia_runtime", result["blockers"])


if __name__ == "__main__":
    unittest.main()
