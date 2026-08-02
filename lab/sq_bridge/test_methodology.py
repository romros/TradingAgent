#!/usr/bin/env python3
import json
from pathlib import Path
from methodology import validate

config = json.loads(Path(__file__).with_name("methodology_v1.json").read_text())
assert validate(config) == []
broken = json.loads(json.dumps(config))
broken["temporal_split"]["train_pct"] = 51
broken["principles"]["holdout_policy"] = "visible"
assert len(validate(broken)) == 2
print("PASS: Alquimia methodology contract")
