#!/usr/bin/env python3
from temporal_gate import _number

assert _number({"metric": "1.25"}, "metric") == 1.25
print("PASS: temporal gate primitives")
