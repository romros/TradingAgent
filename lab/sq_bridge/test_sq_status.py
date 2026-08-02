#!/usr/bin/env python3

import tempfile
from pathlib import Path

from sq_status import build_status


with tempfile.TemporaryDirectory() as tmp:
    project = Path(tmp) / "PILOT"
    (project / "log").mkdir(parents=True)
    (project / "databanks" / "Results").mkdir(parents=True)
    (project / "log" / "global_log_1.log").write_text(
        "Project started\nBuild running\n", encoding="utf-8"
    )
    (project / "databanks" / "Results" / "Strategy 1.sqx").touch()
    status = build_status(project)
    assert status["phase"] == "building"
    assert status["databanks"]["Results"] == 1
    assert status["errors"] == []

print("PASS: SQ compact status")
