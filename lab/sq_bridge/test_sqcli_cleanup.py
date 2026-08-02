import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqcli_cleanup import candidates


class SqcliCleanupTest(unittest.TestCase):
    def test_scopes_and_age_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); now = datetime.now(timezone.utc)
            stock = root / "internal/tmp/stock"; tests = root / "internal/testfiles"; logs = root / "logs"
            for directory in (stock, tests, logs): directory.mkdir(parents=True)
            jar = stock / "generated.jar"; keep = stock / "keep.bin"
            old_test = tests / "old"; new_test = tests / "new"; old_log = logs / "old.log"
            for path in (jar, keep, old_test, new_test, old_log): path.write_bytes(b"x")
            old = (now - timedelta(days=15)).timestamp()
            import os
            for path in (old_test, old_log): os.utime(path, (old, old))
            groups = candidates(root, now, 14, 7)
            self.assertEqual(groups["stock_jars"], [jar])
            self.assertNotIn(keep, groups["stock_jars"])
            self.assertEqual(groups["old_logs"], [old_log])
            self.assertEqual(groups["old_testfiles"], [old_test])


if __name__ == "__main__": unittest.main()
