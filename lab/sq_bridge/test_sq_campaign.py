#!/usr/bin/env python3

import tempfile
import zipfile
from pathlib import Path

from sq_campaign import inspect, prepare


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    source = root / "source.cfx"
    output = root / "pilot.cfx"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("config.xml", '<Project name="Original" version="143"/>')
        archive.writestr(
            "Build-Task1.xml",
            '<MaxStrategies>1000</MaxStrategies><StopCondition passedStrategies="1000"/>',
        )

    manifest = prepare(source, output, "TA_SQ_PILOT", 20)
    result = inspect(output)

    assert manifest["changed_limit_fields"] == 2
    assert result["project_name"] == "TA_SQ_PILOT"
    assert result["strategy_limits"] == [20, 20]
    assert output.with_suffix(".manifest.json").exists()

print("PASS: sq_campaign prepare/inspect")
